// frontend/src/components/cards/signals/SignalClusterCard.jsx
/**
 * SignalClusterCard — list item for a signal cluster.
 *
 * A cluster is the aggregation of all signals (Pain or Objective)
 * sharing the same canonical_key on an account. This card is the
 * primary surface in the Qualification tab: it summarises the cluster
 * at a glance and opens the drill-down drawer on click.
 *
 * Type-agnostic by design — Pain and Objective render through the same
 * component. Branching is driven by `cluster.signal_type` (`pain` |
 * `objective`) to switch palette and to decide which stats appear in
 * the stats row.
 *
 * Visual hierarchy (top to bottom):
 *   1. Header    — type chip, priority bucket, canonical axes, archived
 *   2. Summary   — consolidated "most recent VALIDATED" text
 *   3. Alert     — "N signals need validation" when PENDING members exist
 *   4. Stats     — type-specific (Pain → impacts; Objective → scope/target)
 *   5. Type-specific extras — Pain: human_impacts chips
 *   6. Footer    — freshness badge + last confirmed date + DC indicator
 *
 * Interaction:
 *   - Whole card clickable (onClick) → opens drill-down drawer
 *   - Overflow menu (︙) stops propagation → archive / unarchive
 *   - Archived clusters render at opacity 0.6 with an "Archived" chip
 *
 * The component never calls the API directly — it emits onClick / onArchive /
 * onUnarchive callbacks. The parent owns the drawer state and the mutations.
 */

"use client";

import PropTypes from "prop-types";
import { useCallback, useMemo, useState } from "react";

// material-ui
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// ant-design icons
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import UndoOutlined from "@ant-design/icons/UndoOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";
import WarningOutlined from "@ant-design/icons/WarningOutlined";

// project imports
// project imports
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

// ==============================|| HELPERS ||============================== //

/**
 * Format an ISO date string to a short readable form (dd MMM yyyy).
 * Returns null for falsy input so the caller can conditionally render.
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
 * Truncate a string to max chars with ellipsis.
 * Used for metric chips where free-text values can be arbitrarily long
 * and need to fit a card preview line. The full value is exposed via
 * the chip's tooltip.
 */
function truncate(str, max = 40) {
  if (!str) return null;
  return str.length > max ? `${str.slice(0, max)}…` : str;
}

/**
 * Build the canonical display label for a TechStack cluster from its
 * tech_catalog_entry payload. Mirrors TechStackCard.getCatalogLabel —
 * kept local to avoid an extra cross-file import for what's a simple
 * concatenation.
 *
 *   { company_name: "Salesforce", product_name: "Sales Cloud" }
 *     → "Salesforce Sales Cloud"
 *   { company_name: "Notion", product_name: "Notion" }
 *     → "Notion"
 *
 * Defensive fallback to "Unknown tool" — a malformed cluster payload
 * should never crash the card.
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

// ==============================|| SIGNAL CLUSTER CARD ||============================== //

/**
 * SignalClusterCard
 *
 * @param {Object}   cluster        - Cluster payload from backend list endpoint
 * @param {Function} onClick        - (cluster) => void — open drill-down drawer
 * @param {Function} onArchive      - (cluster) => void — archive from menu
 * @param {Function} onUnarchive    - (cluster) => void — unarchive from menu
 */
export default function SignalClusterCard({
  cluster,
  onClick,
  onArchive,
  onUnarchive,
}) {
  // ==============================|| LOCAL STATE ||============================== //

  const [menuAnchor, setMenuAnchor] = useState(null);

  // ==============================|| TYPE BRANCHING ||============================== //

  /**
   * Resolve type once at the top — every downstream branch reads from
   * `isPain` / `isObjective` / `isTechStack` rather than re-checking
   * signal_type. Three types are clustered today; if a future signal_type
   * ships, the visual fallback ("Cluster" / default palette) renders
   * without crash.
   */
  const signalType = cluster.signal_type;
  const typeVisuals = resolveSignalTypeVisuals(signalType);
  const isPain = signalType === "pain";
  const isObjective = signalType === "objective";
  const isTechStack = signalType === "tech_stack";

  /**
   * Strategic flags from the TechStack catalog entry — only meaningful
   * when the cluster is a TechStack. Resolved here once for downstream
   * use in border emphasis, header chips, and the canonical chip palette.
   */
  const techCatalogEntry = isTechStack ? cluster.tech_catalog_entry : null;
  const isCompetitor = Boolean(techCatalogEntry?.is_competitor);
  const isIntegrationTarget = Boolean(techCatalogEntry?.is_integration_target);

  // ==============================|| DERIVED ||============================== //

  const isArchived = Boolean(cluster.is_archived);

  const freshness = resolveFreshness(cluster.freshness_status);
  const priority = resolvePriority(cluster.priority_bucket);

  const FreshnessIcon = freshness.icon;
  const PriorityIcon = priority.icon;

  // Pain-specific resolutions
  const maxImpactLevel = resolveImpactLevel(cluster.max_impact_level);

  // Objective-specific resolutions
  const maxScopeLevel = resolveScopeLevel(cluster.max_scope_level);
  const targetUrgency = useMemo(
    () =>
      resolveTargetDateUrgency(
        cluster.target_dates,
        cluster.has_target_date_soon,
      ),
    [cluster.target_dates, cluster.has_target_date_soon],
  );

  // TechStack-specific resolutions
  const scopeSummary = isTechStack ? cluster.scope_summary : null;
  const lifecycle = isTechStack ? cluster.lifecycle : null;
  const departmentsUsing = useMemo(() => {
    if (!isTechStack) return [];
    const list = scopeSummary?.departments_using;
    return Array.isArray(list) ? list : [];
  }, [isTechStack, scopeSummary]);

  /**
   * Related Pain clusters cross-referencing this tool — TechStack-only.
   * Capped to 3 visible; remainder collapses into a "+N more" chip.
   * Each entry carries { canonical_key, summary, priority_bucket,
   * confirmation_count } from the backend payload.
   */
  const relatedPainClustersPreview = useMemo(() => {
    if (!isTechStack) return { visible: [], remainder: 0 };
    const all = Array.isArray(cluster.related_pain_clusters)
      ? cluster.related_pain_clusters
      : [];
    const visible = all.slice(0, 3);
    return { visible, remainder: all.length - visible.length };
  }, [isTechStack, cluster.related_pain_clusters]);

  /**
   * Canonical text — type-aware:
   *   - Pain / Objective : "Operations × Time"   (what × dimension)
   *   - TechStack        : "Salesforce Sales Cloud"   (vendor product)
   *
   * Returns null when the source fields are missing so the chip is
   * suppressed entirely rather than rendered with placeholders.
   */
  const canonicalText = useMemo(() => {
    if (isTechStack) {
      return getCatalogLabel(techCatalogEntry);
    }
    if (!cluster.what_display || !cluster.dimension_display) return null;
    return `${cluster.what_display} × ${cluster.dimension_display}`;
  }, [
    isTechStack,
    techCatalogEntry,
    cluster.what_display,
    cluster.dimension_display,
  ]);

  const lastConfirmedDate = formatShortDate(cluster.last_confirmed_at);

  /**
   * Human impacts chips — Pain-only.
   * Capped to 3 visible entries so the card footprint stays bounded;
   * additional entries collapse into a "+N more" chip.
   *
   * For Objective, cluster.human_impacts is always [] (backend symmetry
   * — see _build_objective_cluster). The visible/remainder both end up
   * at zero, and the chip row is skipped in render.
   */
  const humanChips = useMemo(() => {
    const all = Array.isArray(cluster.human_impacts)
      ? cluster.human_impacts
      : [];
    const visible = all.slice(0, 3);
    const remainder = all.length - visible.length;
    return { visible, remainder };
  }, [cluster.human_impacts]);

  /**
   * Metrics preview chips — Pain-only.
   * Same capping strategy as human_impacts: 3 visible + a "+N more"
   * chip when there are extra metrics. Each metric is truncated for
   * the chip label; the full text is exposed via the chip tooltip.
   *
   * For Objective, cluster.metrics is always [] (backend symmetry).
   */
  const metricsPreview = useMemo(() => {
    const all = Array.isArray(cluster.metrics) ? cluster.metrics : [];
    const visible = all.slice(0, 3);
    const remainder = all.length - visible.length;
    return { visible, remainder };
  }, [cluster.metrics]);

  /**
   * Linked DC indicator — shown when the cluster references at least one
   * decision cycle. A simple count ("N DC") keeps the card readable —
   * the drawer shows full names on drill-down.
   */
  const linkedCyclesCount = Array.isArray(cluster.decision_cycle_ids)
    ? cluster.decision_cycle_ids.length
    : 0;

  /**
   * Border emphasis — drives the "weight" of the card border so a busy
   * list still highlights commercially relevant items at a glance.
   *
   * Branching (priority order, top wins):
   *   1. Archived              → divider (muted; visual de-emphasis wins)
   *   2. Pending members       → warning.light (universal — needs validation)
   *   3. TechStack competitor  → error.main (strong commercial signal,
   *                              priority over priority bucket: a
   *                              competitor cluster is always worth
   *                              noticing in the list, even if its
   *                              priority_score happens to be LOW)
   *   4. TechStack integration → info.main (partner signal, opportunity
   *                              for technical alignment)
   *   5. HIGH priority         → type-specific accent
   *                              (Pain=error.light, Obj=info.light,
   *                               TechStack=primary.light)
   *   6. MEDIUM priority       → warning.light (type-agnostic)
   *   7. default               → divider
   */
  const borderColor = useMemo(() => {
    if (isArchived) return "divider";
    if (cluster.has_pending_signals) return "warning.light";
    if (isTechStack && isCompetitor) return "error.main";
    if (isTechStack && isIntegrationTarget) return "info.main";
    if (cluster.priority_bucket === "HIGH") {
      if (isObjective) return "info.light";
      if (isTechStack) return "primary.light";
      return "error.light"; // Pain (default — first type clustered)
    }
    if (cluster.priority_bucket === "MEDIUM") return "warning.light";
    return "divider";
  }, [
    isArchived,
    isObjective,
    isTechStack,
    isCompetitor,
    isIntegrationTarget,
    cluster.has_pending_signals,
    cluster.priority_bucket,
  ]);

  /**
   * Border thickness — 2px for TechStack strategic flags so they
   * visually outweigh standard 1px borders on neighbouring cards.
   */
  const borderWidth =
    isTechStack && (isCompetitor || isIntegrationTarget) ? "2px" : "1px";

  // ==============================|| MENU HANDLERS ||============================== //

  const handleMenuOpen = useCallback((e) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  }, []);

  const handleMenuClose = useCallback((e) => {
    if (e?.stopPropagation) e.stopPropagation();
    setMenuAnchor(null);
  }, []);

  const handleArchive = useCallback(
    (e) => {
      e.stopPropagation();
      setMenuAnchor(null);
      onArchive?.(cluster);
    },
    [cluster, onArchive],
  );

  const handleUnarchive = useCallback(
    (e) => {
      e.stopPropagation();
      setMenuAnchor(null);
      onUnarchive?.(cluster);
    },
    [cluster, onUnarchive],
  );

  // ==============================|| CARD CLICK ||============================== //

  /**
   * Whole-card click opens the drawer. The overflow menu stops propagation
   * so archive/unarchive do not trigger the drawer.
   */
  const handleCardClick = useCallback(() => {
    onClick?.(cluster);
  }, [cluster, onClick]);

  /**
   * Keyboard accessibility — Enter and Space activate the card, matching
   * native button semantics without being a <button>.
   */
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onClick?.(cluster);
      }
    },
    [cluster, onClick],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      aria-label={`Open cluster ${canonicalText ?? cluster.canonical_key}`}
      sx={{
        border: `${borderWidth} solid`,
        borderColor,
        borderRadius: 1.5,
        p: 2,
        bgcolor: "background.paper",
        cursor: "pointer",
        opacity: isArchived ? 0.6 : 1,
        transition: "border-color 0.15s, box-shadow 0.15s, opacity 0.15s",
        "&:hover": {
          borderColor: isArchived ? "divider" : "primary.light",
          boxShadow: 1,
        },
        "&:focus-visible": {
          outline: "2px solid",
          outlineColor: "primary.main",
          outlineOffset: 2,
        },
      }}
    >
      {/* ==================== HEADER ==================== */}
      <Stack direction="row" spacing={1} alignItems="flex-start">
        {/* Left: chips + canonical + archived marker */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1, minWidth: 0 }}
        >
          {/* Type chip — colored per signal_type */}
          <Chip
            label={typeVisuals.label}
            color={typeVisuals.color}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />

          {/* Priority bucket */}
          <Tooltip
            title={`Priority score: ${cluster.priority_score ?? "—"}`}
            placement="top"
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

          {/* Canonical axes — colored per signal_type to match the type chip.
              For Pain/Objective this reads "Operations × Time"; for TechStack
              it reads "{vendor} {product}" — see canonicalText derivation. */}
          {canonicalText && (
            <Chip
              label={canonicalText}
              color={typeVisuals.color}
              variant="outlined"
              size="small"
              sx={{
                fontSize: "0.68rem",
                height: 20,
                fontWeight: isTechStack ? 500 : 400,
              }}
            />
          )}

          {/* TechStack strategic flags — competitor / integration target.
              Earn their own chips (in addition to border emphasis) so the
              rep can spot them mid-list without focusing on the card. */}
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

          {/* Archived marker */}
          {isArchived && (
            <Chip
              icon={<InboxOutlined style={{ fontSize: 11 }} />}
              label="Archived"
              size="small"
              sx={{ fontSize: "0.68rem", height: 20 }}
            />
          )}
        </Stack>

        {/* Right: overflow menu */}
        <IconButton
          size="small"
          onClick={handleMenuOpen}
          aria-label="Cluster actions"
          aria-controls={menuAnchor ? "cluster-action-menu" : undefined}
          aria-haspopup="true"
          aria-expanded={Boolean(menuAnchor)}
          sx={{ flexShrink: 0 }}
        >
          <MoreOutlined style={{ fontSize: 16 }} />
        </IconButton>

        <Menu
          id="cluster-action-menu"
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={handleMenuClose}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          transformOrigin={{ vertical: "top", horizontal: "right" }}
          // Prevent clicks on the menu itself from bubbling up to the card.
          slotProps={{
            paper: { onClick: (e) => e.stopPropagation() },
          }}
        >
          {!isArchived && (
            <MenuItem onClick={handleArchive} dense>
              <Stack direction="row" spacing={1} alignItems="center">
                <InboxOutlined style={{ fontSize: 14 }} />
                <span>Archive cluster</span>
              </Stack>
            </MenuItem>
          )}
          {isArchived && (
            <MenuItem onClick={handleUnarchive} dense>
              <Stack direction="row" spacing={1} alignItems="center">
                <UndoOutlined style={{ fontSize: 14 }} />
                <span>Unarchive cluster</span>
              </Stack>
            </MenuItem>
          )}
        </Menu>
      </Stack>

      {/* ==================== SUMMARY ==================== */}
      {cluster.summary && (
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{
            mt: 1.25,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {cluster.summary}
        </Typography>
      )}

      {/* ==================== PENDING ALERT ==================== */}
      {cluster.has_pending_signals && cluster.pending_count > 0 && (
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          sx={{
            mt: 1.25,
            py: 0.5,
            px: 1,
            bgcolor: "warning.lighter",
            borderRadius: 0.75,
            border: "1px dashed",
            borderColor: "warning.light",
          }}
        >
          <WarningOutlined style={{ fontSize: 12, color: "#faad14" }} />
          <Typography variant="caption" color="warning.dark" fontWeight={500}>
            {cluster.pending_count} signal
            {cluster.pending_count === 1 ? "" : "s"} need
            {cluster.pending_count === 1 ? "s" : ""} validation
          </Typography>
        </Stack>
      )}

      {/* ==================== STATS ROW (TYPE-SPECIFIC) ==================== */}
      {/*
        Stats are type-branched. Common atoms (distinct contacts,
        confirmation count) appear in both branches; type-specific atoms
        appear only in their branch. Keeping the two render paths side by
        side rather than computing a unified row keeps the intent legible.
      */}
      <Stack
        direction="row"
        spacing={2}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
        sx={{ mt: 1.5 }}
      >
        {/* Distinct contacts — universal across types.
            Tooltip text adapts per type for accurate phrasing. */}
        <Tooltip
          title={
            isObjective
              ? "Distinct contacts who set this objective"
              : isTechStack
                ? "Distinct contacts who mentioned this tool"
                : "Distinct contacts who confirmed this pain"
          }
        >
          <Stack direction="row" spacing={0.5} alignItems="center">
            <TeamOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            <Typography variant="caption" color="text.secondary">
              {cluster.distinct_contacts_count ?? 0}
            </Typography>
          </Stack>
        </Tooltip>

        {/* PAIN: impacted contacts (PainImpact at PERSONAL scope) */}
        {isPain && (
          <Tooltip title="Contacts personally impacted">
            <Stack direction="row" spacing={0.5} alignItems="center">
              <UserOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
              <Typography variant="caption" color="text.secondary">
                {cluster.impacted_contacts_count ?? 0}
              </Typography>
            </Stack>
          </Tooltip>
        )}

        {/* PAIN: max impact level */}
        {isPain && cluster.max_impact_level && (
          <Tooltip title="Highest observed impact level">
            <Chip
              label={maxImpactLevel.label}
              color={maxImpactLevel.color}
              size="small"
              variant="outlined"
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          </Tooltip>
        )}

        {/* OBJECTIVE: max scope level */}
        {isObjective && cluster.max_scope_level && (
          <Tooltip title="Highest observed scope level">
            <Chip
              label={maxScopeLevel.label}
              color={maxScopeLevel.color}
              size="small"
              variant="outlined"
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          </Tooltip>
        )}

        {/* OBJECTIVE: target date urgency badge */}
        {isObjective && targetUrgency && (
          <Tooltip
            title={
              targetUrgency.earliestDate
                ? `Earliest target: ${targetUrgency.earliestDate}`
                : "Target date"
            }
          >
            <Chip
              icon={<CalendarOutlined style={{ fontSize: 11 }} />}
              label={targetUrgency.label}
              color={targetUrgency.color}
              size="small"
              variant="outlined"
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          </Tooltip>
        )}

        {/* TECHSTACK: company-wide indicator (boolean badge — collapses
            individual department chips into a single broad-reach signal) */}
        {isTechStack && scopeSummary?.is_company_wide && (
          <Tooltip title="Used company-wide across multiple departments">
            <Chip
              label="Company-wide"
              color="success"
              size="small"
              variant="outlined"
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          </Tooltip>
        )}

        {/* TECHSTACK: renewal-soon urgency badge */}
        {isTechStack && cluster.has_renewal_soon && (
          <Tooltip title="Renewal date is within 90 days">
            <Chip
              icon={<CalendarOutlined style={{ fontSize: 11 }} />}
              label="Renewal soon"
              color="warning"
              size="small"
              variant="outlined"
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          </Tooltip>
        )}

        {/* TECHSTACK: discontinued badge — strong negative signal */}
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
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          </Tooltip>
        )}

        {/* Confirmation count — universal */}
        <Typography variant="caption" color="text.disabled">
          {cluster.confirmation_count ?? 0} confirmation
          {(cluster.confirmation_count ?? 0) === 1 ? "" : "s"}
        </Typography>
      </Stack>

      {/* ==================== HUMAN IMPACTS CHIPS — PAIN ONLY ==================== */}
      {isPain && humanChips.visible.length > 0 && (
        <Stack
          direction="row"
          spacing={0.5}
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 1 }}
        >
          {humanChips.visible.map((entry) => {
            const cfg = resolveHumanImpact(entry.type);
            return (
              <Chip
                key={entry.type}
                label={`${cfg.label} ×${entry.count}`}
                size="small"
                variant="outlined"
                sx={{
                  fontSize: "0.62rem",
                  height: 18,
                  color: "text.secondary",
                }}
              />
            );
          })}
          {humanChips.remainder > 0 && (
            <Chip
              label={`+${humanChips.remainder} more`}
              size="small"
              variant="outlined"
              sx={{
                fontSize: "0.62rem",
                height: 18,
                color: "text.disabled",
              }}
            />
          )}
        </Stack>
      )}

      {/* ==================== METRICS CHIPS — PAIN ONLY ==================== */}
      {/*
        Quantitative evidence preview. Each metric is free-text on the
        backend (e.g. "120k$/year", "15h/week", "3 FTE wasted on manual
        reconciliation"). Truncated to fit the card; full value in the
        tooltip. Drawer shows the complete list with no truncation.
      */}
      {isPain && metricsPreview.visible.length > 0 && (
        <Stack
          direction="row"
          spacing={0.5}
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 0.75 }}
        >
          {metricsPreview.visible.map((metric, idx) => (
            <Tooltip
              // Metrics are free-text — duplicates across a cluster are
              // legitimate (different parents may report identical
              // numbers). Index disambiguates while preserving order.
              // eslint-disable-next-line react/no-array-index-key
              key={`${idx}-${metric.slice(0, 16)}`}
              title={metric}
              placement="top"
            >
              <Chip
                label={truncate(metric, 40)}
                size="small"
                variant="outlined"
                sx={{
                  fontSize: "0.62rem",
                  height: 18,
                  color: "text.secondary",
                  // Italic to visually distinguish from human_impacts chips
                  // ("evidence" vs "feeling") on the same card.
                  fontStyle: "italic",
                }}
              />
            </Tooltip>
          ))}
          {metricsPreview.remainder > 0 && (
            <Chip
              label={`+${metricsPreview.remainder} more`}
              size="small"
              variant="outlined"
              sx={{
                fontSize: "0.62rem",
                height: 18,
                color: "text.disabled",
              }}
            />
          )}
        </Stack>
      )}

      {/* ==================== DEPARTMENTS USING — TECHSTACK ONLY ==================== */}
      {/*
        Compact list of departments using the tool. Skipped entirely when
        is_company_wide is true (the company-wide chip in the stats row
        already conveys the broader picture — listing every department
        would be noise). Capped to 3 chips + "+N more" remainder, mirror
        of the human_impacts / metrics caps for visual rhythm.
      */}
      {isTechStack &&
        !scopeSummary?.is_company_wide &&
        departmentsUsing.length > 0 && (
          <Stack
            direction="row"
            spacing={0.5}
            flexWrap="wrap"
            useFlexGap
            sx={{ mt: 1 }}
          >
            {departmentsUsing.slice(0, 3).map((dept) => {
              const cfg = resolveUsageScope("DEPARTMENT");
              return (
                <Chip
                  key={dept.id}
                  label={dept.name}
                  size="small"
                  color={cfg.color}
                  variant="outlined"
                  sx={{
                    fontSize: "0.62rem",
                    height: 18,
                    color: "text.secondary",
                  }}
                />
              );
            })}
            {departmentsUsing.length > 3 && (
              <Chip
                label={`+${departmentsUsing.length - 3} more`}
                size="small"
                variant="outlined"
                sx={{
                  fontSize: "0.62rem",
                  height: 18,
                  color: "text.disabled",
                }}
              />
            )}
          </Stack>
        )}

      {/* ==================== RELATED PAIN CLUSTERS — TECHSTACK ONLY ==================== */}
      {/*
        Mini-list of Pain clusters cross-referencing this tool. Strong
        commercial cue: a competitor tool with 3 related Pain clusters
        on the same account is a textbook displacement opportunity.
        Capped to 3 visible + "+N more". Each chip surfaces the Pain
        cluster's summary truncated; the drawer shows full content.
      */}
      {isTechStack && relatedPainClustersPreview.visible.length > 0 && (
        <Stack
          direction="row"
          spacing={0.5}
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 0.75 }}
        >
          {relatedPainClustersPreview.visible.map((painCluster) => (
            <Tooltip
              key={painCluster.canonical_key}
              title={painCluster.summary || "Related Pain"}
              placement="top"
            >
              <Chip
                label={`Pain · ${truncate(painCluster.summary, 30) || painCluster.canonical_key}`}
                size="small"
                color="error"
                variant="outlined"
                sx={{
                  fontSize: "0.62rem",
                  height: 18,
                  fontStyle: "italic",
                }}
              />
            </Tooltip>
          ))}
          {relatedPainClustersPreview.remainder > 0 && (
            <Chip
              label={`+${relatedPainClustersPreview.remainder} more pain${relatedPainClustersPreview.remainder === 1 ? "" : "s"}`}
              size="small"
              variant="outlined"
              sx={{
                fontSize: "0.62rem",
                height: 18,
                color: "text.disabled",
              }}
            />
          )}
        </Stack>
      )}

      {/* ==================== FOOTER ==================== */}
      <Divider sx={{ mt: 1.5, mb: 1 }} />

      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
        spacing={1}
      >
        {/* Left: freshness badge + last confirmed */}
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <Tooltip title={freshness.helperText}>
            <Chip
              icon={<FreshnessIcon style={{ fontSize: 11 }} />}
              label={freshness.label}
              color={freshness.color}
              size="small"
              variant="outlined"
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          </Tooltip>

          {lastConfirmedDate && (
            <Typography variant="caption" color="text.disabled">
              Last confirmed {lastConfirmedDate}
            </Typography>
          )}

          {freshness.cta && !isArchived && (
            <Typography
              variant="caption"
              color={freshness.color}
              fontWeight={500}
              sx={{ fontStyle: "italic" }}
            >
              · {freshness.cta}
            </Typography>
          )}
        </Stack>

        {/* Right: linked DC count */}
        {linkedCyclesCount > 0 && (
          <Tooltip title="Linked decision cycles">
            <Typography variant="caption" color="text.disabled">
              {linkedCyclesCount} DC
              {linkedCyclesCount === 1 ? "" : "s"}
            </Typography>
          </Tooltip>
        )}
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

SignalClusterCard.propTypes = {
  cluster: PropTypes.shape({
    // Identity
    canonical_key: PropTypes.string.isRequired,
    signal_type: PropTypes.string,
    what: PropTypes.string,
    what_display: PropTypes.string,
    dimension: PropTypes.string,
    dimension_display: PropTypes.string,
    summary: PropTypes.string,

    // Status
    status: PropTypes.string,
    has_pending_signals: PropTypes.bool,
    pending_count: PropTypes.number,

    // Stats — common
    confirmation_count: PropTypes.number,
    distinct_contacts_count: PropTypes.number,

    // Stats — Pain-specific
    impacted_contacts_count: PropTypes.number,
    max_impact_level: PropTypes.string,
    human_impacts: PropTypes.arrayOf(
      PropTypes.shape({
        type: PropTypes.string.isRequired,
        count: PropTypes.number.isRequired,
      }),
    ),
    metrics: PropTypes.arrayOf(PropTypes.string),

    // Stats — Objective-specific
    max_scope_level: PropTypes.string,
    target_dates: PropTypes.arrayOf(PropTypes.string),
    has_target_date_soon: PropTypes.bool,

    // Stats — TechStack-specific
    tech_catalog_entry: PropTypes.shape({
      id: PropTypes.string,
      company_name: PropTypes.string,
      product_name: PropTypes.string,
      is_competitor: PropTypes.bool,
      is_integration_target: PropTypes.bool,
    }),
    lifecycle: PropTypes.shape({
      usage_start_year: PropTypes.number,
      renewal_date: PropTypes.string,
      cost_description: PropTypes.string,
      is_discontinued: PropTypes.bool,
      discontinued_date: PropTypes.string,
    }),
    scope_summary: PropTypes.shape({
      is_company_wide: PropTypes.bool,
      departments_using: PropTypes.arrayOf(
        PropTypes.shape({
          id: PropTypes.string.isRequired,
          name: PropTypes.string.isRequired,
        }),
      ),
      summary_text: PropTypes.string,
    }),
    has_renewal_soon: PropTypes.bool,
    related_pain_clusters: PropTypes.arrayOf(
      PropTypes.shape({
        canonical_key: PropTypes.string.isRequired,
        summary: PropTypes.string,
        priority_bucket: PropTypes.string,
        confirmation_count: PropTypes.number,
      }),
    ),

    // Lifecycle
    first_observed_at: PropTypes.string,
    last_confirmed_at: PropTypes.string,
    freshness_status: PropTypes.string,

    // Priority
    priority_score: PropTypes.number,
    priority_bucket: PropTypes.string,

    // Linking
    decision_cycle_ids: PropTypes.arrayOf(PropTypes.string),
    campaign_ids: PropTypes.arrayOf(PropTypes.string),

    // Archival
    is_archived: PropTypes.bool,
  }).isRequired,

  onClick: PropTypes.func.isRequired,
  onArchive: PropTypes.func.isRequired,
  onUnarchive: PropTypes.func.isRequired,
};
