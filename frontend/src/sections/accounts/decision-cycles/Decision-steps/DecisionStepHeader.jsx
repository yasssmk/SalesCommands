// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepHeader.jsx
/**
 * Decision Step Header — Hook version for WorkspaceLayout.
 *
 * Returns layout props (no modals, no editable title, no actions):
 *   { avatar, title, chips, infoItems }
 *
 * Usage in index.jsx:
 *   const headerProps = useDecisionStepHeaderProps({ step, account, onAccountClick, onCycleClick });
 *   <WorkspaceLayout {...headerProps} />
 */

"use client";

import { useState } from "react";
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import AimOutlined from "@ant-design/icons/AimOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import AddToCampaignModal from "sections/campaigns/AddToCampaignModal";

// API
import { PIPELINE_STEP_LABELS } from "api/accounts/decisionCycles";

// Icons
import {
  SearchOutlined,
  ToolOutlined,
  SolutionOutlined,
  DollarOutlined,
  FileProtectOutlined,
  BankOutlined,
  ApartmentOutlined,
} from "@ant-design/icons";

// ==============================|| STAGE CONFIGURATION ||============================== //

const STAGE_ICONS = {
  QUALIFICATION: SearchOutlined,
  TECHNICAL_FIT: ToolOutlined,
  SOLUTION_VALIDATION: SolutionOutlined,
  BUSINESS_CASE: DollarOutlined,
  CLOSING: FileProtectOutlined,
};

const STAGE_AVATAR_COLORS = {
  QUALIFICATION: "info.main",
  TECHNICAL_FIT: "secondary.main",
  SOLUTION_VALIDATION: "success.main",
  BUSINESS_CASE: "warning.main",
  CLOSING: "primary.main",
};

const STATUS_CONFIG = {
  OVERDUE: { label: "Overdue", color: "error" },
  VALIDATED: { label: "Validated", color: "primary" },
  IN_PROGRESS: { label: "In Progress", color: "secondary" },
  STALLED: { color: "warning", label: "Stalled" },
  IN_CHASING: { label: "In Chasing", color: "warning" },
  NOT_STARTED: { label: "Not Started", color: "default" },
};

// ==============================|| DECISION STEP HEADER HOOK ||============================== //

/**
 * @param {Object} params
 * @param {Object} params.step - Step data from API
 * @param {Object} params.account - Account data from API
 * @param {Function} params.onAccountClick - Navigate to account workspace
 * @param {Function} params.onCycleClick - Navigate to cycle tab
 * @returns {Object} Props object spread into <WorkspaceLayout {...props} />
 */
export default function useDecisionStepHeaderProps({
  step,
  account,
  onAccountClick,
  onCycleClick,
}) {
  const theme = useTheme();
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [addToCampaignOpen, setAddToCampaignOpen] = useState(false);

  if (!step) {
    return {
      avatar: null,
      title: "",
      chips: [],
      infoItems: [],
      headerActions: null,
      modals: null,
    };
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const StageIcon = STAGE_ICONS[step.stage] || SearchOutlined;
  const avatarColor = STAGE_AVATAR_COLORS[step.stage] || "grey.500";
  const statusConfig =
    STATUS_CONFIG[step.derived_status] || STATUS_CONFIG.NOT_STARTED;
  const stepName =
    step.name || PIPELINE_STEP_LABELS?.[step.stage] || step.stage || "";
  const accountName = account?.company_name;
  const accountId = account?.id || step?.account_id;
  const cycleName = step.cycle_detail?.name || step.cycle_name || null;

  // ==============================|| ROW 1: Avatar + Title (read-only) ||============================== //

  const avatar = (
    <Avatar
      sx={{
        width: 56,
        height: 56,
        bgcolor: avatarColor,
        fontSize: "1.5rem",
      }}
    >
      <StageIcon />
    </Avatar>
  );

  const title = stepName;

  // ==============================|| ROW 2: Chips ||============================== //

  const chips = [
    <Chip
      key="status"
      label={step.derived_status_display || statusConfig.label}
      color={statusConfig.color}
      size="small"
      variant="filled"
    />,
  ];

  // ==============================|| ROW 3: Info Items ||============================== //

  const infoItems = [
    // Account (clickable)
    accountName && (
      <Stack
        key="account"
        direction="row"
        spacing={0.75}
        alignItems="center"
        onClick={onAccountClick}
        sx={{
          cursor: "pointer",
          "&:hover .info-link": { textDecoration: "underline" },
        }}
      >
        <BankOutlined
          style={{
            fontSize: theme.iconSizes.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="primary.main" className="info-link">
          {accountName}
        </Typography>
      </Stack>
    ),

    // Cycle (clickable)
    cycleName && (
      <Stack
        key="cycle"
        direction="row"
        spacing={0.75}
        alignItems="center"
        onClick={onCycleClick}
        sx={{
          cursor: "pointer",
          "&:hover .info-link": { textDecoration: "underline" },
        }}
      >
        <ApartmentOutlined
          style={{
            fontSize: theme.iconSizes.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="primary.main" className="info-link">
          {cycleName}
        </Typography>
      </Stack>
    ),
  ];

  // ==============================|| RETURN ||============================== //

  const headerActions = (
    <>
      <IconButton onClick={(e) => setMenuAnchor(e.currentTarget)}>
        <MoreOutlined />
      </IconButton>
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={() => setMenuAnchor(null)}
      >
        <MenuItem
          onClick={() => {
            setMenuAnchor(null);
            setAddToCampaignOpen(true);
          }}
          disabled={!accountId}
        >
          <ListItemIcon>
            <AimOutlined />
          </ListItemIcon>
          <Typography>Add to Campaign</Typography>
        </MenuItem>
      </Menu>
    </>
  );

  const modals = accountId ? (
    <AddToCampaignModal
      open={addToCampaignOpen}
      onClose={() => setAddToCampaignOpen(false)}
      accountId={accountId}
      accountName={accountName}
    />
  ) : null;

  return {
    avatar,
    title,
    chips,
    infoItems,
    headerActions,
    modals,
  };
}
