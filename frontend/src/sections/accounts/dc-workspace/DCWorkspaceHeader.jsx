"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";

// MUI
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import ListItemText from "@mui/material/ListItemText";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Date formatting
import { format, differenceInDays, addDays } from "date-fns";

// Icons
import {
  ApartmentOutlined,
  CalendarOutlined,
  DashboardOutlined,
  DownOutlined,
  EditOutlined,
  FieldTimeOutlined,
  NodeIndexOutlined,
  SwapOutlined,
  UserOutlined,
  BankOutlined,
  DollarOutlined,
} from "@ant-design/icons";

// Project imports
import {
  updateDecisionCycle,
  useGetDecisionCyclesByAccount,
  CYCLE_DERIVED_STATUS_LABELS,
  CYCLE_STATUS_COLORS,
} from "api/accounts/decisionCycles";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";
import DecisionCycleModal from "sections/accounts/decision-cycles/DecisionCycleModal";
import DealHealthRunButton from "./DealHealthRunButton";
import CycleCloseDialog, { useCycleCloseReopen } from "./CycleCloseDialog";

// ==============================|| HELPERS ||============================== //

function formatCurrency(value) {
  if (value == null) return null;
  const num = Number(value);
  if (Number.isNaN(num)) return null;
  return num.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

// ==============================|| DC WORKSPACE HEADER HOOK ||============================== //

export default function useDCWorkspaceHeaderProps({
  cycle,
  accountId,
  onUpdate,
}) {
  const theme = useTheme();
  const router = useRouter();
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectorAnchor, setSelectorAnchor] = useState(null);

  const isCycleClosed = ["WON", "LOST", "NOT_QUALIFIED"].includes(
    cycle?.outcome,
  );
  const isCyclePaused = cycle?.outcome === "ON_HOLD";
  const isLocked = isCycleClosed || isCyclePaused;

  const effectiveStatus =
    cycle?.outcome || cycle?.cycle_status || "IN_PROGRESS";

  // Close/reopen
  const closeReopen = useCycleCloseReopen({ cycle, onRefresh: onUpdate });

  // Sibling cycles for selector
  const { cycles } = useGetDecisionCyclesByAccount(accountId);
  const otherCycles = useMemo(
    () => (cycles || []).filter((c) => c.id !== cycle?.id),
    [cycles, cycle?.id],
  );

  // Progress object
  const progress = cycle?.progress || {};
  const percentage = progress.percentage ?? 0;

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

  // ==============================|| CYCLE SELECTOR ||============================== //

  const handleSelectorOpen = useCallback((e) => {
    setSelectorAnchor(e.currentTarget);
  }, []);

  const handleSelectorClose = useCallback(() => {
    setSelectorAnchor(null);
  }, []);

  const handleSwitchCycle = useCallback(
    (otherId) => {
      setSelectorAnchor(null);
      router.push(`/accounts/${accountId}/dc/${otherId}`);
    },
    [router, accountId],
  );

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

  // Age chip
  if (cycle?.created_at) {
    const age = differenceInDays(new Date(), new Date(cycle.created_at));
    chips.push(
      <Chip key="age" label={`${age}d`} size="small" variant="outlined" />,
    );
  }

  // Progress chip
  chips.push(
    <Chip
      key="progress"
      label={`${percentage}%`}
      size="small"
      variant="outlined"
    />,
  );

  // ==============================|| INFO ITEMS ||============================== //

  const infoItems = [];

  // Account
  if (cycle?.account_name) {
    infoItems.push(
      <Stack key="account" direction="row" spacing={0.75} alignItems="center">
        <BankOutlined
          style={{
            fontSize: theme.iconSizes?.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {cycle.account_name}
        </Typography>
      </Stack>,
    );
  }

  // Owner
  if (cycle?.owner_name) {
    infoItems.push(
      <Stack key="owner" direction="row" spacing={0.75} alignItems="center">
        <UserOutlined
          style={{
            fontSize: theme.iconSizes?.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {cycle.owner_name}
        </Typography>
      </Stack>,
    );
  }

  // Estimated value
  const formattedValue = formatCurrency(cycle?.estimated_value);
  if (formattedValue) {
    infoItems.push(
      <Stack key="value" direction="row" spacing={0.75} alignItems="center">
        <DollarOutlined
          style={{
            fontSize: theme.iconSizes?.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {formattedValue}
        </Typography>
      </Stack>,
    );
  }

  // Current step
  if (progress.current_step_name) {
    const stepLabel = progress.current_step_order
      ? `${progress.current_step_name} (${progress.current_step_order}/${progress.total_steps ?? 0})`
      : progress.current_step_name;
    infoItems.push(
      <Stack key="step" direction="row" spacing={0.75} alignItems="center">
        <NodeIndexOutlined
          style={{
            fontSize: theme.iconSizes?.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {stepLabel}
        </Typography>
      </Stack>,
    );
  }

  // Readiness
  if (cycle?.readiness_score != null) {
    infoItems.push(
      <Stack key="readiness" direction="row" spacing={0.75} alignItems="center">
        <DashboardOutlined
          style={{
            fontSize: theme.iconSizes?.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          Readiness {cycle.readiness_score}%
        </Typography>
      </Stack>,
    );
  }

  // Closing date (created_at + estimated_timeline_days, or outcome_date)
  if (cycle?.outcome_date) {
    infoItems.push(
      <Stack key="closing" direction="row" spacing={0.75} alignItems="center">
        <CalendarOutlined
          style={{
            fontSize: theme.iconSizes?.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          Closed {format(new Date(cycle.outcome_date), "MMM d, yyyy")}
        </Typography>
      </Stack>,
    );
  } else if (
    cycle?.created_at &&
    cycle?.estimated_timeline_days != null &&
    cycle.estimated_timeline_days > 0
  ) {
    const closingDate = addDays(
      new Date(cycle.created_at),
      cycle.estimated_timeline_days,
    );
    infoItems.push(
      <Stack key="closing" direction="row" spacing={0.75} alignItems="center">
        <FieldTimeOutlined
          style={{
            fontSize: theme.iconSizes?.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          Est. close {format(closingDate, "MMM d, yyyy")}
        </Typography>
      </Stack>,
    );
  } else if (cycle?.created_at) {
    infoItems.push(
      <Stack key="date" direction="row" spacing={0.75} alignItems="center">
        <CalendarOutlined
          style={{
            fontSize: theme.iconSizes?.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {format(new Date(cycle.created_at), "MMM d, yyyy")}
        </Typography>
      </Stack>,
    );
  }

  // ==============================|| HEADER ACTIONS ||============================== //

  const headerActions = (
    <Stack direction="row" spacing={1} alignItems="center">
      {/* Cycle selector */}
      {otherCycles.length > 0 && (
        <>
          <Tooltip title="Switch cycle">
            <IconButton size="small" onClick={handleSelectorOpen}>
              <SwapOutlined />
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={selectorAnchor}
            open={Boolean(selectorAnchor)}
            onClose={handleSelectorClose}
          >
            {otherCycles.map((c) => (
              <MenuItem key={c.id} onClick={() => handleSwitchCycle(c.id)}>
                <ListItemText
                  primary={c.name}
                  secondary={
                    CYCLE_DERIVED_STATUS_LABELS[c.outcome || c.cycle_status] ||
                    "Active"
                  }
                />
              </MenuItem>
            ))}
          </Menu>
        </>
      )}

      <DealHealthRunButton cycleId={cycle?.id} disabled={isLocked} />

      <Tooltip title="Edit cycle">
        <span>
          <IconButton
            size="small"
            onClick={() => setEditModalOpen(true)}
            disabled={isLocked}
          >
            <EditOutlined />
          </IconButton>
        </span>
      </Tooltip>

      {/* Close / Reopen */}
      {isCycleClosed || isCyclePaused ? (
        <Button
          size="small"
          variant="outlined"
          onClick={closeReopen.handleReopenCycle}
          disabled={closeReopen.reopenLoading}
        >
          {closeReopen.reopenLoading ? "Reopening..." : "Reopen"}
        </Button>
      ) : (
        <Button
          size="small"
          variant="outlined"
          color="warning"
          onClick={() => closeReopen.setCloseDialogOpen(true)}
        >
          Close
        </Button>
      )}
    </Stack>
  );

  // ==============================|| MODALS ||============================== //

  const modals = (
    <>
      <DecisionCycleModal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        cycle={cycle}
        accountId={accountId}
        onSuccess={() => {
          onUpdate?.();
        }}
      />
      <CycleCloseDialog
        open={closeReopen.closeDialogOpen}
        onClose={closeReopen.handleCloseDialogDismiss}
        formik={closeReopen.closeFormik}
      />
    </>
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
