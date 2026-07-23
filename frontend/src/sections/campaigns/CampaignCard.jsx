// frontend/src/sections/campaigns/CampaignCard.jsx

import PropTypes from "prop-types";
import { useRouter } from "next/navigation";

// material-ui
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

// project imports
import {
  CAMPAIGN_TYPE_LABELS,
  getCampaignScheduleLine,
} from "api/campaigns/campaigns";
// Reuse the shared queue-gradient mechanic for the "X left to contact" framing —
// the same pure helper queueGradient wraps. Imported directly (not via
// ProgressBlock) so the card does not pull Home's React module graph into its
// bundle; no reinvented remaining calc.
import { goalGradient } from "sections/home/utils/goalGradient";

// icons
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import AimOutlined from "@ant-design/icons/AimOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";

// ==============================|| TARGET PROGRESS — PER STATUS ||============================== //

// Per-status presentation of the OUTBOUND target-progress bar. A config map,
// not scattered conditionals: each entry gives the bar `color` and how `fill`
// (0-100) and `label` derive from the computed model { pct, remaining }.
// The total===0 ("No targets yet") and null (no bar) cases are handled BEFORE
// this map, so entries here only run when there are targets to show.
const TARGET_PROGRESS_BY_STATUS = {
  DRAFT: { color: "secondary", fill: () => 0, label: () => "Drafted" },
  ACTIVE: {
    color: "primary",
    fill: (m) => m.pct,
    label: (m) => `${m.remaining} left to contact`,
  },
  PAUSED: { color: "warning", fill: (m) => m.pct, label: (m) => `${m.pct}% Paused` },
  // COMPLETED shows the REAL progress, not a forced 100%: a campaign can be
  // completed without every target contacted, and the figure must be honest.
  COMPLETED: { color: "success", fill: (m) => m.pct, label: (m) => `${m.pct}% completed` },
  CANCELLED: { color: "error", fill: (m) => m.pct, label: () => "Cancelled" },
};

// ==============================|| CAMPAIGN CARD ||============================== //

/**
 * Campaign Card Component
 *
 * Displays a campaign as a card with:
 * - Name and campaign type (Outbound/Targeted)
 * - Status badge
 * - Activity progress bar
 * - Objective progress
 * - Date range
 * - Action buttons
 */
export default function CampaignCard({
  campaign,
  onOpen,
  onDelete,
  // Selection props
  selected = false,
  onSelect,
  selectionMode = false,
}) {
  const router = useRouter();
  const theme = useTheme();

  // ==============================|| DERIVED VALUES ||============================== //

  const isOutbound = campaign.campaign_type === "OUTBOUND";
  const isTargeted = campaign.campaign_type === "TARGETED";

  // Status now reads from the real date fields (planned_*/actual_*) via a
  // status→date rule, replacing the corner status badge and the old
  // start_date/end_date alias that no serializer emits.
  const schedule = getCampaignScheduleLine(campaign);

  // Attribution — owner + team, and executor + team only when the executor is a
  // distinct person (executor is null when it defaults to the owner, so that
  // line would be redundant).
  const owner = campaign.owner;
  const executor =
    campaign.executor && campaign.executor.id !== campaign.owner?.id
      ? campaign.executor
      : null;

  // ==============================|| HANDLERS ||============================== //

  const handleCardClick = () => {
    // Don't navigate if in selection mode
    if (selectionMode) return;
    onOpen?.(campaign);
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    onDelete?.(campaign);
  };

  const handleSelect = (event) => {
    event.stopPropagation();
    onSelect?.(campaign.id);
  };

  // ==============================|| TARGET PROGRESS BAR (OUTBOUND) ||============================== //

  // Raw counts from the 5c payload (targets_total / targets_worked). Called only
  // for non-TARGETED cards (the JSX gates on isTargeted). Order matters:
  //   - total == null/undefined → not annotated (e.g. detail view) → no bar.
  //   - total === 0 → "No targets yet", no fill — checked BEFORE the status map.
  //   - otherwise → per-status color/fill/label from TARGET_PROGRESS_BY_STATUS,
  //     with pct/remaining from the queue gradient (noun 'contacts').
  const renderTargetProgress = () => {
    const total = campaign.targets_total;
    if (total == null) return null; // null ≠ 0: render nothing

    const cfg = TARGET_PROGRESS_BY_STATUS[campaign.status];
    if (!cfg) return null;

    const empty = total === 0;
    const g = empty
      ? null
      : goalGradient(campaign.targets_worked ?? 0, total, {
          framing: "queue",
          noun: "contacts",
        });
    const model = g
      ? { pct: g.pct, remaining: g.remaining }
      : { pct: 0, remaining: 0 };

    const value = empty ? 0 : cfg.fill(model);
    const label = empty ? "No targets yet" : cfg.label(model);
    // The %/label text carries the status colour too (not just the bar) —
    // COMPLETED→success, PAUSED→warning, etc. The empty state stays neutral.
    const labelColor = empty ? "text.secondary" : `${cfg.color}.main`;

    return (
      <Box sx={{ mb: 1.5 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          mb={0.5}
        >
          <Typography variant="caption" color="text.secondary">
            Progress
          </Typography>
          <Typography variant="caption" color={labelColor} fontWeight={500}>
            {label}
          </Typography>
        </Stack>
        {/* Mirrors TerritoryCard's coverage bar geometry (height 6 / radius 3 /
            grey track); color is the per-status palette key. */}
        <LinearProgress
          variant="determinate"
          value={value}
          color={cfg.color}
          sx={{
            height: 6,
            borderRadius: 3,
            bgcolor: theme.palette.grey[200],
            "& .MuiLinearProgress-bar": { borderRadius: 3 },
          }}
        />
      </Box>
    );
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Card
      elevation={0}
      onClick={handleCardClick}
      sx={{
        position: "relative",
        border: "1px solid",
        borderColor: selected ? "error.main" : "divider",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        transition: "all 0.2s ease-in-out",
        cursor: selectionMode ? "default" : "pointer",
        bgcolor: selected ? "error.lighter" : "background.paper",
        "&:hover": {
          borderColor: selectionMode ? "divider" : "primary.main",
          boxShadow: selectionMode ? "none" : "0 4px 12px rgba(0,0,0,0.08)",
        },
        // The delete reveals on hover for non-protected cards. Status is no
        // longer a corner occupant (it now reads from the date line in the
        // body), so the corner at rest is empty — same as the territory card.
        "&:hover .gtm-card-delete": { opacity: 1 },
        "&:active": {
          transform: selectionMode ? "none" : "scale(0.99)",
        },
      }}
    >
      <CardContent
        sx={{ flexGrow: 1, display: "flex", flexDirection: "column" }}
      >
        {/* Header: Icon + Name + Status */}
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="flex-start"
          mb={2}
        >
          <Stack
            direction="row"
            spacing={1.5}
            alignItems="center"
            sx={{ minWidth: 0 }}
          >
            {/* Family Icon */}
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: 1,
                bgcolor: isOutbound ? "primary.lighter" : "warning.lighter",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              {isOutbound ? (
                <AimOutlined
                  style={{ fontSize: 20, color: theme.palette.primary.main }}
                />
              ) : (
                <ThunderboltOutlined
                  style={{ fontSize: 20, color: theme.palette.warning.main }}
                />
              )}
            </Box>

            {/* Name + Family chip */}
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h5" fontWeight={600} noWrap>
                {campaign.name}
              </Typography>
              <Chip
                label={
                  CAMPAIGN_TYPE_LABELS[campaign.campaign_type] ||
                  campaign.campaign_type
                }
                size="small"
                color={isOutbound ? "primary" : "warning"}
                variant="outlined"
                sx={{ mt: 0.5, height: 20, fontSize: "0.7rem" }}
              />
            </Box>
          </Stack>

        </Stack>

        {/* Description */}
        {campaign.description && (
          <Typography
            variant="body2"
            color="text.secondary"
            mb={2}
            sx={{
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {campaign.description}
          </Typography>
        )}

        {/* Accounts count */}
        <Box sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="baseline">
            <Typography variant="h2" component="div" fontWeight={600}>
              {campaign.accounts_count}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              accounts
            </Typography>
          </Stack>
        </Box>

        {/* Two stacked bars — OUTBOUND only; TARGETED shows neither (no bar at
            all, per the final decision).
            Top: the per-status Progress bar (5c targets_total / targets_worked).
            Bottom: the Objective bar — an EMPTY neutral placeholder that
            reserves the row for real objective data in S8. It carries NO data
            and must NOT reuse the progress figures (that would duplicate the
            Progress bar). */}
        {!isTargeted && (
          <>
            {renderTargetProgress()}

            <Box sx={{ mb: 1.5 }}>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                mb={0.5}
              >
                <Typography variant="caption" color="text.secondary">
                  Objective
                </Typography>
                <Typography variant="caption" color="text.disabled">
                  —
                </Typography>
              </Stack>
              <Box
                sx={{
                  height: 6,
                  borderRadius: 3,
                  bgcolor: "divider",
                  opacity: 0.5,
                }}
              />
            </Box>
          </>
        )}

        {/* Meta: schedule + attribution (owner + team, executor + team).
            Pinned to the bottom (mt:auto in the flex-column CardContent) so the
            footer aligns across cards whatever the middle height — OUTBOUND
            (two bars) and TARGETED (no bars) land on the same line. */}
        <Stack spacing={0.5} sx={{ mt: "auto", pt: 1.5 }}>
          {/* Schedule — status→date line; warning tone once the end has passed */}
          <Stack direction="row" spacing={1} alignItems="center">
            <CalendarOutlined
              style={{ fontSize: 12, color: theme.palette.text.secondary }}
            />
            <Typography
              variant="caption"
              sx={{
                color:
                  schedule.tone === "warning" ? "warning.main" : "text.secondary",
                fontWeight: schedule.tone === "warning" ? 500 : 400,
              }}
            >
              {schedule.text}
            </Typography>
          </Stack>

          {/* Owner attribution — "Owner: Name — TEAM" */}
          {owner?.full_name && (
            <Stack direction="row" spacing={1} alignItems="center">
              <UserOutlined
                style={{ fontSize: 12, color: theme.palette.text.secondary }}
              />
              <Typography variant="caption" color="text.secondary" noWrap>
                Owner: {owner.full_name}
                {campaign.owner_team?.name ? ` — ${campaign.owner_team.name}` : ""}
              </Typography>
            </Stack>
          )}

          {/* Executor attribution — only when a distinct executor is set */}
          {executor?.full_name && (
            <Stack direction="row" spacing={1} alignItems="center">
              <TeamOutlined
                style={{ fontSize: 12, color: theme.palette.text.secondary }}
              />
              <Typography variant="caption" color="text.secondary" noWrap>
                Executor: {executor.full_name}
                {campaign.executor_team?.name
                  ? ` — ${campaign.executor_team.name}`
                  : ""}
              </Typography>
            </Stack>
          )}
        </Stack>
      </CardContent>

      {/* Top-right corner — exclusive state machine (non-protected cards only):
          exactly one element at a time. Selection mode shows the checkbox;
          otherwise the individual delete reveals on hover (replacing the status
          via the shared :hover rule above). TARGETED campaigns are protected:
          no checkbox, no delete — their status stays in the header always. */}
      {!isTargeted && (
        selectionMode ? (
          <Box sx={{ position: "absolute", top: 8, right: 8, zIndex: 1 }}>
            <Checkbox
              checked={selected}
              onChange={handleSelect}
              onClick={(e) => e.stopPropagation()}
              size="small"
              sx={{
                bgcolor: "background.paper",
                borderRadius: 1,
                "&:hover": { bgcolor: "background.paper" },
              }}
            />
          </Box>
        ) : (
          <Box
            className="gtm-card-delete"
            sx={{
              position: "absolute",
              top: 8,
              right: 8,
              zIndex: 1,
              opacity: 0,
              transition: "opacity 0.2s ease-in-out",
            }}
          >
            <Tooltip title="Delete">
              <IconButton
                size="small"
                color="error"
                onClick={handleDelete}
                sx={{ bgcolor: "error.lighter", "&:hover": { bgcolor: "error.light" } }}
              >
                <DeleteOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        )
      )}
    </Card>
  );
}

// ==============================|| PROP TYPES ||============================== //

CampaignCard.propTypes = {
  campaign: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    campaign_type: PropTypes.oneOf(["OUTBOUND", "TARGETED"]).isRequired,
    status: PropTypes.string.isRequired,
    description: PropTypes.string,
    accounts_count: PropTypes.number,
    // Target progress (5c). Raw counts; null on non-annotated views.
    targets_total: PropTypes.number,
    targets_worked: PropTypes.number,
    // Real date fields (no start_date/end_date alias).
    planned_start_date: PropTypes.string,
    planned_end_date: PropTypes.string,
    actual_start_date: PropTypes.string,
    actual_end_date: PropTypes.string,
    // Attribution.
    owner: PropTypes.shape({ id: PropTypes.string, full_name: PropTypes.string }),
    owner_team: PropTypes.shape({ name: PropTypes.string }),
    executor: PropTypes.shape({ id: PropTypes.string, full_name: PropTypes.string }),
    executor_team: PropTypes.shape({ name: PropTypes.string }),
  }).isRequired,
  onOpen: PropTypes.func,
  onDelete: PropTypes.func,
  // Selection props
  selected: PropTypes.bool,
  onSelect: PropTypes.func,
  selectionMode: PropTypes.bool,
};
