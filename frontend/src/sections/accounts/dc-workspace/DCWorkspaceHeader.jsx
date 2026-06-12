"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";

// Date formatting
import { format } from "date-fns";

// Icons
import {
  ApartmentOutlined,
  EditOutlined,
  CalendarOutlined,
  UserOutlined,
  BankOutlined,
} from "@ant-design/icons";

// Project imports
import { updateDecisionCycle } from "api/accounts/decisionCycles";
import {
  CYCLE_DERIVED_STATUS_LABELS,
  CYCLE_STATUS_COLORS,
} from "api/accounts/decisionCycles";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";
import DecisionCycleModal from "sections/accounts/decision-cycles/DecisionCycleModal";
import DealHealthRunButton from "./DealHealthRunButton";

// ==============================|| DC WORKSPACE HEADER HOOK ||============================== //

export default function useDCWorkspaceHeaderProps({
  cycle,
  accountId,
  onUpdate,
}) {
  const theme = useTheme();
  const [editModalOpen, setEditModalOpen] = useState(false);

  const isCycleClosed = ["WON", "LOST", "NOT_QUALIFIED"].includes(
    cycle?.outcome,
  );
  const isCyclePaused = cycle?.outcome === "ON_HOLD";
  const isLocked = isCycleClosed || isCyclePaused;

  // Effective status: outcome takes priority over derived cycle_status
  const effectiveStatus = cycle?.outcome || cycle?.cycle_status || "IN_PROGRESS";

  // ==============================|| TITLE SAVE ||============================== //

  const handleTitleSave = async (newTitle) => {
    if (isLocked || !cycle?.id) return false;

    try {
      const result = await updateDecisionCycle(cycle.id, {
        name: newTitle.trim(),
      });
      if (result.success) {
        displaySuccessSnackbar("Cycle name updated");
        onUpdate?.();
        return true;
      }
      displayErrorSnackbar(result);
      return false;
    } catch (err) {
      displayErrorSnackbar(err);
      return false;
    }
  };

  // ==============================|| AVATAR ||============================== //

  const avatar = (
    <Avatar
      sx={{
        bgcolor: `${CYCLE_STATUS_COLORS[effectiveStatus] || "primary"}.lighter`,
        color: `${CYCLE_STATUS_COLORS[effectiveStatus] || "primary"}.main`,
        width: 48,
        height: 48,
      }}
    >
      <ApartmentOutlined style={{ fontSize: theme.iconSizes?.lg || 24 }} />
    </Avatar>
  );

  // ==============================|| CHIPS ||============================== //

  const chips = [];

  chips.push(
    <Chip
      key="status"
      label={CYCLE_DERIVED_STATUS_LABELS[effectiveStatus] || effectiveStatus}
      size="small"
      color={CYCLE_STATUS_COLORS[effectiveStatus] || "default"}
      variant="filled"
    />,
  );

  if (cycle?.steps_count != null) {
    const validated = cycle.validated_steps_count || 0;
    chips.push(
      <Chip
        key="progress"
        label={`${validated}/${cycle.steps_count} steps`}
        size="small"
        variant="outlined"
      />,
    );
  }

  // ==============================|| INFO ITEMS ||============================== //

  const infoItems = [];

  if (cycle?.account_name) {
    infoItems.push({
      icon: BankOutlined,
      label: cycle.account_name,
    });
  }

  if (cycle?.owner_name) {
    infoItems.push({
      icon: UserOutlined,
      label: cycle.owner_name,
    });
  }

  if (cycle?.created_at) {
    infoItems.push({
      icon: CalendarOutlined,
      label: format(new Date(cycle.created_at), "MMM d, yyyy"),
    });
  }

  // ==============================|| HEADER ACTIONS ||============================== //

  const headerActions = (
    <Stack direction="row" spacing={1} alignItems="center">
      <DealHealthRunButton cycleId={cycle?.id} disabled={isLocked} />
      <Tooltip title="Edit cycle">
        <IconButton
          size="small"
          onClick={() => setEditModalOpen(true)}
          disabled={isLocked}
        >
          <EditOutlined />
        </IconButton>
      </Tooltip>
    </Stack>
  );

  // ==============================|| MODALS ||============================== //

  const modals = (
    <DecisionCycleModal
      open={editModalOpen}
      onClose={() => setEditModalOpen(false)}
      cycle={cycle}
      accountId={accountId}
      onSuccess={() => {
        onUpdate?.();
      }}
    />
  );

  // ==============================|| RETURN ||============================== //

  return {
    avatar,
    title: cycle?.name || "",
    onTitleSave: handleTitleSave,
    titleDisabled: isLocked,
    headerActions,
    chips,
    infoItems,
    modals,
  };
}

useDCWorkspaceHeaderProps.propTypes = {
  cycle: PropTypes.object,
  accountId: PropTypes.string,
  onUpdate: PropTypes.func,
};
