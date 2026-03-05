// frontend/src/sections/campaigns/workspace/CampaignHeader.jsx
/**
 * Campaign Header — Hook version for WorkspaceLayout.
 *
 * Returns layout props:
 *   { avatar, title, chips, infoItems, headerActions }
 *
 * Usage in workspace/index.jsx:
 *   const headerProps = useCampaignHeaderProps({ campaign, stats, onMutate });
 *   <WorkspaceLayout {...headerProps} />
 *
 * Pattern: sections/activities/workspace/ActivityHeader.jsx
 */
"use client";
import { useState } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import CampaignStatusBadge from "sections/campaigns/CampaignStatusBadge";
import {
  CAMPAIGN_FAMILIES,
  CAMPAIGN_FAMILY_LABELS,
  SEQUENCE_TYPE_LABELS,
  OBJECTIVE_TYPE_LABELS,
  getCampaignProgress,
  startCampaign,
  pauseCampaign,
  resumeCampaign,
  completeCampaign,
  generateCampaignActivities,
} from "api/campaigns/campaigns";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// icons
import AimOutlined from "@ant-design/icons/AimOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import BankOutlined from "@ant-design/icons/BankOutlined";
import PlayCircleOutlined from "@ant-design/icons/PlayCircleOutlined";
import PauseCircleOutlined from "@ant-design/icons/PauseCircleOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";

// ==============================|| FAMILY CONFIG ||============================== //

const FAMILY_CONFIG = {
  OUTBOUND: {
    Icon: AimOutlined,
    avatarColor: "primary.main",
    chipColor: "primary",
  },
  TARGETED: {
    Icon: ThunderboltOutlined,
    avatarColor: "warning.main",
    chipColor: "warning",
  },
};

// ==============================|| ACTION BUTTONS COMPONENT ||============================== //

/**
 * Stateful sub-component so we can use useState for loading.
 * After startCampaign succeeds, also calls generateCampaignActivities
 * so the playlist is populated immediately.
 */
function CampaignActionButtons({ campaign, onMutate }) {
  const [loading, setLoading] = useState(false);

  const handleAction = async (actionFn, successMessage) => {
    setLoading(true);
    try {
      const result = await actionFn(campaign.id);

      if (!result.success) {
        displayErrorSnackbar(result);
        return;
      }

      // Generate activities right after start so the playlist is immediately populated
      if (actionFn === startCampaign) {
        const genResult = await generateCampaignActivities(campaign.id);
        if (!genResult.success) {
          displayErrorSnackbar(
            "Campaign started but activity generation failed. Refresh to retry.",
          );
        }
      }

      displaySuccessSnackbar(successMessage);
      if (onMutate) onMutate();
    } catch {
      displayErrorSnackbar("An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack direction="row" spacing={1}>
      {campaign.status === "DRAFT" && (
        <Button
          variant="contained"
          color="success"
          size="small"
          startIcon={
            loading ? (
              <CircularProgress size={14} color="inherit" />
            ) : (
              <PlayCircleOutlined />
            )
          }
          disabled={loading}
          onClick={() => handleAction(startCampaign, "Campaign started")}
        >
          Start
        </Button>
      )}
      {campaign.status === "ACTIVE" && (
        <>
          <Button
            variant="outlined"
            color="warning"
            size="small"
            startIcon={
              loading ? (
                <CircularProgress size={14} color="inherit" />
              ) : (
                <PauseCircleOutlined />
              )
            }
            disabled={loading}
            onClick={() => handleAction(pauseCampaign, "Campaign paused")}
          >
            Pause
          </Button>
          <Button
            variant="outlined"
            color="primary"
            size="small"
            startIcon={
              loading ? (
                <CircularProgress size={14} color="inherit" />
              ) : (
                <CheckCircleOutlined />
              )
            }
            disabled={loading}
            onClick={() => handleAction(completeCampaign, "Campaign completed")}
          >
            Complete
          </Button>
        </>
      )}
      {campaign.status === "PAUSED" && (
        <>
          <Button
            variant="contained"
            color="success"
            size="small"
            startIcon={
              loading ? (
                <CircularProgress size={14} color="inherit" />
              ) : (
                <PlayCircleOutlined />
              )
            }
            disabled={loading}
            onClick={() => handleAction(resumeCampaign, "Campaign resumed")}
          >
            Resume
          </Button>
          <Button
            variant="outlined"
            color="primary"
            size="small"
            startIcon={
              loading ? (
                <CircularProgress size={14} color="inherit" />
              ) : (
                <CheckCircleOutlined />
              )
            }
            disabled={loading}
            onClick={() => handleAction(completeCampaign, "Campaign completed")}
          >
            Complete
          </Button>
        </>
      )}
    </Stack>
  );
}

// ==============================|| CAMPAIGN HEADER HOOK ||============================== //

/**
 * @param {Object} params
 * @param {Object}   params.campaign  - Campaign data from API
 * @param {Object}   params.stats     - Campaign stats
 * @param {Function} params.onMutate  - Callback to revalidate campaign after lifecycle action
 * @returns {Object} Props object spread into <WorkspaceLayout {...props} />
 */
export default function useCampaignHeaderProps({ campaign, stats, onMutate }) {
  const theme = useTheme();

  if (!campaign) {
    return {
      avatar: null,
      title: "",
      chips: [],
      infoItems: [],
      headerActions: null,
    };
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const familyConfig =
    FAMILY_CONFIG[campaign.campaign_type] || FAMILY_CONFIG.OUTBOUND;
  const FamilyIcon = familyConfig.Icon;
  const progress = stats?.completion_rate || getCampaignProgress(campaign);

  // ==============================|| AVATAR + TITLE ||============================== //

  const avatar = (
    <Avatar
      sx={{
        width: 56,
        height: 56,
        bgcolor: familyConfig.avatarColor,
        fontSize: "1.5rem",
      }}
    >
      <FamilyIcon />
    </Avatar>
  );

  const title = campaign.name || "";

  const headerActions = (
    <CampaignActionButtons campaign={campaign} onMutate={onMutate} />
  );

  // ==============================|| ROW 2: Chips ||============================== //

  const chips = [
    <CampaignStatusBadge key="status" status={campaign.status} />,
    <Chip
      key="family"
      label={
        CAMPAIGN_FAMILY_LABELS[campaign.campaign_type] || campaign.campaign_type
      }
      size="small"
      color={familyConfig.chipColor}
      variant="outlined"
    />,
    campaign.sequence_type && (
      <Chip
        key="sequence"
        label={
          SEQUENCE_TYPE_LABELS[campaign.sequence_type] || campaign.sequence_type
        }
        size="small"
        variant="outlined"
      />
    ),
  ].filter(Boolean);

  // ==============================|| ROW 3: Info Items (JSX elements) ||============================== //

  const infoItems = [
    // Territory
    campaign.territory_name && (
      <Stack key="territory" direction="row" spacing={0.75} alignItems="center">
        <BankOutlined
          style={{ fontSize: 14, color: theme.palette.text.secondary }}
        />
        <Typography variant="body2" color="text.secondary">
          {campaign.territory_name}
        </Typography>
      </Stack>
    ),
    // Objective
    campaign.objective_type && (
      <Stack key="objective" direction="row" spacing={0.75} alignItems="center">
        <CheckCircleOutlined
          style={{ fontSize: 14, color: theme.palette.text.secondary }}
        />
        <Typography variant="body2" color="text.secondary">
          {OBJECTIVE_TYPE_LABELS[campaign.objective_type] ||
            campaign.objective_type}
        </Typography>
      </Stack>
    ),
    // Dates
    campaign.start_date && (
      <Stack key="dates" direction="row" spacing={0.75} alignItems="center">
        <CalendarOutlined
          style={{ fontSize: 14, color: theme.palette.text.secondary }}
        />
        <Typography variant="body2" color="text.secondary">
          {campaign.start_date}
          {campaign.end_date ? ` → ${campaign.end_date}` : ""}
        </Typography>
      </Stack>
    ),
    // Members
    <Stack key="members" direction="row" spacing={0.75} alignItems="center">
      <TeamOutlined
        style={{ fontSize: 14, color: theme.palette.text.secondary }}
      />
      <Typography variant="body2" color="text.secondary">
        {campaign.members?.length || stats?.total_members || 0} members
      </Typography>
    </Stack>,
    // Accounts
    <Stack key="accounts" direction="row" spacing={0.75} alignItems="center">
      <BankOutlined
        style={{ fontSize: 14, color: theme.palette.text.secondary }}
      />
      <Typography variant="body2" color="text.secondary">
        {stats?.total_accounts ?? campaign.accounts_count ?? 0} accounts
      </Typography>
    </Stack>,
    // Progress
    typeof progress === "number" && (
      <Stack key="progress" direction="row" spacing={0.75} alignItems="center">
        <Typography
          variant="body2"
          color={progress >= 100 ? "success.main" : "text.secondary"}
          fontWeight={500}
        >
          {progress}% complete
        </Typography>
      </Stack>
    ),
  ].filter(Boolean);

  // ==============================|| RETURN ||============================== //

  return {
    avatar,
    title,
    headerActions,
    chips,
    infoItems,
  };
}
