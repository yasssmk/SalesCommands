// frontend/src/components/cards/signals/SignalClusterCard.jsx
/**
 * SignalClusterCard — list item for a Pain signal cluster.
 *
 * A cluster is the aggregation of all PainSignals sharing the same
 * canonical_key on an account. This card is the primary surface in the
 * new Pain tab: it summarises the cluster at a glance and opens the
 * drill-down drawer on click.
 *
 * Visual hierarchy (top to bottom):
 *   1. Header    — type chip, priority bucket, canonical axes, created date
 *   2. Summary   — consolidated "most recent VALIDATED" text
 *   3. Alert     — "N signals need validation" when PENDING members exist
 *   4. Stats     — contacts count, impacted count, max level, metrics
 *   5. Human     — aggregated human impact chips ("FRUSTRATION ×3", ...)
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
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import UndoOutlined from "@ant-design/icons/UndoOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";
import WarningOutlined from "@ant-design/icons/WarningOutlined";

// project imports
import {
  resolveFreshness,
  resolveHumanImpact,
  resolveImpactLevel,
  resolvePriority,
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
 * Used for the summary line (3-line clamp handled in CSS) and metric chips.
 */
function truncate(str, max = 140) {
  if (!str) return null;
  return str.length > max ? `${str.slice(0, max)}…` : str;
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

  // ==============================|| DERIVED ||============================== //

  const isArchived = Boolean(cluster.is_archived);

  const freshness = resolveFreshness(cluster.freshness_status);
  const priority = resolvePriority(cluster.priority_bucket);
  const maxLevel = resolveImpactLevel(cluster.max_impact_level);

  const FreshnessIcon = freshness.icon;
  const PriorityIcon = priority.icon;

  /** Canonical axes label — "Operations × Time" */
  const canonicalText = useMemo(() => {
    if (!cluster.what_display || !cluster.dimension_display) return null;
    return `${cluster.what_display} × ${cluster.dimension_display}`;
  }, [cluster.what_display, cluster.dimension_display]);

  const lastConfirmedDate = formatShortDate(cluster.last_confirmed_at);

  /**
   * Human impacts chips — "FRUSTRATION ×3, OVERLOAD ×1".
   * Capped to 3 visible entries so the card footprint stays bounded;
   * additional entries collapse into a "+N more" chip.
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
   * Linked DC indicator — shown when the cluster references at least one
   * decision cycle. A simple count ("N DC") keeps the card readable —
   * the drawer shows full names on drill-down.
   */
  const linkedCyclesCount = Array.isArray(cluster.decision_cycle_ids)
    ? cluster.decision_cycle_ids.length
    : 0;

  /**
   * Border emphasis — cluster priority drives the "weight" of the card
   * border so a busy list still highlights HIGH items at a glance.
   * PENDING signals push the border to warning.light regardless of
   * priority to mirror PainCard's existing convention.
   */
  const borderColor = useMemo(() => {
    if (isArchived) return "divider";
    if (cluster.has_pending_signals) return "warning.light";
    if (cluster.priority_bucket === "HIGH") return "error.light";
    if (cluster.priority_bucket === "MEDIUM") return "warning.light";
    return "divider";
  }, [isArchived, cluster.has_pending_signals, cluster.priority_bucket]);

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
        border: "1px solid",
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
        {/* Left: chips + canonical + date */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1, minWidth: 0 }}
        >
          <Chip
            label="Pain"
            color="error"
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

          {/* Canonical axes */}
          {canonicalText && (
            <Chip
              label={canonicalText}
              color="error"
              variant="outlined"
              size="small"
              sx={{ fontSize: "0.68rem", height: 20 }}
            />
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

      {/* ==================== STATS ROW ==================== */}
      <Stack
        direction="row"
        spacing={2}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
        sx={{ mt: 1.5 }}
      >
        {/* Distinct contacts (confirmation breadth) */}
        <Tooltip title="Distinct contacts who confirmed this pain">
          <Stack direction="row" spacing={0.5} alignItems="center">
            <TeamOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            <Typography variant="caption" color="text.secondary">
              {cluster.distinct_contacts_count ?? 0}
            </Typography>
          </Stack>
        </Tooltip>

        {/* Impacted contacts */}
        <Tooltip title="Contacts personally impacted">
          <Stack direction="row" spacing={0.5} alignItems="center">
            <UserOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            <Typography variant="caption" color="text.secondary">
              {cluster.impacted_contacts_count ?? 0}
            </Typography>
          </Stack>
        </Tooltip>

        {/* Max impact level */}
        {cluster.max_impact_level && (
          <Tooltip title="Highest observed impact level">
            <Chip
              label={maxLevel.label}
              color={maxLevel.color}
              size="small"
              variant="outlined"
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          </Tooltip>
        )}

        {/* Confirmation count */}
        <Typography variant="caption" color="text.disabled">
          {cluster.confirmation_count ?? 0} confirmation
          {(cluster.confirmation_count ?? 0) === 1 ? "" : "s"}
        </Typography>
      </Stack>

      {/* ==================== HUMAN IMPACTS CHIPS ==================== */}
      {humanChips.visible.length > 0 && (
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

    // Stats
    confirmation_count: PropTypes.number,
    distinct_contacts_count: PropTypes.number,
    impacted_contacts_count: PropTypes.number,
    max_impact_level: PropTypes.string,

    // Lifecycle
    first_observed_at: PropTypes.string,
    last_confirmed_at: PropTypes.string,
    freshness_status: PropTypes.string,

    // Priority
    priority_score: PropTypes.number,
    priority_bucket: PropTypes.string,

    // Impacts aggregation
    human_impacts: PropTypes.arrayOf(
      PropTypes.shape({
        type: PropTypes.string.isRequired,
        count: PropTypes.number.isRequired,
      }),
    ),
    metrics: PropTypes.arrayOf(PropTypes.string),

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
