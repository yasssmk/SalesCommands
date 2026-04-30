// frontend/src/sections/accounts/signals/SignalClusterDetailDrawer.jsx
/**
 * SignalClusterDetailDrawer — drill-down view for a signal cluster.
 *
 * Opens on click of a SignalClusterCard. Type-agnostic — handles both
 * Pain and Objective clusters. Branching is driven by
 * `clusterSummary.signal_type`:
 *
 *   Pain      → impact CRUD via AddPainImpactDialog, max_impact_level
 *               chip, human_impacts + metrics aggregation, member cards
 *               are PainCard.
 *   Objective → no impact CRUD, max_scope_level chip, target_dates
 *               section, member cards are ObjectiveCard.
 *
 * Self-contained modal state
 * --------------------------
 * The drawer owns its own dialogs (SignalEditDialog, AlertSignalReject,
 * and AddPainImpactDialog for Pain only) and routes the member cards'
 * callbacks to them. This keeps the parent (AccountQualificationTab /
 * AccountSignalsTab during transition) thin — it only needs to provide
 * accountId, choices, and a callback when something happens so it can
 * revalidate its own cluster list.
 *
 * Cache flow
 * ----------
 * Any signal/impact mutation from the members revalidates the shared
 * caches (handled by painImpacts.js / signals.js). Since the cluster
 * endpoint shares the same backend cache tag, the drawer's own cluster
 * detail fetch automatically refreshes on next focus or next mutation.
 * We also call mutateCluster() explicitly for immediate UI feedback
 * after each action.
 */

"use client";

import PropTypes from "prop-types";
import { useCallback, useMemo, useState } from "react";

// material-ui
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// ant-design icons
import AlertOutlined from "@ant-design/icons/AlertOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import UndoOutlined from "@ant-design/icons/UndoOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";

// project imports
import ObjectiveCard from "components/cards/signals/ObjectiveCard";
import PainCard from "components/cards/signals/PainCard";
import TechStackCard from "components/cards/signals/TechStackCard";
import AddPainImpactDialog from "./pain/AddPainImpactDialog";
import AlertSignalReject from "./AlertSignalReject";
import SignalEditDialog from "./SignalEditDialog";

import {
  useGetClusterDetail,
  archiveCluster,
  unarchiveCluster,
} from "api/signals/signalClusters";
import { validateSignal, deleteSignal } from "api/signals/signals";
import { deletePainImpact } from "api/signals/painImpacts";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

import {
  resolveFreshness,
  resolveHumanImpact,
  resolveImpactLevel,
  resolvePriority,
  resolveScopeLevel,
  resolveSignalTypeVisuals,
  resolveTargetDateUrgency,
  resolveUsageScope,
} from "sections/accounts/signals/signalClusters";

// ==============================|| CONSTANTS ||============================== //

/**
 * Drawer width — responsive.
 * xs (mobile) full-width, sm/md tablet ~560px, lg+ 640px for comfortable
 * nested member card reading without feeling cramped.
 */
const DRAWER_WIDTH = { xs: "100%", sm: 560, md: 640 };

// ==============================|| HELPERS ||============================== //

function formatShortDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

/**
 * Build the canonical display label for a TechStack cluster from its
 * tech_catalog_entry payload. Mirror of TechStackCard.getCatalogLabel
 * and SignalClusterCard.getCatalogLabel — kept local for symmetry,
 * concat is too trivial to warrant a shared module.
 *
 *   { company_name: "Salesforce", product_name: "Sales Cloud" }
 *     → "Salesforce Sales Cloud"
 *   { company_name: "Notion", product_name: "Notion" }
 *     → "Notion"
 */
function getCatalogLabel(entry) {
  if (!entry) return "Unknown tool";
  const company = entry.company_name?.trim() || "";
  const product = entry.product_name?.trim() || "";
  if (!company && !product) return "Unknown tool";
  if (!company) return product;
  if (!product || product === company) return company;
  return `${company} ${product}`;
}

// ==============================|| STAT CELL ||============================== //

/**
 * Small labelled stat cell used in the stats grid at the top of the body.
 *
 * value handling
 * --------------
 * MUI Typography defaults its HTML element to <p> for body/caption variants.
 * If we unconditionally wrap the `value` prop in <Typography>, any caller
 * passing a nested <Typography> (e.g. styled fallback) or any component that
 * itself renders a <p> would produce invalid <p><p>…</p></p> markup and
 * trigger a hydration error.
 *
 * We therefore:
 *   - wrap primitive values (string/number) in a <Typography> for consistent
 *     style with other cells;
 *   - render composite values (Chip, custom node) directly so callers can
 *     style them as they wish.
 */
function StatCell({ label, value, hint }) {
  const isPrimitiveValue =
    typeof value === "string" || typeof value === "number";

  return (
    <Stack spacing={0.25}>
      <Typography variant="caption" color="text.disabled" fontWeight={500}>
        {label}
      </Typography>

      {isPrimitiveValue ? (
        <Typography variant="body1" fontWeight={600}>
          {value}
        </Typography>
      ) : (
        value
      )}

      {hint && (
        <Typography variant="caption" color="text.disabled">
          {hint}
        </Typography>
      )}
    </Stack>
  );
}

StatCell.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  hint: PropTypes.string,
};

// ==============================|| BY-LEVEL ACCORDION ||============================== //

/**
 * Format a contact's display name from the by_level payload shape.
 *
 *   { first_name: 'Marie', last_name: 'Durand', job_title: 'CFO' }
 *   → "Marie Durand · CFO"
 *
 * Job title is folded in only when present. Returns "Unknown contact"
 * as a defensive fallback so a malformed entry never renders as blank.
 */
function formatByLevelContact(contact) {
  if (!contact) return "Unknown contact";
  const fullName =
    `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  const base = fullName || "Unknown contact";
  return contact.job_title ? `${base} · ${contact.job_title}` : base;
}

/**
 * One entry row inside a DEPARTMENT or PERSONAL accordion section.
 *
 * Renders: scope-colored bullet + entity name + impact_count chip +
 * parent-pains count chip. Compact single-line layout that wraps on
 * narrow widths.
 */
function ByLevelEntryRow({ name, impactCount, parentPainsCount, color, icon }) {
  const Icon = icon;
  return (
    <Stack
      direction="row"
      spacing={1}
      alignItems="center"
      flexWrap="wrap"
      useFlexGap
      sx={{ py: 0.5 }}
    >
      <Box
        sx={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          bgcolor: `${color}.main`,
          flexShrink: 0,
        }}
      />
      {Icon && <Icon style={{ fontSize: 12, color: "#8c8c8c" }} />}
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{
          flex: 1,
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={name}
      >
        {name}
      </Typography>
      <Tooltip title="Impacts recorded at this level">
        <Chip
          label={`${impactCount} impact${impactCount === 1 ? "" : "s"}`}
          size="small"
          variant="outlined"
          sx={{ fontSize: "0.62rem", height: 18 }}
        />
      </Tooltip>
      <Tooltip title="Number of parent pain observations contributing">
        <Chip
          label={`From ${parentPainsCount} pain${parentPainsCount === 1 ? "" : "s"}`}
          size="small"
          variant="outlined"
          sx={{
            fontSize: "0.62rem",
            height: 18,
            color: "text.disabled",
          }}
        />
      </Tooltip>
    </Stack>
  );
}

ByLevelEntryRow.propTypes = {
  name: PropTypes.string.isRequired,
  impactCount: PropTypes.number.isRequired,
  parentPainsCount: PropTypes.number.isRequired,
  color: PropTypes.string.isRequired,
  icon: PropTypes.elementType,
};

/**
 * ByLevelAccordion — Pain-only breakdown of a cluster's VALIDATED
 * PainImpacts grouped by ScopeLevel.
 *
 * The backend's by_level payload (Wave A) tells the rep at which
 * organisational layer the pain has been documented and which parent
 * pain observations contributed. This component renders that as a
 * three-section MUI Accordion:
 *
 *   BUSINESS   — single fixed entry (always rendered, even at zero)
 *   DEPARTMENT — one entry per impacted department
 *   PERSONAL   — one entry per impacted contact
 *
 * Sections without entries (empty DEPARTMENT or PERSONAL dicts) are
 * skipped entirely. BUSINESS is always present in the payload —
 * impact_count may legitimately be zero, in which case the accordion
 * summary states the absence and the details panel is not rendered.
 *
 * Visual rules:
 *   - BUSINESS expanded by default (broadest scope, most likely useful)
 *   - DEPARTMENT / PERSONAL collapsed by default
 *   - Bullet color follows the same scope palette as PainImpact rows
 *     (warning / info / error)
 *
 * @param {Object} byLevel - Cluster `by_level` payload. May be null.
 */
function ByLevelAccordion({ byLevel }) {
  // Defensive: backend always emits the key for Pain detail, but we
  // don't want a missing field to break the drawer. Render nothing.
  if (!byLevel || typeof byLevel !== "object") {
    return null;
  }

  const business = byLevel.BUSINESS ?? { impact_count: 0, parent_pain_ids: [] };
  const departmentEntries = Object.entries(byLevel.DEPARTMENT ?? {});
  const personalEntries = Object.entries(byLevel.PERSONAL ?? {});

  // Sort each non-business bucket by impact_count desc so the most
  // impacted entity surfaces first. Stable (preserves backend tie order).
  departmentEntries.sort(
    (a, b) => (b[1]?.impact_count ?? 0) - (a[1]?.impact_count ?? 0),
  );
  personalEntries.sort(
    (a, b) => (b[1]?.impact_count ?? 0) - (a[1]?.impact_count ?? 0),
  );

  const businessImpactCount = business.impact_count ?? 0;
  const businessParentCount = Array.isArray(business.parent_pain_ids)
    ? business.parent_pain_ids.length
    : 0;
  const businessHasContent = businessImpactCount > 0;

  return (
    <Box sx={{ mx: 2.5, mb: 2 }}>
      <Typography
        variant="caption"
        color="text.disabled"
        fontWeight={500}
        sx={{ display: "block", mb: 0.75 }}
      >
        BREAKDOWN BY LEVEL
      </Typography>

      {/* ==================== BUSINESS ==================== */}
      <Accordion
        defaultExpanded={businessHasContent}
        disableGutters
        elevation={0}
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1,
          mb: 0.5,
          "&:before": { display: "none" },
        }}
      >
        <AccordionSummary
          expandIcon={<DownOutlined style={{ fontSize: 11 }} />}
          sx={{
            minHeight: 36,
            "& .MuiAccordionSummary-content": { my: 0.5 },
          }}
        >
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
            sx={{ flex: 1 }}
          >
            <Box
              sx={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                bgcolor: "warning.main",
              }}
            />
            <Typography variant="body2" fontWeight={600}>
              Business
            </Typography>
            <Typography variant="caption" color="text.disabled">
              {businessHasContent
                ? `${businessImpactCount} impact${
                    businessImpactCount === 1 ? "" : "s"
                  } from ${businessParentCount} pain${
                    businessParentCount === 1 ? "" : "s"
                  }`
                : "No business-level impact yet"}
            </Typography>
          </Stack>
        </AccordionSummary>
        {businessHasContent && (
          <AccordionDetails sx={{ pt: 0, pb: 1 }}>
            {/*
              Business is a flat scope — there's no entity to break down
              by. We surface the same metrics as the summary in the
              detail body so the open / closed state stays informative.
            */}
            <Typography variant="caption" color="text.secondary">
              {businessImpactCount} business-level impact
              {businessImpactCount === 1 ? "" : "s"} recorded across{" "}
              {businessParentCount} parent pain
              {businessParentCount === 1 ? "" : "s"} in this cluster.
            </Typography>
          </AccordionDetails>
        )}
      </Accordion>

      {/* ==================== DEPARTMENT ==================== */}
      {departmentEntries.length > 0 && (
        <Accordion
          disableGutters
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            mb: 0.5,
            "&:before": { display: "none" },
          }}
        >
          <AccordionSummary
            expandIcon={<DownOutlined style={{ fontSize: 11 }} />}
            sx={{
              minHeight: 36,
              "& .MuiAccordionSummary-content": { my: 0.5 },
            }}
          >
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
              flexWrap="wrap"
              useFlexGap
              sx={{ flex: 1 }}
            >
              <Box
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  bgcolor: "info.main",
                }}
              />
              <Typography variant="body2" fontWeight={600}>
                Department
              </Typography>
              <Typography variant="caption" color="text.disabled">
                {departmentEntries.length} department
                {departmentEntries.length === 1 ? "" : "s"} impacted
              </Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0, pb: 1 }}>
            <Stack divider={<Divider flexItem />}>
              {departmentEntries.map(([deptId, entry]) => {
                const deptName =
                  entry?.department?.name ?? "Unknown department";
                const impactCount = entry?.impact_count ?? 0;
                const parentCount = Array.isArray(entry?.parent_pain_ids)
                  ? entry.parent_pain_ids.length
                  : 0;
                return (
                  <ByLevelEntryRow
                    key={deptId}
                    name={deptName}
                    impactCount={impactCount}
                    parentPainsCount={parentCount}
                    color="info"
                    icon={TeamOutlined}
                  />
                );
              })}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      {/* ==================== PERSONAL ==================== */}
      {personalEntries.length > 0 && (
        <Accordion
          disableGutters
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            "&:before": { display: "none" },
          }}
        >
          <AccordionSummary
            expandIcon={<DownOutlined style={{ fontSize: 11 }} />}
            sx={{
              minHeight: 36,
              "& .MuiAccordionSummary-content": { my: 0.5 },
            }}
          >
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
              flexWrap="wrap"
              useFlexGap
              sx={{ flex: 1 }}
            >
              <Box
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  bgcolor: "error.main",
                }}
              />
              <Typography variant="body2" fontWeight={600}>
                Personal
              </Typography>
              <Typography variant="caption" color="text.disabled">
                {personalEntries.length} contact
                {personalEntries.length === 1 ? "" : "s"} impacted
              </Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0, pb: 1 }}>
            <Stack divider={<Divider flexItem />}>
              {personalEntries.map(([contactId, entry]) => {
                const contactName = formatByLevelContact(entry?.contact);
                const impactCount = entry?.impact_count ?? 0;
                const parentCount = Array.isArray(entry?.parent_pain_ids)
                  ? entry.parent_pain_ids.length
                  : 0;
                return (
                  <ByLevelEntryRow
                    key={contactId}
                    name={contactName}
                    impactCount={impactCount}
                    parentPainsCount={parentCount}
                    color="error"
                    icon={UserOutlined}
                  />
                );
              })}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
}

ByLevelAccordion.propTypes = {
  byLevel: PropTypes.shape({
    BUSINESS: PropTypes.shape({
      impact_count: PropTypes.number,
      parent_pain_ids: PropTypes.arrayOf(PropTypes.string),
    }),
    DEPARTMENT: PropTypes.objectOf(
      PropTypes.shape({
        impact_count: PropTypes.number,
        parent_pain_ids: PropTypes.arrayOf(PropTypes.string),
        department: PropTypes.shape({
          id: PropTypes.string,
          name: PropTypes.string,
        }),
      }),
    ),
    PERSONAL: PropTypes.objectOf(
      PropTypes.shape({
        impact_count: PropTypes.number,
        parent_pain_ids: PropTypes.arrayOf(PropTypes.string),
        contact: PropTypes.shape({
          id: PropTypes.string,
          first_name: PropTypes.string,
          last_name: PropTypes.string,
          job_title: PropTypes.string,
        }),
      }),
    ),
  }),
};

ByLevelAccordion.defaultProps = {
  byLevel: null,
};

// ==============================|| TECH STACK OBSERVATIONS ACCORDION ||============================== //

/**
 * Per-field labels for the TechStack observations accordion.
 *
 * Each lifecycle field on TechStackSignal can have multiple distinct
 * values across the cluster's member signals (e.g. one rep recorded
 * usage_start_year=2019, another said 2020). The cluster's lifecycle
 * panel shows the predominant value; this accordion drills into the
 * full history per field, with the originating activity surfaced for
 * traceability.
 */
const OBSERVATION_FIELD_LABELS = {
  usage_start_year: "Usage start year",
  renewal_date: "Renewal date",
  cost_description: "Cost",
  is_discontinued: "Discontinuation status",
};

/**
 * TechStackObservationsAccordion — TechStack-only drill-down.
 *
 * Renders one accordion per lifecycle field that has 2+ distinct
 * observations across the cluster's member signals. Single-observation
 * fields are already covered by the Lifecycle panel — repeating them
 * in an accordion would be noise.
 *
 * Each observation entry surfaces:
 *   value           → what was reported
 *   observed_at     → when (date only)
 *   source_activity_id → which conversation (truncated UUID for compactness)
 *
 * The detail body of each accordion stays text-only and dense — the
 * drawer is already a 560–640px column, no need for chips here.
 *
 * @param {Object} allObservations - Backend payload from /detail.
 *                  Shape: { field_name: [{ value, signal_id,
 *                  source_activity_id, observed_at }, ...] }
 */
function TechStackObservationsAccordion({ allObservations }) {
  // Defensive: empty / non-object → render nothing rather than crash.
  if (!allObservations || typeof allObservations !== "object") {
    return null;
  }

  // Filter to fields with 2+ observations — singletons already covered
  // by the Lifecycle panel.
  const renderableFields = Object.entries(allObservations).filter(
    ([, obs]) => Array.isArray(obs) && obs.length >= 2,
  );

  if (renderableFields.length === 0) return null;

  return (
    <Box sx={{ mx: 2.5, mb: 2 }}>
      <Typography
        variant="caption"
        color="text.disabled"
        fontWeight={500}
        sx={{ display: "block", mb: 0.75 }}
      >
        ALL OBSERVATIONS
      </Typography>

      <Stack spacing={0.5}>
        {renderableFields.map(([fieldKey, obs]) => {
          const label = OBSERVATION_FIELD_LABELS[fieldKey] ?? fieldKey;
          return (
            <Accordion
              key={fieldKey}
              disableGutters
              elevation={0}
              sx={{
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 1,
                "&:before": { display: "none" },
              }}
            >
              <AccordionSummary
                expandIcon={<DownOutlined style={{ fontSize: 11 }} />}
                sx={{
                  minHeight: 36,
                  "& .MuiAccordionSummary-content": { my: 0.5 },
                }}
              >
                <Stack
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  sx={{ flex: 1 }}
                >
                  <Typography variant="body2" fontWeight={600}>
                    {label}
                  </Typography>
                  <Chip
                    label={`${obs.length} obs`}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: "0.6rem", height: 16 }}
                  />
                </Stack>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 0, pb: 1.25 }}>
                <Stack divider={<Divider flexItem />} spacing={0.5}>
                  {obs.map((entry, idx) => (
                    <Stack
                      // Observations may legitimately repeat (same
                      // value reported in different activities).
                      // signal_id is the natural disambiguator; index
                      // is the fallback for malformed entries.
                      // eslint-disable-next-line react/no-array-index-key
                      key={`${entry.signal_id || "noid"}-${idx}`}
                      direction="row"
                      spacing={1}
                      alignItems="center"
                      flexWrap="wrap"
                      useFlexGap
                      sx={{ py: 0.5 }}
                    >
                      <Typography variant="body2" fontWeight={500}>
                        {String(entry.value ?? "—")}
                      </Typography>
                      {entry.observed_at && (
                        <Typography variant="caption" color="text.disabled">
                          · {String(entry.observed_at).slice(0, 10)}
                        </Typography>
                      )}
                      {entry.source_activity_id && (
                        <Typography variant="caption" color="text.disabled">
                          · Activity #
                          {String(entry.source_activity_id).slice(0, 8)}
                        </Typography>
                      )}
                    </Stack>
                  ))}
                </Stack>
              </AccordionDetails>
            </Accordion>
          );
        })}
      </Stack>
    </Box>
  );
}

TechStackObservationsAccordion.propTypes = {
  allObservations: PropTypes.objectOf(
    PropTypes.arrayOf(
      PropTypes.shape({
        value: PropTypes.oneOfType([
          PropTypes.string,
          PropTypes.number,
          PropTypes.bool,
        ]),
        signal_id: PropTypes.string,
        source_activity_id: PropTypes.string,
        observed_at: PropTypes.string,
      }),
    ),
  ),
};

TechStackObservationsAccordion.defaultProps = {
  allObservations: null,
};

// ==============================|| DRAWER ||============================== //

/**
 * SignalClusterDetailDrawer
 *
 * @param {boolean}  open              - Drawer open state
 * @param {Function} onClose           - () => void
 * @param {Object}   clusterSummary    - Cluster list item (has canonical_key,
 *                                        used to trigger the detail fetch).
 *                                        Must carry signal_type for the
 *                                        type-agnostic branching.
 *                                        May be null when drawer is closed.
 * @param {string}   accountId         - Account UUID
 * @param {Object}   choices           - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {Function} onClusterChange   - () => void — notifies the parent that
 *                                        it should revalidate its list
 *                                        (archive, unarchive, member edits).
 */
export default function SignalClusterDetailDrawer({
  open,
  onClose,
  clusterSummary,
  accountId,
  choices,
  choicesLoading,
  onClusterChange,
}) {
  // ==============================|| TYPE BRANCHING ||============================== //

  /**
   * Resolve cluster type once. Defaults to 'pain' for backward
   * compatibility with any caller that forgets signal_type — the
   * legacy Pain-only behaviour stays the safe default.
   */
  const signalType = clusterSummary?.signal_type ?? "pain";
  const isPain = signalType === "pain";
  const isObjective = signalType === "objective";
  const isTechStack = signalType === "tech_stack";

  const typeVisuals = resolveSignalTypeVisuals(signalType);

  // ==============================|| DETAIL FETCH ||============================== //

  const canonicalKey = clusterSummary?.canonical_key ?? null;

  const { cluster, clusterLoading, clusterError, mutateCluster } =
    useGetClusterDetail(accountId, canonicalKey, { signalType });

  // ==============================|| DERIVED ||============================== //

  // While the detail is loading for the first time, we rely on the list
  // summary payload to render the header so the drawer doesn't flash empty.
  const display = cluster ?? clusterSummary ?? null;

  const isArchived = Boolean(display?.is_archived);
  const freshness = resolveFreshness(display?.freshness_status);
  const priority = resolvePriority(display?.priority_bucket);

  // Pain-specific
  const maxImpactLevel = resolveImpactLevel(display?.max_impact_level);

  // Objective-specific
  const maxScopeLevel = resolveScopeLevel(display?.max_scope_level);
  const targetUrgency = useMemo(
    () =>
      resolveTargetDateUrgency(
        display?.target_dates,
        display?.has_target_date_soon,
      ),
    [display?.target_dates, display?.has_target_date_soon],
  );

  const FreshnessIcon = freshness.icon;
  const PriorityIcon = priority.icon;

  const firstObservedDate = formatShortDate(display?.first_observed_at);
  const lastConfirmedDate = formatShortDate(display?.last_confirmed_at);

  /**
   * Deduplicated member signals coming from the detail payload.
   * The backend serializer field is `members` for both signal types.
   */
  const members = useMemo(
    () => (Array.isArray(cluster?.members) ? cluster.members : []),
    [cluster?.members],
  );

  /** Pain-only — metrics free-text list from VALIDATED impacts. */
  const metrics = useMemo(
    () => (Array.isArray(display?.metrics) ? display.metrics : []),
    [display?.metrics],
  );

  /** Pain-only — human impacts aggregated by type. */
  const humanImpacts = useMemo(
    () => (Array.isArray(display?.human_impacts) ? display.human_impacts : []),
    [display?.human_impacts],
  );

  /** Objective-only — sorted target dates. */
  const targetDates = useMemo(
    () => (Array.isArray(display?.target_dates) ? display.target_dates : []),
    [display?.target_dates],
  );

  // ============== TechStack-specific derived data ==============

  /**
   * Catalog entry — compact dict { id, company_name, product_name,
   * is_competitor, is_integration_target } from the cluster payload.
   * Drives the type-aware title in the header and the strategic
   * badge surface.
   */
  const techCatalogEntry = isTechStack ? display?.tech_catalog_entry : null;
  const isCompetitor = Boolean(techCatalogEntry?.is_competitor);
  const isIntegrationTarget = Boolean(techCatalogEntry?.is_integration_target);

  /** Lifecycle nested dict — {usage_start_year, renewal_date,
   *  cost_description, is_discontinued, discontinued_date}. */
  const lifecycle = isTechStack ? display?.lifecycle : null;

  /** Scope summary nested dict — {is_company_wide, departments_using:[],
   *  summary_text}. */
  const scopeSummary = isTechStack ? display?.scope_summary : null;

  /**
   * Departments using the tool — full list (no cap, drawer has the
   * room). Skipped in render when is_company_wide is true.
   */
  const departmentsUsing = useMemo(() => {
    if (!isTechStack) return [];
    const list = scopeSummary?.departments_using;
    return Array.isArray(list) ? list : [];
  }, [isTechStack, scopeSummary]);

  /**
   * Related Pain clusters cross-referencing this tool. Strong
   * commercial signal: a competitor tool with related Pains on the
   * same account is a textbook displacement opportunity. Drawer
   * surfaces the full list (no cap).
   */
  const relatedPainClusters = useMemo(() => {
    if (!isTechStack) return [];
    const list = display?.related_pain_clusters;
    return Array.isArray(list) ? list : [];
  }, [isTechStack, display?.related_pain_clusters]);

  /**
   * Per-field observations from /detail endpoint — TechStack only.
   * Shape from the backend: { usage_start_year: [{value, signal_id,
   * source_activity_id, observed_at}], renewal_date: [...], ... }.
   * Drives the "All observations" accordion drill-down.
   */
  const allObservations = isTechStack ? cluster?.all_observations : null;

  // ============================================================

  /**
   * Header title — type-aware resolution.
   *
   *   TechStack          → "<vendor> <product>" from the catalog entry
   *                        (e.g. "Salesforce Sales Cloud"). Catalog
   *                        identity, not narrative axes.
   *   Pain / Objective   → "<What> × <Dimension>" labels resolved
   *                        through choices.signal_whats /
   *                        signal_dimensions. The canonical_key carries
   *                        the raw codes ("pain:OPS:TIME"); we parse
   *                        them and map to display labels via choices
   *                        so the title matches what the user picked
   *                        in the wizard.
   *
   * Returns null when the upstream data isn't ready (catalog entry
   * missing for TechStack, choices not loaded yet for Pain/Objective,
   * malformed canonical_key) — the caller suppresses the <Typography>
   * via && so an absent title never renders an empty heading.
   */
  const canonicalText = useMemo(() => {
    // TechStack — catalog label takes precedence.
    if (isTechStack) {
      if (!techCatalogEntry) return null;
      return getCatalogLabel(techCatalogEntry);
    }

    // Pain / Objective — parse "<type>:<what>:<dimension>" and
    // resolve the labels from choices. choices may not be loaded yet
    // on first paint; fall back to the raw codes so the user sees
    // something meaningful even before choices arrive.
    const key = display?.canonical_key;
    if (!key || typeof key !== "string") return null;

    const parts = key.split(":");
    if (parts.length < 3) return null;
    const [, whatCode, dimensionCode] = parts;

    const whatLabel =
      choices?.signal_whats?.find((opt) => opt.value === whatCode)?.label ??
      whatCode;
    const dimensionLabel =
      choices?.signal_dimensions?.find((opt) => opt.value === dimensionCode)
        ?.label ?? dimensionCode;

    return `${whatLabel} × ${dimensionLabel}`;
  }, [isTechStack, techCatalogEntry, display?.canonical_key, choices]);

  const linkedCyclesCount = Array.isArray(display?.decision_cycle_ids)
    ? display.decision_cycle_ids.length
    : 0;

  // ==============================|| LOCAL STATE (modals) ||============================== //

  const [editModal, setEditModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  const [rejectModal, setRejectModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  const [impactDialog, setImpactDialog] = useState({
    open: false,
    mode: null,
    painSignalId: null,
    initialImpact: null,
  });

  const [archivalSubmitting, setArchivalSubmitting] = useState(false);

  // ==============================|| REVALIDATION ||============================== //

  /**
   * Called after any mutation that changes the cluster's underlying data.
   * - Revalidates THIS drawer's detail fetch
   * - Notifies the parent so it can revalidate its listing
   */
  const notifyChange = useCallback(() => {
    mutateCluster?.();
    onClusterChange?.();
  }, [mutateCluster, onClusterChange]);

  // ==============================|| ARCHIVE / UNARCHIVE ||============================== //

  const handleArchive = useCallback(async () => {
    if (!canonicalKey || !accountId) return;
    setArchivalSubmitting(true);
    const result = await archiveCluster({
      account: accountId,
      canonicalKey,
      signalType,
    });
    setArchivalSubmitting(false);
    if (result.success) {
      displaySuccessSnackbar("Cluster archived");
      notifyChange();
    } else {
      displayErrorSnackbar(result);
    }
  }, [accountId, canonicalKey, signalType, notifyChange]);

  const handleUnarchive = useCallback(async () => {
    if (!canonicalKey || !accountId) return;
    setArchivalSubmitting(true);
    const result = await unarchiveCluster({
      account: accountId,
      canonicalKey,
      signalType,
    });
    setArchivalSubmitting(false);
    if (result.success) {
      displaySuccessSnackbar("Cluster unarchived");
      notifyChange();
    } else {
      displayErrorSnackbar(result);
    }
  }, [accountId, canonicalKey, signalType, notifyChange]);

  // ==============================|| MEMBER LIFECYCLE HANDLERS ||============================== //

  const handleValidate = useCallback(
    async (signal, type) => {
      const result = await validateSignal(type, signal.id);
      if (result.success) {
        notifyChange();
        displaySuccessSnackbar("Signal validated");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [notifyChange],
  );

  const handleRejectOpen = useCallback((signal, type) => {
    setRejectModal({ open: true, signal, signalType: type });
  }, []);

  const handleRejectClose = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleRejectSuccess = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
    notifyChange();
    displaySuccessSnackbar("Signal rejected");
  }, [notifyChange]);

  const handleEdit = useCallback((signal, type) => {
    setEditModal({ open: true, signal, signalType: type });
  }, []);

  const handleEditClose = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleEditSuccess = useCallback(() => {
    notifyChange();
  }, [notifyChange]);

  const handleDelete = useCallback(
    async (signal, type) => {
      const result = await deleteSignal(type, signal.id);
      if (result.success) {
        notifyChange();
        displaySuccessSnackbar("Signal deleted");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [notifyChange],
  );

  // ==============================|| IMPACT HANDLERS — PAIN ONLY ||============================== //
  //
  // These handlers are bound to PainCard's onAddImpact / onEditImpact /
  // onDeleteImpact props. They never run for Objective members because
  // ObjectiveCard does not have impact-related callbacks. The dialog
  // they drive (AddPainImpactDialog) is also rendered conditionally
  // (isPain &&) so it never mounts for Objective clusters.

  const handleAddImpact = useCallback((painSignalId) => {
    setImpactDialog({
      open: true,
      mode: "create",
      painSignalId,
      initialImpact: null,
    });
  }, []);

  const handleEditImpact = useCallback((impact) => {
    setImpactDialog({
      open: true,
      mode: "edit",
      painSignalId: null,
      initialImpact: impact,
    });
  }, []);

  const handleImpactDialogClose = useCallback(() => {
    setImpactDialog({
      open: false,
      mode: null,
      painSignalId: null,
      initialImpact: null,
    });
  }, []);

  const handleImpactDialogSuccess = useCallback(() => {
    notifyChange();
    displaySuccessSnackbar("Impact saved");
  }, [notifyChange]);

  const handleDeleteImpact = useCallback(
    async (impact) => {
      const result = await deletePainImpact(impact.id);
      if (result.success) {
        notifyChange();
        displaySuccessSnackbar("Impact deleted");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [notifyChange],
  );

  // ==============================|| RENDER: HEADER ||============================== //

  const renderHeader = () => (
    <Box sx={{ px: 2.5, pt: 2, pb: 1.5 }}>
      {/* Top row: chips + close button */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        sx={{ mb: 1 }}
      >
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
        >
          {/* Type chip — colored per signal_type */}
          <Chip
            label={typeVisuals.label}
            color={typeVisuals.color}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />

          {display?.priority_bucket && (
            <Tooltip
              title={`Priority score: ${display?.priority_score ?? "—"}`}
            >
              <Chip
                icon={<PriorityIcon style={{ fontSize: 11 }} />}
                label={priority.label}
                color={priority.color}
                variant={priority.variant}
                size="small"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            </Tooltip>
          )}

          {display?.freshness_status && (
            <Tooltip title={freshness.helperText}>
              <Chip
                icon={<FreshnessIcon style={{ fontSize: 11 }} />}
                label={freshness.label}
                color={freshness.color}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            </Tooltip>
          )}

          {/* TechStack strategic flags — surfaced in the header so the
              rep sees them before scrolling through observations. */}
          {isTechStack && isCompetitor && (
            <Tooltip title="This vendor competes with us">
              <Chip
                label="Competitor"
                color="error"
                size="small"
                sx={{ fontSize: "0.62rem", height: 18 }}
              />
            </Tooltip>
          )}
          {isTechStack && isIntegrationTarget && (
            <Tooltip title="This vendor is an integration target">
              <Chip
                label="Integration"
                color="info"
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.62rem", height: 18 }}
              />
            </Tooltip>
          )}

          {/* TechStack quick-status chips — company-wide / renewal /
              discontinued. Co-located with priority/freshness so the
              entire commercial state of the cluster reads in one row. */}
          {isTechStack && scopeSummary?.is_company_wide && (
            <Tooltip title="Used company-wide across multiple departments">
              <Chip
                label="Company-wide"
                color="success"
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            </Tooltip>
          )}
          {isTechStack && display?.has_renewal_soon && (
            <Tooltip title="Renewal date is within 90 days">
              <Chip
                icon={<CalendarOutlined style={{ fontSize: 11 }} />}
                label="Renewal soon"
                color="warning"
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            </Tooltip>
          )}
          {isTechStack && lifecycle?.is_discontinued && (
            <Tooltip
              title={
                lifecycle.discontinued_date
                  ? `Discontinued ${lifecycle.discontinued_date}`
                  : "Tool no longer in use"
              }
            >
              <Chip
                label="Discontinued"
                color="error"
                size="small"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            </Tooltip>
          )}

          {isArchived && (
            <Chip
              icon={<InboxOutlined style={{ fontSize: 11 }} />}
              label="Archived"
              size="small"
              sx={{ fontSize: "0.68rem", height: 20 }}
            />
          )}
        </Stack>

        <IconButton
          size="small"
          onClick={onClose}
          aria-label="Close drawer"
          sx={{ ml: 1, flexShrink: 0 }}
        >
          <CloseOutlined style={{ fontSize: 14 }} />
        </IconButton>
      </Stack>

      {/* Canonical axes title */}
      {canonicalText && (
        <Typography variant="h6" fontWeight={600} sx={{ mt: 0.5 }}>
          {canonicalText}
        </Typography>
      )}

      {/* Consolidated summary — Pain/Objective only.
          TechStack does not carry a backend-aggregated summary; its
          identity is the catalog entry, not narrative text. The scope
          summary section below carries the equivalent narrative. */}
      {!isTechStack && display?.summary && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 0.75, whiteSpace: "pre-wrap" }}
        >
          {display.summary}
        </Typography>
      )}

      {/* Pending alert */}
      {display?.has_pending_signals && display?.pending_count > 0 && (
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          sx={{
            mt: 1.5,
            py: 0.75,
            px: 1,
            bgcolor: "warning.lighter",
            borderRadius: 0.75,
            border: "1px dashed",
            borderColor: "warning.light",
          }}
        >
          <AlertOutlined style={{ fontSize: 12, color: "#faad14" }} />
          <Typography variant="caption" color="warning.dark" fontWeight={500}>
            {display.pending_count} signal
            {display.pending_count === 1 ? "" : "s"} need
            {display.pending_count === 1 ? "s" : ""} validation below
          </Typography>
        </Stack>
      )}

      {/* Archive / unarchive actions */}
      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
        {!isArchived ? (
          <Button
            size="small"
            variant="outlined"
            color="inherit"
            startIcon={<InboxOutlined />}
            onClick={handleArchive}
            disabled={archivalSubmitting || !canonicalKey}
          >
            Archive cluster
          </Button>
        ) : (
          <Button
            size="small"
            variant="outlined"
            color="primary"
            startIcon={<UndoOutlined />}
            onClick={handleUnarchive}
            disabled={archivalSubmitting || !canonicalKey}
          >
            Unarchive cluster
          </Button>
        )}
      </Stack>
    </Box>
  );

  // ==============================|| RENDER: STATS PANEL ||============================== //

  /**
   * Stats panel content branches by signal_type. The Paper container is
   * shared so the visual rhythm of the drawer body stays uniform.
   *
   * Pain stats:
   *   - Max level chip + Impacted contacts + Decision cycles
   *   - First observed / Last confirmed
   *   - Human impacts chips
   *   - Metrics list
   *
   * Objective stats:
   *   - Max scope chip + Distinct contacts + Decision cycles
   *   - First observed / Last confirmed
   *   - Target dates section with urgency badge (if applicable)
   */
  const renderStats = () => (
    <Paper
      variant="outlined"
      sx={{
        mx: 2.5,
        mb: 2,
        p: 2,
        borderRadius: 1.5,
        bgcolor: "background.default",
      }}
    >
      {/* ============== TOP ROW: type-specific scope/level + counts ============== */}
      <Stack
        direction="row"
        spacing={3}
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1.5 }}
      >
        {isPain && (
          <>
            <StatCell
              label="Max level"
              value={
                display?.max_impact_level ? (
                  <Chip
                    label={maxImpactLevel.label}
                    color={maxImpactLevel.color}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: "0.68rem", height: 20 }}
                  />
                ) : (
                  <Typography variant="body2" color="text.disabled">
                    —
                  </Typography>
                )
              }
            />
            <StatCell
              label="Impacted contacts"
              value={display?.impacted_contacts_count ?? 0}
            />
            <StatCell label="Decision cycles" value={linkedCyclesCount} />
          </>
        )}

        {isObjective && (
          <>
            <StatCell
              label="Max scope"
              value={
                display?.max_scope_level ? (
                  <Chip
                    label={maxScopeLevel.label}
                    color={maxScopeLevel.color}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: "0.68rem", height: 20 }}
                  />
                ) : (
                  <Typography variant="body2" color="text.disabled">
                    —
                  </Typography>
                )
              }
            />
            <StatCell
              label="Distinct contacts"
              value={display?.distinct_contacts_count ?? 0}
            />
            <StatCell label="Decision cycles" value={linkedCyclesCount} />
          </>
        )}

        {/* TechStack top stats: distinct contacts (rep mentions), departments
            count when not company-wide, decision cycles. The strategic
            flags (competitor / integration / discontinued) live in the
            header — they are state, not stats. */}
        {isTechStack && (
          <>
            <StatCell
              label="Distinct contacts"
              value={display?.distinct_contacts_count ?? 0}
              hint="Mentioned this tool"
            />
            <StatCell
              label={
                scopeSummary?.is_company_wide ? "Reach" : "Departments using"
              }
              value={
                scopeSummary?.is_company_wide ? (
                  <Chip
                    label="Company-wide"
                    color="success"
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: "0.68rem", height: 20 }}
                  />
                ) : (
                  departmentsUsing.length
                )
              }
            />
            <StatCell label="Decision cycles" value={linkedCyclesCount} />
          </>
        )}
      </Stack>

      {/* ============== LIFECYCLE ROW (universal) ============== */}
      <Stack
        direction="row"
        spacing={3}
        flexWrap="wrap"
        useFlexGap
        sx={{
          // Bottom margin only when there is a type-specific section below.
          mb: shouldRenderTypeSpecificSection({
            isPain,
            humanImpacts,
            metrics,
            isObjective,
            targetDates,
          })
            ? 1.5
            : 0,
        }}
      >
        {firstObservedDate && (
          <StatCell label="First observed" value={firstObservedDate} />
        )}
        {lastConfirmedDate && (
          <StatCell label="Last confirmed" value={lastConfirmedDate} />
        )}
      </Stack>

      {/* ============== PAIN: Human impacts ============== */}
      {isPain && humanImpacts.length > 0 && (
        <Stack spacing={0.75} sx={{ mb: metrics.length ? 1.5 : 0 }}>
          <Typography variant="caption" color="text.disabled" fontWeight={500}>
            Human impacts
          </Typography>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {humanImpacts.map((entry) => {
              const cfg = resolveHumanImpact(entry.type);
              return (
                <Chip
                  key={entry.type}
                  label={`${cfg.label} ×${entry.count}`}
                  size="small"
                  variant="outlined"
                  sx={{ fontSize: "0.68rem", height: 20 }}
                />
              );
            })}
          </Stack>
        </Stack>
      )}

      {/* ============== PAIN: Metrics ============== */}
      {isPain && metrics.length > 0 && (
        <Stack spacing={0.75}>
          <Typography variant="caption" color="text.disabled" fontWeight={500}>
            Metrics observed
          </Typography>
          <Stack spacing={0.25}>
            {metrics.map((metric, idx) => (
              // Metrics are free-text — index is acceptable as key since the
              // list is stable for a given cluster read and we don't reorder.
              // eslint-disable-next-line react/no-array-index-key
              <Typography
                key={`${idx}-${metric.slice(0, 20)}`}
                variant="body2"
                color="text.secondary"
                sx={{ pl: 1, borderLeft: "2px solid", borderColor: "divider" }}
              >
                {metric}
              </Typography>
            ))}
          </Stack>
        </Stack>
      )}

      {/* ============== OBJECTIVE: Target dates ============== */}
      {isObjective && targetDates.length > 0 && (
        <Stack spacing={0.75}>
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            justifyContent="space-between"
            flexWrap="wrap"
            useFlexGap
          >
            <Typography
              variant="caption"
              color="text.disabled"
              fontWeight={500}
            >
              Target dates
            </Typography>
            {targetUrgency && (
              <Chip
                icon={<CalendarOutlined style={{ fontSize: 11 }} />}
                label={targetUrgency.label}
                color={targetUrgency.color}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.62rem", height: 18 }}
              />
            )}
          </Stack>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {targetDates.map((dateStr, idx) => (
              // ISO strings can repeat across distinct objectives in the
              // same cluster — index disambiguates while preserving order.
              // eslint-disable-next-line react/no-array-index-key
              <Chip
                key={`${idx}-${dateStr}`}
                label={dateStr}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.62rem", height: 18 }}
              />
            ))}
          </Stack>
        </Stack>
      )}

      {/* ============== TECHSTACK: Lifecycle ============== */}
      {/*
        Consolidated lifecycle view from the cluster's predominant
        values. Each row renders only when its source field is set so
        a brand-new cluster doesn't show four blank rows. The "All
        observations" accordion below this Paper drills into per-field
        history when multiple distinct values exist across members.
      */}
      {isTechStack && lifecycle && (
        <Stack
          spacing={0.75}
          sx={{
            mb:
              departmentsUsing.length > 0 ||
              scopeSummary?.summary_text ||
              relatedPainClusters.length > 0
                ? 1.5
                : 0,
          }}
        >
          <Typography variant="caption" color="text.disabled" fontWeight={500}>
            Lifecycle
          </Typography>
          <Stack spacing={0.5}>
            {lifecycle.usage_start_year && (
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography
                  variant="caption"
                  color="text.disabled"
                  sx={{ minWidth: 110 }}
                >
                  Used since
                </Typography>
                <Typography variant="body2">
                  {lifecycle.usage_start_year}
                </Typography>
              </Stack>
            )}
            {lifecycle.renewal_date && (
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography
                  variant="caption"
                  color="text.disabled"
                  sx={{ minWidth: 110 }}
                >
                  Renewal date
                </Typography>
                <Typography variant="body2">
                  {lifecycle.renewal_date}
                </Typography>
              </Stack>
            )}
            {lifecycle.cost_description?.trim() && (
              <Stack direction="row" spacing={1} alignItems="flex-start">
                <Typography
                  variant="caption"
                  color="text.disabled"
                  sx={{ minWidth: 110, mt: 0.25 }}
                >
                  Cost
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ flex: 1, whiteSpace: "pre-wrap" }}
                >
                  {lifecycle.cost_description}
                </Typography>
              </Stack>
            )}
            {lifecycle.is_discontinued && (
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography
                  variant="caption"
                  color="text.disabled"
                  sx={{ minWidth: 110 }}
                >
                  Discontinued
                </Typography>
                <Typography variant="body2" color="error.main">
                  {lifecycle.discontinued_date || "Yes (no date set)"}
                </Typography>
              </Stack>
            )}
          </Stack>
        </Stack>
      )}

      {/* ============== TECHSTACK: Scope ============== */}
      {isTechStack &&
        scopeSummary &&
        (scopeSummary.summary_text || departmentsUsing.length > 0) && (
          <Stack
            spacing={0.75}
            sx={{ mb: relatedPainClusters.length > 0 ? 1.5 : 0 }}
          >
            <Typography
              variant="caption"
              color="text.disabled"
              fontWeight={500}
            >
              Scope
            </Typography>
            {scopeSummary.summary_text && (
              <Typography variant="body2" color="text.secondary">
                {scopeSummary.summary_text}
              </Typography>
            )}
            {/* Full department list — no cap (drawer has the room) */}
            {!scopeSummary.is_company_wide && departmentsUsing.length > 0 && (
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {departmentsUsing.map((dept) => {
                  const cfg = resolveUsageScope("DEPARTMENT");
                  return (
                    <Chip
                      key={dept.id}
                      label={dept.name}
                      size="small"
                      color={cfg.color}
                      variant="outlined"
                      sx={{ fontSize: "0.65rem", height: 20 }}
                    />
                  );
                })}
              </Stack>
            )}
          </Stack>
        )}

      {/* ============== TECHSTACK: Related Pains ============== */}
      {/*
        Mini-list of Pain clusters cross-referencing this tool. Strong
        commercial cue: a competitor with related Pains on the same
        account is a textbook displacement opportunity. Each row is
        informational for MVP — no navigation between clusters yet.
      */}
      {isTechStack && relatedPainClusters.length > 0 && (
        <Stack spacing={0.75}>
          <Typography variant="caption" color="text.disabled" fontWeight={500}>
            Related Pains ({relatedPainClusters.length})
          </Typography>
          <Stack spacing={0.75}>
            {relatedPainClusters.map((painCluster) => (
              <Box
                key={painCluster.canonical_key}
                sx={{
                  p: 1.25,
                  border: "1px solid",
                  borderColor: "error.light",
                  borderRadius: 1,
                  bgcolor: "error.lighter",
                }}
              >
                <Stack
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  flexWrap="wrap"
                  useFlexGap
                  sx={{ mb: 0.5 }}
                >
                  <Chip
                    label="Pain"
                    color="error"
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: "0.6rem", height: 16 }}
                  />
                  {painCluster.priority_bucket && (
                    <Chip
                      label={painCluster.priority_bucket}
                      size="small"
                      sx={{ fontSize: "0.6rem", height: 16 }}
                    />
                  )}
                  {painCluster.confirmation_count !== undefined && (
                    <Typography variant="caption" color="text.disabled">
                      {painCluster.confirmation_count} confirmation
                      {painCluster.confirmation_count === 1 ? "" : "s"}
                    </Typography>
                  )}
                </Stack>
                <Typography variant="body2">
                  {painCluster.summary || painCluster.canonical_key}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Stack>
      )}
    </Paper>
  );

  // ==============================|| RENDER: MEMBERS ||============================== //

  const renderMembers = () => (
    <Box sx={{ px: 2.5, pb: 3 }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="subtitle2" fontWeight={600}>
          Signals in this cluster
        </Typography>
        {members.length > 0 && (
          <Chip
            label={members.length}
            size="small"
            variant="outlined"
            sx={{ height: 18, fontSize: "0.62rem" }}
          />
        )}
      </Stack>

      {clusterLoading && !cluster && (
        <Stack alignItems="center" py={3}>
          <CircularProgress size={20} />
        </Stack>
      )}

      {clusterError && (
        <Stack alignItems="center" spacing={1} py={3}>
          <AlertOutlined style={{ fontSize: 24, color: "#ff4d4f" }} />
          <Typography variant="body2" color="error">
            Failed to load cluster details.
          </Typography>
        </Stack>
      )}

      {cluster && members.length === 0 && (
        <Typography
          variant="body2"
          color="text.disabled"
          sx={{ fontStyle: "italic", py: 1.5 }}
        >
          No signals to display. All previous members may have been deleted or
          rejected.
        </Typography>
      )}

      {/*
        Member rendering branches on signal_type. The lifecycle handlers
        (validate / reject / edit / delete) are shared — they accept the
        signalType parameter and route to the right backend endpoint via
        signals.js. Impact handlers are bound only on PainCard.
      */}
      {members.length > 0 && (
        <Stack spacing={1.5}>
          {isPain &&
            members.map((member) => (
              <PainCard
                key={member.id}
                pain={member}
                choices={choices}
                onValidate={handleValidate}
                onReject={handleRejectOpen}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onAddImpact={handleAddImpact}
                onEditImpact={handleEditImpact}
                onDeleteImpact={handleDeleteImpact}
              />
            ))}

          {isObjective &&
            members.map((member) => (
              <ObjectiveCard
                key={member.id}
                objective={member}
                choices={choices}
                onValidate={handleValidate}
                onReject={handleRejectOpen}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}

          {isTechStack &&
            members.map((member) => (
              <TechStackCard
                key={member.id}
                techStack={member}
                choices={choices}
                onValidate={handleValidate}
                onReject={handleRejectOpen}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}
        </Stack>
      )}
    </Box>
  );

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <Drawer
        anchor="right"
        open={open}
        onClose={onClose}
        PaperProps={{
          sx: {
            width: DRAWER_WIDTH,
            maxWidth: "100vw",
          },
        }}
      >
        {!clusterSummary ? (
          // No cluster provided — safe guard, should not happen in practice
          // because the parent only opens the drawer after setting the summary.
          <Stack alignItems="center" justifyContent="center" sx={{ py: 8 }}>
            <CircularProgress size={24} />
          </Stack>
        ) : (
          <>
            {renderHeader()}
            <Divider />
            <Box sx={{ pt: 2 }}>{renderStats()}</Box>

            {/*
              By-level breakdown — Pain only. The backend doesn't compute
              by_level for Objective clusters (see SignalClusterService.
              get_cluster_detail), so cluster?.by_level is undefined for
              Objective and the section vanishes naturally. Wrapped in
              isPain && for explicit intent, but the inner null-guard
              would also handle it.
            */}
            {isPain && cluster?.by_level && (
              <ByLevelAccordion byLevel={cluster.by_level} />
            )}

            {/*
              All observations breakdown — TechStack only. Drills into
              per-field history when multiple distinct values exist
              across the cluster's member signals. Symmetric in spirit
              to ByLevelAccordion for Pain — different content, same
              visual placement (between stats panel and members list).
            */}
            {isTechStack && allObservations && (
              <TechStackObservationsAccordion
                allObservations={allObservations}
              />
            )}

            <Divider sx={{ mx: 2.5 }} />
            <Box sx={{ pt: 2 }}>{renderMembers()}</Box>
          </>
        )}
      </Drawer>

      {/* ==================== MEMBER MODALS — universal ==================== */}

      <SignalEditDialog
        open={editModal.open}
        onClose={handleEditClose}
        onSuccess={handleEditSuccess}
        signal={editModal.signal}
        signalType={editModal.signalType}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
      />

      <AlertSignalReject
        open={rejectModal.open}
        onClose={handleRejectClose}
        onSuccess={handleRejectSuccess}
        signal={rejectModal.signal}
        signalType={rejectModal.signalType}
      />

      {/* ==================== IMPACT DIALOG — Pain only ==================== */}
      {/*
        Conditional mount: AddPainImpactDialog never mounts for Objective
        clusters. The handlers above are equally guarded by the fact that
        ObjectiveCard simply does not have onAddImpact / onEditImpact /
        onDeleteImpact in its prop surface — they cannot be triggered.
      */}
      {isPain && (
        <AddPainImpactDialog
          open={impactDialog.open}
          onClose={handleImpactDialogClose}
          onSuccess={handleImpactDialogSuccess}
          painSignalId={impactDialog.painSignalId}
          accountId={accountId}
          initialImpact={impactDialog.initialImpact}
        />
      )}
    </>
  );
}

// ==============================|| LAYOUT HELPER ||============================== //

/**
 * Decide whether the stats panel has a type-specific section below the
 * lifecycle row, so the lifecycle row's bottom margin can be set
 * accordingly. Centralised so the render() body stays uncluttered.
 */
function shouldRenderTypeSpecificSection({
  isPain,
  humanImpacts,
  metrics,
  isObjective,
  targetDates,
}) {
  if (isPain) {
    return humanImpacts.length > 0 || metrics.length > 0;
  }
  if (isObjective) {
    return targetDates.length > 0;
  }
  return false;
}

// ==============================|| PROP TYPES ||============================== //

SignalClusterDetailDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  clusterSummary: PropTypes.shape({
    canonical_key: PropTypes.string.isRequired,
    signal_type: PropTypes.string,
    // Other fields optional — the drawer fetches full detail.
  }),
  accountId: PropTypes.string.isRequired,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  onClusterChange: PropTypes.func,
};

SignalClusterDetailDrawer.defaultProps = {
  clusterSummary: null,
  choices: null,
  choicesLoading: false,
  onClusterChange: () => {},
};
