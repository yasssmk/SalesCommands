// frontend/src/sections/campaigns/CampaignCard.jsx

import PropTypes from "prop-types";
import { useRouter } from "next/navigation";

// material-ui
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

// project imports
import CampaignStatusBadge from "sections/campaigns/CampaignStatusBadge";
import {
  CAMPAIGN_TYPE_LABELS,
  OBJECTIVE_TYPE_LABELS,
  getCampaignProgress,
  getObjectiveProgress,
} from "api/campaigns/campaigns";

// icons
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import AimOutlined from "@ant-design/icons/AimOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";

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
export default function CampaignCard({ campaign, onOpen, onDelete }) {
  const router = useRouter();
  const theme = useTheme();

  // ==============================|| DERIVED VALUES ||============================== //

  const isOutbound = campaign.campaign_type === "OUTBOUND";
  const activityProgress = getCampaignProgress(campaign);
  const objectiveProgress = getObjectiveProgress(campaign);
  const isOverdue =
    ["ACTIVE", "PAUSED"].includes(campaign.status) &&
    campaign.end_date &&
    new Date(campaign.end_date) < new Date();

  // ==============================|| HANDLERS ||============================== //

  const handleCardClick = () => {
    onOpen?.(campaign);
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    onDelete?.(campaign);
  };

  // ==============================|| HELPERS ||============================== //

  /**
   * Format date range for display
   */
  const formatDateRange = () => {
    if (!campaign.start_date && !campaign.end_date) return "No dates set";

    const formatDate = (dateStr) => {
      if (!dateStr) return null;
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    };

    const start = formatDate(campaign.start_date);
    const end = formatDate(campaign.end_date);

    if (start && end) return `${start} → ${end}`;
    if (start) return `From ${start}`;
    return "";
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Card
      elevation={0}
      onClick={handleCardClick}
      sx={{
        position: "relative",
        border: "1px solid",
        borderColor: "divider",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        transition: "all 0.2s ease-in-out",
        cursor: "pointer",
        "&:hover": {
          borderColor: "primary.main",
          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
        },
        "&:hover .gtm-card-delete": { opacity: 1 },
        "&:active": {
          transform: "scale(0.99)",
        },
      }}
    >
      <CardContent sx={{ flexGrow: 1 }}>
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

          {/* Status Badge + Overdue */}
          <Stack direction="row" spacing={0.5} alignItems="center">
            <CampaignStatusBadge status={campaign.status} />
            {isOverdue && (
              <Chip
                label="Overdue"
                size="small"
                color="error"
                sx={{ height: 20, fontSize: "0.7rem", fontWeight: 600 }}
              />
            )}
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

        {/* Activity Progress */}
        <Box sx={{ mb: 2 }}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            mb={0.5}
          >
            <Typography variant="caption" color="text.secondary">
              Activities
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {campaign.activities_completed}/{campaign.activities_total} (
              {activityProgress}%)
            </Typography>
          </Stack>
          <LinearProgress
            variant="determinate"
            value={activityProgress}
            sx={{
              height: 6,
              borderRadius: 3,
              bgcolor: theme.palette.grey[200],
              "& .MuiLinearProgress-bar": {
                borderRadius: 3,
              },
            }}
          />
        </Box>

        {/* Objective Progress */}
        {campaign.objective_type && (
          <Box sx={{ mb: 1.5 }}>
            <Stack
              direction="row"
              justifyContent="space-between"
              alignItems="center"
              mb={0.5}
            >
              <Typography variant="caption" color="text.secondary">
                {OBJECTIVE_TYPE_LABELS[campaign.objective_type] ||
                  campaign.objective_type}
              </Typography>
              <Typography
                variant="caption"
                fontWeight={600}
                color={
                  objectiveProgress >= 100 ? "success.main" : "text.primary"
                }
              >
                {campaign.objective_current}/{campaign.objective_target}
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={objectiveProgress}
              color={objectiveProgress >= 100 ? "success" : "primary"}
              sx={{
                height: 4,
                borderRadius: 2,
                bgcolor: theme.palette.grey[200],
                "& .MuiLinearProgress-bar": {
                  borderRadius: 2,
                },
              }}
            />
          </Box>
        )}

        {/* Meta: Dates + Sequence + Members */}
        <Stack spacing={0.5} mt={1.5}>
          {/* Dates */}
          <Stack direction="row" spacing={1} alignItems="center">
            <CalendarOutlined
              style={{ fontSize: 12, color: theme.palette.text.secondary }}
            />
            <Typography
              variant="caption"
              sx={{
                color: isOverdue ? "error.main" : "text.secondary",
                fontWeight: isOverdue ? 500 : 400,
              }}
            >
              {formatDateRange()}
            </Typography>
          </Stack>

          {/* Sequence type (prospection only) */}
          {campaign.sequence_type && (
            <Typography variant="caption" color="text.secondary">
              Sequence:{" "}
              {CAMPAIGN_TYPE_LABELS[campaign.sequence_type] ||
                campaign.sequence_type}
            </Typography>
          )}

          {/* Members count */}
          {campaign.members && campaign.members.length > 0 && (
            <Stack direction="row" spacing={1} alignItems="center">
              <TeamOutlined
                style={{ fontSize: 12, color: theme.palette.text.secondary }}
              />
              <Typography variant="caption" color="text.secondary">
                {campaign.members.length} member
                {campaign.members.length > 1 ? "s" : ""}
              </Typography>
            </Stack>
          )}
        </Stack>
      </CardContent>

      {/* Hover-reveal individual delete — top-right. Commit 4 will share this
          corner with the status icon and the multi-select checkbox
          (priority: normal -> status, hover -> delete, selection -> checkbox). */}
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
    sequence_type: PropTypes.string,
    start_date: PropTypes.string,
    end_date: PropTypes.string,
    accounts_count: PropTypes.number,
    activities_total: PropTypes.number,
    activities_completed: PropTypes.number,
    objective_type: PropTypes.string,
    objective_target: PropTypes.number,
    objective_current: PropTypes.number,
    members: PropTypes.array,
  }).isRequired,
  onOpen: PropTypes.func,
  onDelete: PropTypes.func,
};
