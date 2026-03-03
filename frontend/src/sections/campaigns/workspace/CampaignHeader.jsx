// frontend/src/sections/campaigns/workspace/CampaignHeader.jsx
/**
 * Campaign Header — Hook version for WorkspaceLayout.
 *
 * Returns layout props:
 *   { avatar, title, chips, infoItems, headerActions }
 *
 * Usage in workspace/index.jsx:
 *   const headerProps = useCampaignHeaderProps({ campaign, stats });
 *   <WorkspaceLayout {...headerProps} />
 *
 * Pattern: sections/activities/workspace/ActivityHeader.jsx
 */

"use client";

// MUI
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
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
} from "api/campaigns/campaigns";

// icons
import AimOutlined from "@ant-design/icons/AimOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import BankOutlined from "@ant-design/icons/BankOutlined";
import GlobalOutlined from "@ant-design/icons/GlobalOutlined";
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

// ==============================|| CAMPAIGN HEADER HOOK ||============================== //

/**
 * @param {Object} params
 * @param {Object} params.campaign - Campaign data from API / mock
 * @param {Object} params.stats - Campaign stats { accounts_count, activities_total, activities_completed, completion_rate }
 * @returns {Object} Props object spread into <WorkspaceLayout {...props} />
 */
export default function useCampaignHeaderProps({ campaign, stats }) {
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

  const isOutbound = campaign.campaign_type === CAMPAIGN_FAMILIES.OUTBOUND;
  const familyConfig =
    FAMILY_CONFIG[campaign.campaign_type] || FAMILY_CONFIG.OUTBOUND;
  const FamilyIcon = familyConfig.Icon;
  const progress = stats?.completion_rate || getCampaignProgress(campaign);

  // ==============================|| ROW 1: Avatar + Title + Actions ||============================== //

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

  // Action buttons based on status
  const headerActions = (
    <Stack direction="row" spacing={1}>
      {campaign.status === "DRAFT" && (
        <Button
          variant="contained"
          color="success"
          size="small"
          startIcon={<PlayCircleOutlined />}
          onClick={() => console.log("TODO: startCampaign", campaign.id)}
        >
          Start
        </Button>
      )}
      {campaign.status === "ACTIVE" && (
        <Button
          variant="outlined"
          color="warning"
          size="small"
          startIcon={<PauseCircleOutlined />}
          onClick={() => console.log("TODO: pauseCampaign", campaign.id)}
        >
          Pause
        </Button>
      )}
      {campaign.status === "PAUSED" && (
        <>
          <Button
            variant="contained"
            color="success"
            size="small"
            startIcon={<PlayCircleOutlined />}
            onClick={() => console.log("TODO: resumeCampaign", campaign.id)}
          >
            Resume
          </Button>
          <Button
            variant="outlined"
            color="primary"
            size="small"
            startIcon={<CheckCircleOutlined />}
            onClick={() => console.log("TODO: completeCampaign", campaign.id)}
          >
            Complete
          </Button>
        </>
      )}
      {campaign.status === "ACTIVE" && (
        <Button
          variant="outlined"
          color="primary"
          size="small"
          startIcon={<CheckCircleOutlined />}
          onClick={() => console.log("TODO: completeCampaign", campaign.id)}
        >
          Complete
        </Button>
      )}
    </Stack>
  );

  // ==============================|| ROW 2: Chips ||============================== //

  const chips = [
    <CampaignStatusBadge key="status" status={campaign.status} />,
    <Chip
      key="family"
      label={
        CAMPAIGN_FAMILY_LABELS[campaign.campaign_type] || campaign.campaign_type
      }
      color={familyConfig.chipColor}
      size="small"
      variant="outlined"
      icon={<FamilyIcon />}
    />,
  ];

  // Territory chip (Prospection only)
  if (isOutbound && campaign.territory_name) {
    chips.push(
      <Chip
        key="territory"
        label={campaign.territory_name}
        size="small"
        variant="outlined"
        icon={<GlobalOutlined />}
      />,
    );
  }

  // Sequence type chip
  if (campaign.sequence_type && SEQUENCE_TYPE_LABELS[campaign.sequence_type]) {
    chips.push(
      <Chip
        key="sequence"
        label={SEQUENCE_TYPE_LABELS[campaign.sequence_type]}
        size="small"
        variant="outlined"
      />,
    );
  }

  // ==============================|| ROW 3: Info Items ||============================== //

  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const infoItems = [
    // Date range
    (campaign.start_date || campaign.end_date) && (
      <Stack key="dates" direction="row" spacing={0.75} alignItems="center">
        <CalendarOutlined
          style={{
            fontSize: theme.iconSizes?.sm || 14,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {formatDate(campaign.start_date) || "No start"}
          {" → "}
          {formatDate(campaign.end_date) || "Ongoing"}
        </Typography>
      </Stack>
    ),

    // Owner
    campaign.members?.[0]?.user_name && (
      <Stack key="owner" direction="row" spacing={0.75} alignItems="center">
        <TeamOutlined
          style={{
            fontSize: theme.iconSizes?.sm || 14,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {campaign.members[0].user_name}
        </Typography>
      </Stack>
    ),

    // Accounts count
    <Stack key="accounts" direction="row" spacing={0.75} alignItems="center">
      <BankOutlined
        style={{
          fontSize: theme.iconSizes?.sm || 14,
          color: theme.palette.text.secondary,
          display: "flex",
        }}
      />
      <Typography variant="body2" color="text.secondary">
        {stats?.accounts_count ?? campaign.accounts_count ?? 0} accounts
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
  ];

  // ==============================|| RETURN ||============================== //

  return {
    avatar,
    title,
    headerActions,
    chips,
    infoItems,
  };
}
