// frontend/src/sections/accounts/dc-workspace/SignalsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { InboxOutlined } from "@ant-design/icons";

// Project imports
import useDCAllSignals from "hooks/useDCAllSignals";
import { useGetSignalChoices } from "api/signals/signals";
import { validateSignal, rejectSignal, reopenSignal } from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Section imports — reuse Activity signal components
import SignalsFilterBar from "sections/activities/signals/SignalsFilterBar";
import SignalsFlatView from "sections/activities/signals/SignalsFlatView";
import SignalsSortSelect from "sections/activities/signals/SignalsSortSelect";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";

// ==============================|| SIGNAL TYPE FILTER ||============================== //

const TYPE_FILTERS = [
  { value: "all", label: "All" },
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "impact", label: "Impact" },
  { value: "tech-stack", label: "Tech Stack" },
  { value: "blockers", label: "Blocker" },
  { value: "next-steps", label: "Next Step" },
  { value: "people", label: "People" },
  { value: "constraints", label: "Constraint" },
];

// Types supported by SignalEditDialog (inline forms exist only for these)
const EDITABLE_TYPES = new Set([
  "pain",
  "objective",
  "impact",
  "tech-stack",
  "blockers",
  "next-steps",
]);

// ==============================|| TYPE FILTER BAR ||============================== //

import Chip from "@mui/material/Chip";

function TypeFilterBar({ activeType, onChange, signalsByType }) {
  return (
    <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
      <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
        Type:
      </Typography>
      {TYPE_FILTERS.map((f) => {
        const count =
          f.value === "all"
            ? Object.values(signalsByType).reduce(
                (sum, arr) => sum + arr.length,
                0,
              )
            : (signalsByType[f.value] || []).length;
        return (
          <Chip
            key={f.value}
            label={`${f.label} (${count})`}
            size="small"
            variant={activeType === f.value ? "filled" : "outlined"}
            color={activeType === f.value ? "primary" : "default"}
            onClick={() => onChange(f.value)}
            clickable
          />
        );
      })}
    </Stack>
  );
}

TypeFilterBar.propTypes = {
  activeType: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  signalsByType: PropTypes.object.isRequired,
};

// ==============================|| DC SIGNALS TAB ||============================== //

export default function SignalsTab({ cycleId, accountId }) {
  const {
    signalsByType,
    allSignals,
    loading,
    error,
    mutateAll,
  } = useDCAllSignals(accountId, cycleId);

  const { choices, choicesLoading } = useGetSignalChoices();

  // Status filter state
  const [statusFilter, setStatusFilter] = useState("all-active");
  const [includeRejected, setIncludeRejected] = useState(false);

  // Type filter state
  const [typeFilter, setTypeFilter] = useState("all");

  // Sort state
  const [sortKey, setSortKey] = useState("date-desc");

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedType, setSelectedType] = useState(null);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);
  const [editType, setEditType] = useState(null);

  // Type-filtered signals
  const typeFilteredSignals = useMemo(() => {
    if (typeFilter === "all") return allSignals;
    return allSignals.filter((s) => s._signalType === typeFilter);
  }, [allSignals, typeFilter]);

  // Status-filtered signals
  const statusFilterFn = useCallback(
    (s) => {
      const isRejected = s.status === "REJECTED";
      if (isRejected) return includeRejected;
      if (statusFilter === "all-active") return true;
      return s.status === statusFilter;
    },
    [statusFilter, includeRejected],
  );

  const filteredSignals = useMemo(
    () => typeFilteredSignals.filter(statusFilterFn),
    [typeFilteredSignals, statusFilterFn],
  );

  // Handlers
  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal validated");
        mutateAll();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  const handleReject = useCallback(
    async (signal, signalType) => {
      const result = await rejectSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal rejected");
        mutateAll();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  const handleReopen = useCallback(
    async (signal, signalType) => {
      const result = await reopenSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateAll();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  const handleEdit = useCallback((signal, signalType) => {
    if (!EDITABLE_TYPES.has(signalType)) return;
    setEditSignal(signal);
    setEditType(signalType);
    setEditDialogOpen(true);
  }, []);

  const handleEditClose = useCallback(() => {
    setEditDialogOpen(false);
    setEditSignal(null);
    setEditType(null);
  }, []);

  const handleEditSuccess = useCallback(() => {
    mutateAll();
  }, [mutateAll]);

  const handleSelect = useCallback((signal, signalType) => {
    setSelectedSignal(signal);
    setSelectedType(signalType);
    setDrawerOpen(true);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedSignal(null);
    setSelectedType(null);
  }, []);

  // Loading state
  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <Typography color="error">Failed to load signals</Typography>
      </Box>
    );
  }

  // Empty state
  if (allSignals.length === 0) {
    return (
      <Box
        display="flex"
        flexDirection="column"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
        gap={1}
      >
        <InboxOutlined style={{ fontSize: 36, color: "#8c8c8c" }} />
        <Typography color="text.secondary">
          No signals captured for this cycle yet.
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Signals are extracted from activity transcripts or created manually.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Toolbar: status filter + type filter + sort */}
      <Stack spacing={1.5} sx={{ mb: 2.5 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={1}
        >
          <SignalsFilterBar
            activeFilter={statusFilter}
            onChange={setStatusFilter}
            includeRejected={includeRejected}
            onToggleRejected={setIncludeRejected}
            signals={typeFilteredSignals}
          />
          <SignalsSortSelect value={sortKey} onChange={setSortKey} />
        </Stack>
        <TypeFilterBar
          activeType={typeFilter}
          onChange={setTypeFilter}
          signalsByType={signalsByType}
        />
      </Stack>

      {/* Signal list — flat view only (grouped view = Strategic/Themes tab) */}
      <SignalsFlatView
        signals={filteredSignals}
        sortKey={sortKey}
        onSelect={handleSelect}
        onValidate={handleValidate}
        onReject={handleReject}
        onEdit={handleEdit}
        onReopen={handleReopen}
        isLocked={false}
        emptyMessage="No signals for this decision cycle"
      />

      {/* Quick Drawer */}
      <SignalQuickDrawer
        open={drawerOpen}
        signal={selectedSignal}
        signalType={selectedType}
        onClose={handleCloseDrawer}
        onValidate={handleValidate}
        onReject={handleReject}
        onEdit={handleEdit}
        isLocked={false}
      />

      {/* Edit Dialog (6 original types only — people/constraints forms deferred) */}
      <SignalEditDialog
        open={editDialogOpen}
        onClose={handleEditClose}
        onSuccess={handleEditSuccess}
        signal={editSignal}
        signalType={editType}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
      />
    </Box>
  );
}

SignalsTab.propTypes = {
  cycleId: PropTypes.string.isRequired,
  accountId: PropTypes.string.isRequired,
};
