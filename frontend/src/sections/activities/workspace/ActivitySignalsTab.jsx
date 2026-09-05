// frontend/src/sections/activities/workspace/ActivitySignalsTab.jsx
//
// Activity "Signals" tab — FLAT-FORCED (SIG-2). The Grouped/Flat toggle is gone:
// this tab is now only the flat validation list (SignalsValidationList), which
// splits the activity's signals into 3 status sections (To validate / Validated
// / Rejected), each grouped by type behind a coloured type header. The grouped
// synthesis still lives in its own place (ActivityQualificationTab, and the
// shared grouped views on DC / Account) — untouched here.
//
// The list is fed by the aggregated endpoint (useAggregatedSignals) scoped by
// activity_id. It fetches the whole matching set in one page (pageSize 100, the
// endpoint's max) so the 3 sections are coherent — no server pager. Clicking a
// row injects the signal detail into the single workspace drawer coque.

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// MUI
import Badge from "@mui/material/Badge";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// icons
import FilterOutlined from "@ant-design/icons/FilterOutlined";

// Project imports
import useAggregatedSignals from "api/signals/aggregatedSignals";
import useSignalFilters from "hooks/useSignalFilters";
import { useGetSignalChoices } from "api/signals/signals";
import {
  validateSignal,
  rejectSignal,
  reopenSignal,
} from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Section imports
import SignalsFilterPanel from "components/signals/SignalsFilterPanel";
import SignalsValidationList from "components/signals/SignalsValidationList";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import SignalEditDrawer from "components/signals/SignalEditDrawer";
import SignalsSortSelect from "sections/activities/signals/SignalsSortSelect";

// The activity flat view shows qualification (pain/objective/impact) plus
// tech-stack, blockers and constraints, competitors and people — next-steps
// live in their own tab and are excluded. Constraints are activity-scoped
// provenance here (the DC groups them by nature; the account excludes them).
const ACTIVITY_FLAT_TYPES = [
  "pain",
  "objective",
  "impact",
  "tech-stack",
  "blockers",
  "constraints",
  "competitors",
  "people",
];

// The aggregated endpoint caps page_size at 100 (core StandardResultsSetPagination).
// One activity's signal set sits well under that, so we fetch it all in one page
// and render the 3 grouped sections without a pager.
const PAGE_SIZE = 100;

// ==============================|| ACTIVITY SIGNALS TAB (FLAT) ||============================== //

export default function ActivitySignalsTab({
  activity,
  isLocked,
  mutateCounts,
}) {
  const activityId = activity?.id;
  const accountId = activity?.account;

  // Choices for edit forms
  const { choices, choicesLoading } = useGetSignalChoices();

  // Filter / sort state
  const [filterPanelOpen, setFilterPanelOpen] = useState(false);
  const {
    pending,
    updatePending,
    apply,
    clear,
    syncPending,
    statuses,
    activeTypes,
    department,
    contactId,
    scope,
    activeCount,
    hasPendingChanges,
  } = useSignalFilters();

  // Controlled department list + contact-search scope for the filter drawer.
  const { standardDepartments } = useGetContactChoices();
  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: d.value ?? d.id,
        label: d.label ?? d.name,
      })),
    [standardDepartments],
  );
  const contactFilters = useMemo(() => ({ account_id: accountId }), [accountId]);

  const [sortKey, setSortKey] = useState("date-desc");

  // The single workspace drawer coque (B3.5.3): clicking a signal injects its
  // detail via openDrawer; the coque owns open state + close.
  const { openDrawer } = useWorkspaceDrawer();

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);
  const [editType, setEditType] = useState(null);

  // One aggregated call, server-driven filter / sort. The filter drawer drives
  // signal_type (a subset; none selected = all activity types) and status
  // (default pending+validated, +rejected when opted in — which surfaces the
  // Rejected section). The whole set comes back in one page (pageSize 100).
  const signalTypes = useMemo(
    () => (activeTypes.length ? activeTypes : ACTIVITY_FLAT_TYPES),
    [activeTypes],
  );

  const {
    signals: flatSignals,
    loading,
    error,
    mutate: mutateAll,
  } = useAggregatedSignals({
    activityId,
    statuses,
    signalTypes,
    department,
    contact: contactId,
    scope,
    ordering: sortKey,
    page: 1,
    pageSize: PAGE_SIZE,
  });

  // Handlers
  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal validated");
        mutateAll();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts],
  );

  const handleReject = useCallback(
    async (signal, signalType) => {
      const result = await rejectSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal rejected");
        mutateAll();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts],
  );

  const handleReopen = useCallback(
    async (signal, signalType) => {
      const result = await reopenSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateAll();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts],
  );

  const handleEdit = useCallback((signal, signalType) => {
    setEditSignal(signal);
    setEditType(signalType);
    setEditDialogOpen(true);
  }, []);

  // Inject the signal detail into the single coque. Clicking another signal
  // replaces the content (React reconciles the panel in place); the coque owns
  // the close button. Declared after the action handlers it captures.
  const handleSelect = useCallback(
    (signal, signalType) => {
      openDrawer(
        <SignalDetailPanel
          signal={signal}
          signalType={signalType}
          onValidate={handleValidate}
          onReject={handleReject}
          onEdit={handleEdit}
          onReopen={handleReopen}
          isLocked={isLocked}
        />,
      );
    },
    [openDrawer, handleValidate, handleReject, handleEdit, handleReopen, isLocked],
  );

  const handleEditClose = useCallback(() => {
    setEditDialogOpen(false);
    setEditSignal(null);
    setEditType(null);
  }, []);

  const handleEditSuccess = useCallback(() => {
    mutateAll();
    mutateCounts?.();
  }, [mutateAll, mutateCounts]);

  const handleOpenFilters = () => {
    syncPending();
    setFilterPanelOpen(true);
  };
  const handleApplyFilters = () => {
    apply();
  };
  const handleClearFilters = () => {
    clear();
  };

  // A fetch can fail while previous data is still shown (SWR keeps the last
  // data). Keep the list and surface the transient failure via the standard
  // error snackbar instead of blanking the view.
  useEffect(() => {
    if (error && flatSignals.length) displayErrorSnackbar(error);
  }, [error, flatSignals.length]);

  return (
    <Box>
      {/* Toolbar: sort · filter icon */}
      <Stack
        direction="row"
        justifyContent="flex-end"
        alignItems="center"
        sx={{ mb: 2.5, flexWrap: "wrap", gap: 1 }}
      >
        <SignalsSortSelect value={sortKey} onChange={setSortKey} />
        <Tooltip title="Filters">
          <IconButton onClick={handleOpenFilters} aria-label="Open filters">
            <Badge badgeContent={activeCount} color="primary">
              <FilterOutlined />
            </Badge>
          </IconButton>
        </Tooltip>
      </Stack>

      {/* The flat validation list: 3 status sections × type groups. */}
      {error && !flatSignals.length ? (
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="300px"
        >
          <Typography color="error">Failed to load signals</Typography>
        </Box>
      ) : (
        <SignalsValidationList
          signals={flatSignals}
          loading={loading}
          onSelect={handleSelect}
          emptyMessage="No signals match these filters"
        />
      )}

      {/* Filter drawer (flat mode) — type / department / contact / include-rejected. */}
      <SignalsFilterPanel
        open={filterPanelOpen}
        onClose={() => setFilterPanelOpen(false)}
        availableTypes={ACTIVITY_FLAT_TYPES}
        departmentOptions={departmentOptions}
        contactFilters={contactFilters}
        pendingFilters={pending}
        onFilterChange={updatePending}
        onApply={handleApplyFilters}
        onClear={handleClearFilters}
        hasPendingChanges={hasPendingChanges}
        mode="flat"
      />

      {/* Edit Dialog */}
      <SignalEditDrawer
        context="activity"
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

ActivitySignalsTab.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    account: PropTypes.string,
  }),
  isLocked: PropTypes.bool,
  mutateCounts: PropTypes.func,
};
