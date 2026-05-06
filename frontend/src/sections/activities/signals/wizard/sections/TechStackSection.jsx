// frontend/src/sections/activities/signals/wizard/sections/TechStackSection.jsx
/**
 * TechStackSection — wizard section for capturing TechStackSignals.
 *
 * Responsibilities:
 *   - Display list of staged tech stack signals with toggle VALIDATED / REJECTED
 *   - "+ Add Tech Stack" button reveals InlineTechStackForm inline
 *   - Calls onAdd(payload) to stage a new signal in the wizard
 *   - Calls onToggleStatus(_key) to flip a staged signal between VALIDATED / REJECTED
 *
 * Staged signal shape (managed by WizardSignalAdd):
 *   { _key: string, _status: 'VALIDATED'|'REJECTED', ...payload }
 *
 * Sprint TechStack — model alignment
 * ----------------------------------
 * The staged payload follows the new TechStackSignal model:
 *   tech_catalog_entry  : full TechCatalog object (UUID extracted at dispatch)
 *   usage_scope         : 'TEAM' | 'DEPARTMENT' | 'COMPANY' | 'UNKNOWN' | null
 *   usage_department    : department object | null (DEPARTMENT scope only)
 *   usage_start_year    : number | null
 *   renewal_date        : ISO yyyy-mm-dd | null
 *   cost_description    : string ('' allowed)
 *   is_discontinued     : boolean
 *   discontinued_date   : ISO yyyy-mm-dd | null
 *   source_activity     : activity object | null
 *   source_quote, notes : strings
 *
 * No legacy free-text fields (tech_name, category, satisfaction, usage,
 * limitations, workarounds, integrations, source_department,
 * signal_category, flat renewal_date) — they no longer exist on the
 * model and are not part of the staged shape.
 *
 * Standardisation refactor (post-PHASES A-E backend) — destructive
 * --------------------------------------------------------------
 * source_contact and source_department were never on TechStackSignal
 * (shadow-overridden on the model since Sprint TechStack), so this
 * section was never a consumer. The legacy `defaultContact` prop has
 * been dropped since InlineTechStackForm no longer carries the
 * signature parity slot.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import InlineTechStackForm from "../forms/InlineTechStackForm";
import { buildEditInitialValues } from "../forms/buildEditInitialValues";

// ==============================|| HELPERS ||============================== //

/**
 * Build the canonical display label from a tech_catalog_entry payload.
 * Mirrors the same helper in TechStackCard / SignalClusterCard /
 * SignalClusterDetailDrawer — kept local for symmetry.
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

/**
 * Format a short date label for inline display in the lifecycle row.
 * Returns null on falsy input so the caller can omit the segment.
 */
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
 * Truncate a string to max length with an ellipsis. Used for the
 * cost_description segment and for the notes preview.
 */
function truncate(str, max) {
  if (!str) return null;
  return str.length > max ? `${str.slice(0, max)}…` : str;
}

/**
 * UsageScope display labels — local copy, mirror of TechStackCard.
 *
 * Hard-coded rather than pulled from `choices` because TechStack scope
 * options are fixed and the staged card has no need for a runtime lookup.
 */
const USAGE_SCOPE_LABELS = {
  TEAM: "Team",
  DEPARTMENT: "Department",
  COMPANY: "Company-wide",
  UNKNOWN: "Unknown scope",
};

// ==============================|| STAGED TECH STACK CARD ||============================== //

/**
 * StagedTechStackCard — displays a single staged TechStackSignal with
 * a VALIDATED/REJECTED toggle.
 *
 * Layout (top to bottom):
 *   1. Header line   : "{vendor} {product}" + Competitor / Integration badges
 *   2. Scope row     : usage_scope chip + usage_department (when scope=DEPARTMENT)
 *   3. Lifecycle row : "Used since 2019 · Renewal Sep 2025 · ~80k€/year"
 *                      (each segment included only when set; null fields collapse)
 *   4. Discontinuation badge : when is_discontinued=true
 *   5. Source line   : "From {activity subject or id}" — when source_activity set
 *   6. Notes preview : truncated to 80 chars
 *   7. Actions       : Include/Exclude toggle + Edit + Remove
 *
 * Visual rules:
 *   - REJECTED state strikes through the title and dims to opacity 0.75
 *   - The container border switches to error.light / error.lighter for REJECTED
 *   - Strategic flags (Competitor / Integration) earn explicit chips IN ADDITION
 *     to driving border emphasis on the live card (TechStackCard); inside the
 *     wizard staging context the border stays scoped to the include/exclude
 *     state — the staged card is not a final display surface.
 *
 * `choices` is kept in the signature for parity with the section's other
 * staged cards but is not used here — TechStack scope and discontinuation
 * options are static and rendered from local label tables.
 */
function StagedTechStackCard({
  signal,
  // eslint-disable-next-line no-unused-vars
  choices,
  onToggleStatus,
  onEdit,
  onRemove,
}) {
  const isRejected = signal._status === "REJECTED";

  // ----- Catalog anchor -----
  const catalogLabel = useMemo(
    () => getCatalogLabel(signal.tech_catalog_entry),
    [signal.tech_catalog_entry],
  );
  const isCompetitor = Boolean(signal.tech_catalog_entry?.is_competitor);
  const isIntegrationTarget = Boolean(
    signal.tech_catalog_entry?.is_integration_target,
  );

  // ----- Scope -----
  const scopeLabel = signal.usage_scope
    ? (USAGE_SCOPE_LABELS[signal.usage_scope] ?? signal.usage_scope)
    : null;

  /**
   * usage_department arrives from the staged payload as an object whole
   * (AsyncSelect compatibility) — we extract its name for display.
   * Defensive: if a UUID string ever lands here, render that as-is.
   */
  const departmentName = useMemo(() => {
    const dept = signal.usage_department;
    if (!dept) return null;
    if (typeof dept === "string") return dept;
    return dept.name ?? null;
  }, [signal.usage_department]);

  // ----- Lifecycle compact line -----
  const lifecycleLine = useMemo(() => {
    const parts = [];

    if (signal.usage_start_year) {
      parts.push(`Used since ${signal.usage_start_year}`);
    }
    if (signal.renewal_date) {
      const label = formatShortDate(signal.renewal_date);
      if (label) parts.push(`Renewal ${label}`);
    }
    if (signal.cost_description?.trim()) {
      parts.push(truncate(signal.cost_description.trim(), 50));
    }

    return parts.length > 0 ? parts.join(" · ") : null;
  }, [signal.usage_start_year, signal.renewal_date, signal.cost_description]);

  // ----- Discontinuation -----
  const discontinuationLabel = useMemo(() => {
    if (!signal.is_discontinued) return null;
    const dateLabel = formatShortDate(signal.discontinued_date);
    return dateLabel ? `Discontinued ${dateLabel}` : "Discontinued";
  }, [signal.is_discontinued, signal.discontinued_date]);

  // ----- Source activity (subject or id) -----
  const sourceLabel = useMemo(() => {
    const activity = signal.source_activity;
    if (!activity) return null;
    if (typeof activity === "string") {
      return `From Activity #${activity.slice(0, 8)}`;
    }
    const subject = activity.subject || activity.title;
    if (subject) return `From ${subject}`;
    if (activity.id) return `From Activity #${String(activity.id).slice(0, 8)}`;
    return null;
  }, [signal.source_activity]);

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: isRejected ? "error.light" : "primary.light",
        borderRadius: 1.5,
        p: 1.5,
        bgcolor: isRejected ? "error.lighter" : "primary.lighter",
        transition: "border-color 0.15s, background-color 0.15s",
        opacity: isRejected ? 0.75 : 1,
      }}
    >
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        {/* Content */}
        <Stack spacing={0.75} flex={1} minWidth={0}>
          {/* ---- Header line: catalog label + strategic badges ---- */}
          <Stack
            direction="row"
            spacing={0.75}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
            sx={{ minWidth: 0 }}
          >
            <Typography
              variant="body2"
              fontWeight={600}
              sx={{
                textDecoration: isRejected ? "line-through" : "none",
                color: isRejected ? "text.disabled" : "text.primary",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                minWidth: 0,
                flex: "0 1 auto",
              }}
              title={catalogLabel}
            >
              {catalogLabel}
            </Typography>
            {isCompetitor && !isRejected && (
              <Chip
                label="Competitor"
                color="error"
                size="small"
                sx={{ fontSize: "0.6rem", height: 18 }}
              />
            )}
            {isIntegrationTarget && !isRejected && (
              <Chip
                label="Integration"
                color="info"
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.6rem", height: 18 }}
              />
            )}
          </Stack>

          {/* ---- Scope row: scope chip + (department name when applicable) ---- */}
          {(scopeLabel || departmentName) && (
            <Stack
              direction="row"
              spacing={0.5}
              alignItems="center"
              flexWrap="wrap"
              useFlexGap
            >
              {scopeLabel && (
                <Chip
                  label={scopeLabel}
                  size="small"
                  variant="outlined"
                  sx={{
                    fontSize: "0.62rem",
                    height: 18,
                    color: isRejected ? "text.disabled" : "text.secondary",
                  }}
                />
              )}
              {departmentName && signal.usage_scope === "DEPARTMENT" && (
                <Typography
                  variant="caption"
                  color={isRejected ? "text.disabled" : "text.secondary"}
                >
                  {departmentName}
                </Typography>
              )}
            </Stack>
          )}

          {/* ---- Lifecycle compact line ---- */}
          {lifecycleLine && (
            <Typography
              variant="caption"
              color={isRejected ? "text.disabled" : "text.secondary"}
              sx={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={signal.cost_description?.trim() || undefined}
            >
              {lifecycleLine}
            </Typography>
          )}

          {/* ---- Discontinuation badge ---- */}
          {discontinuationLabel && (
            <Typography
              variant="caption"
              color="error.dark"
              fontWeight={500}
              sx={{
                width: "fit-content",
                px: 0.75,
                py: 0.25,
                borderRadius: 0.5,
                bgcolor: "error.lighter",
                border: "1px dashed",
                borderColor: "error.light",
              }}
            >
              {discontinuationLabel}
            </Typography>
          )}

          {/* ---- Source activity line ---- */}
          {sourceLabel && (
            <Typography
              variant="caption"
              color="text.disabled"
              sx={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {sourceLabel}
            </Typography>
          )}

          {/* ---- Notes preview ---- */}
          {signal.notes?.trim() && (
            <Typography
              variant="caption"
              color={isRejected ? "text.disabled" : "text.secondary"}
              sx={{ fontStyle: "italic" }}
              title={signal.notes}
            >
              {truncate(signal.notes.trim(), 80)}
            </Typography>
          )}
        </Stack>

        {/* Actions — unchanged from prior implementation */}
        <Stack direction="row" spacing={0.5} alignItems="center" flexShrink={0}>
          <Button
            size="small"
            variant="outlined"
            color={isRejected ? "error" : "success"}
            onClick={() => onToggleStatus(signal._key)}
            startIcon={
              isRejected ? (
                <CloseCircleOutlined style={{ fontSize: 13 }} />
              ) : (
                <CheckCircleOutlined style={{ fontSize: 13 }} />
              )
            }
            sx={{ fontSize: "0.7rem", px: 1, py: 0.5 }}
          >
            {isRejected ? "Excluded" : "Include"}
          </Button>
          <IconButton
            size="small"
            onClick={() => onEdit(signal._key)}
            aria-label="Edit signal"
            sx={{
              color: "text.disabled",
              "&:hover": { color: "primary.main" },
            }}
          >
            <EditOutlined style={{ fontSize: 13 }} />
          </IconButton>
          <IconButton
            size="small"
            onClick={() => onRemove(signal._key)}
            aria-label="Remove signal"
            sx={{ color: "text.disabled", "&:hover": { color: "error.main" } }}
          >
            <DeleteOutlined style={{ fontSize: 13 }} />
          </IconButton>
        </Stack>
      </Stack>
    </Box>
  );
}

StagedTechStackCard.propTypes = {
  signal: PropTypes.shape({
    _key: PropTypes.string.isRequired,
    _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
    // Catalog anchor — object whole; UUID extracted at dispatch.
    tech_catalog_entry: PropTypes.shape({
      id: PropTypes.string,
      company_name: PropTypes.string,
      product_name: PropTypes.string,
      is_competitor: PropTypes.bool,
      is_integration_target: PropTypes.bool,
    }),
    // Scope axis
    usage_scope: PropTypes.oneOf(["TEAM", "DEPARTMENT", "COMPANY", "UNKNOWN"]),
    usage_department: PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.shape({ id: PropTypes.string, name: PropTypes.string }),
    ]),
    // Lifecycle
    usage_start_year: PropTypes.number,
    renewal_date: PropTypes.string,
    cost_description: PropTypes.string,
    is_discontinued: PropTypes.bool,
    discontinued_date: PropTypes.string,
    // Narrative
    notes: PropTypes.string,
    // Source — object whole or UUID string fallback
    source_activity: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
  }).isRequired,
  choices: PropTypes.object,
  onToggleStatus: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
};

// ==============================|| EMPTY STATE ||============================== //

function EmptyState() {
  return (
    <Stack spacing={1} alignItems="center" py={4}>
      <InboxOutlined style={{ fontSize: 28, color: "#bfbfbf" }} />
      <Typography variant="body2" color="text.disabled" textAlign="center">
        No tech stack signals staged yet.
        <br />
        Click &ldquo;Add Tech Stack&rdquo; to capture one.
      </Typography>
    </Stack>
  );
}

// ==============================|| TECH STACK SECTION ||============================== //

/**
 * TechStackSection
 *
 * @param {Array}    stagedSignals    - Staged tech stack signals managed by WizardSignalAdd
 * @param {Function} onAdd            - (payload: Object) => void
 * @param {Function} onToggleStatus   - (_key: string) => void
 * @param {Function} onEdit           - (_key: string) => void
 * @param {Function} onUpdate         - (_key: string, payload: Object) => void
 * @param {Function} onRemove         - (_key: string) => void
 * @param {string}   editingKey       - _key currently being edited (or null)
 * @param {Function} onCancelEdit     - () => void
 * @param {Object}   choices          - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {string}   accountId
 * @param {Function} onFormOpenChange - Notifies the wizard when inline form opens/closes
 */
export default function TechStackSection({
  stagedSignals,
  onAdd,
  onToggleStatus,
  onEdit,
  onUpdate,
  onRemove,
  editingKey,
  onCancelEdit,
  choices,
  choicesLoading,
  accountId,
  onFormOpenChange,
}) {
  const [formOpen, setFormOpen] = useState(false);

  const isEditMode = editingKey != null;
  const isFormVisible = formOpen || isEditMode;

  // Notify parent wizard when any form (create OR edit) is visible
  useEffect(() => {
    onFormOpenChange?.(isFormVisible);
  }, [isFormVisible, onFormOpenChange]);

  // Find the staged signal being edited — stable reference for initialValues
  const editingSignal = useMemo(
    () =>
      isEditMode
        ? (stagedSignals.find((s) => s._key === editingKey) ?? null)
        : null,
    [isEditMode, editingKey, stagedSignals],
  );

  // Pre-fill the inline form when entering edit mode
  const editInitialValues = useMemo(
    () =>
      editingSignal
        ? buildEditInitialValues("tech-stack", editingSignal)
        : null,
    [editingSignal],
  );

  const handleAdd = useCallback(
    (payload) => {
      onAdd(payload);
      setFormOpen(false);
    },
    [onAdd],
  );

  const handleUpdate = useCallback(
    (payload) => {
      if (editingKey) onUpdate(editingKey, payload);
    },
    [onUpdate, editingKey],
  );

  const handleCancel = useCallback(() => {
    if (isEditMode) {
      onCancelEdit?.();
    } else {
      setFormOpen(false);
    }
  }, [isEditMode, onCancelEdit]);

  const validatedCount = useMemo(
    () => stagedSignals.filter((s) => s._status === "VALIDATED").length,
    [stagedSignals],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Stack spacing={2}>
      {/* ---- Section header ---- */}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="subtitle1" fontWeight={600}>
            Tech Stack Signals
          </Typography>
          {stagedSignals.length > 0 && (
            <Chip
              label={`${validatedCount} / ${stagedSignals.length}`}
              size="small"
              color={validatedCount > 0 ? "primary" : "default"}
              sx={{ height: 20, fontSize: "0.68rem" }}
            />
          )}
        </Stack>

        {/* Add button — hidden when any form (create or edit) is open */}
        {!isFormVisible && (
          <Button
            size="small"
            variant="outlined"
            color="primary"
            startIcon={<PlusOutlined style={{ fontSize: 12 }} />}
            onClick={() => setFormOpen(true)}
          >
            Add Tech Stack
          </Button>
        )}
      </Stack>

      {/* ---- Staged signals list ---- */}
      {stagedSignals.length === 0 && !isFormVisible && <EmptyState />}

      {stagedSignals.length > 0 && (
        <Stack spacing={1}>
          {stagedSignals.map((signal) =>
            // In edit mode, the edited signal is replaced inline by the form
            isEditMode && signal._key === editingKey ? (
              <InlineTechStackForm
                key={signal._key}
                choices={choices}
                choicesLoading={choicesLoading}
                accountId={accountId}
                onAdd={handleUpdate}
                onCancel={handleCancel}
                initialValues={editInitialValues}
                submitLabel="Save changes"
              />
            ) : (
              <StagedTechStackCard
                key={signal._key}
                signal={signal}
                choices={choices}
                onToggleStatus={onToggleStatus}
                onEdit={onEdit}
                onRemove={onRemove}
              />
            ),
          )}
        </Stack>
      )}

      {/* ---- Divider before create form ---- */}
      {formOpen && stagedSignals.length > 0 && <Divider />}

      {/* ---- Inline form for CREATE (edit form is rendered inside the list above) ---- */}
      {formOpen && (
        <InlineTechStackForm
          choices={choices}
          choicesLoading={choicesLoading}
          accountId={accountId}
          onAdd={handleAdd}
          onCancel={handleCancel}
        />
      )}
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

TechStackSection.propTypes = {
  stagedSignals: PropTypes.arrayOf(
    PropTypes.shape({
      _key: PropTypes.string.isRequired,
      _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
      // Sprint TechStack staged shape — see file docstring.
      tech_catalog_entry: PropTypes.object,
      usage_scope: PropTypes.string,
      usage_department: PropTypes.oneOfType([
        PropTypes.string,
        PropTypes.object,
      ]),
      usage_start_year: PropTypes.number,
      renewal_date: PropTypes.string,
      cost_description: PropTypes.string,
      is_discontinued: PropTypes.bool,
      discontinued_date: PropTypes.string,
      notes: PropTypes.string,
      source_activity: PropTypes.oneOfType([
        PropTypes.string,
        PropTypes.object,
      ]),
      source_quote: PropTypes.string,
    }),
  ).isRequired,
  onAdd: PropTypes.func.isRequired,
  onToggleStatus: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onUpdate: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
  editingKey: PropTypes.string,
  onCancelEdit: PropTypes.func,
  onFormOpenChange: PropTypes.func,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
};
