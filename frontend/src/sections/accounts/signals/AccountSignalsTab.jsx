// frontend/src/sections/accounts/signals/AccountSignalsTab.jsx
/**
 * AccountSignalsTab — container for the Signals tab in Account Workspace.
 *
 * Responsibilities:
 *   - Fetch qualification + tech-stack signals for the account (two SWR calls)
 *   - Merge and sort both lists client-side for the "All" view
 *   - Own all modal states (add, edit, reject, supersede)
 *   - Dispatch validate / reject / edit / supersede / delete to the API layer
 *   - Delegate rendering to SignalList, FormSignalAdd, FormSignalEdit, AlertSignalReject
 *
 * Filter state lives here so it persists across modal open/close cycles.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import InputAdornment from "@mui/material/InputAdornment";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// ant-design icons
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import SearchOutlined from "@ant-design/icons/SearchOutlined";

// project imports
import SignalList from "./SignalList";
import FormSignalAdd from "./FormSignalAdd";
import FormSignalEdit from "./FormSignalEdit";
import AlertSignalReject from "./AlertSignalReject";

import {
  useGetSignalsByAccount,
  useGetSignalChoices,
  validateSignal,
  deleteSignal,
} from "api/accounts/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

/** Filter options for signal type toggle */
const TYPE_OPTIONS = [
  { value: "all", label: "All" },
  { value: "qualification", label: "Qualification" },
  { value: "tech-stack", label: "Tech Stack" },
];

/** Filter options for signal status dropdown */
const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "PENDING", label: "Pending" },
  { value: "VALIDATED", label: "Validated" },
  { value: "REJECTED", label: "Rejected" },
  { value: "MERGED", label: "Merged" },
];

// ==============================|| ACCOUNT SIGNALS TAB ||============================== //

/**
 * AccountSignalsTab
 *
 * @param {string} accountId - Account UUID (required)
 * @param {Object} account   - Account object (for pre-filling forms)
 */
export default function AccountSignalsTab({ accountId, account }) {
  // ==============================|| FILTER STATE ||============================== //

  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  // ==============================|| MODAL STATE ||============================== //

  /** FormSignalAdd — also used for supersede (supersedeTarget set when in supersede mode) */
  const [addModal, setAddModal] = useState({
    open: false,
    supersedeTarget: null, // { signal, signalType } — set when superseding
  });

  /** FormSignalEdit */
  const [editModal, setEditModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  /** AlertSignalReject */
  const [rejectModal, setRejectModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  // ==============================|| DATA FETCHING ||============================== //

  const sharedFilters = useMemo(
    () => ({
      status: statusFilter || undefined,
    }),
    [statusFilter],
  );

  const {
    signals: qualSignals,
    signalsLoading: qualLoading,
    signalsError: qualError,
    mutateSignals: mutateQual,
  } = useGetSignalsByAccount(accountId, "qualification", {
    search,
    ordering: "-created_at",
    filters: sharedFilters,
  });

  const {
    signals: tsSignals,
    signalsLoading: tsLoading,
    signalsError: tsError,
    mutateSignals: mutateTs,
  } = useGetSignalsByAccount(accountId, "tech-stack", {
    search,
    ordering: "-created_at",
    filters: sharedFilters,
  });

  const { choices, choicesLoading } = useGetSignalChoices();

  // ==============================|| DERIVED DATA ||============================== //

  /**
   * Build the combined + tagged signal list based on the active type filter.
   *
   * Each signal is tagged with its `signalType` so child components can call
   * the correct API endpoint without knowing which list it came from.
   */
  const signals = useMemo(() => {
    const taggedQual = qualSignals.map((s) => ({
      ...s,
      signalType: "qualification",
    }));
    const taggedTs = tsSignals.map((s) => ({ ...s, signalType: "tech-stack" }));

    let combined;
    if (typeFilter === "qualification") combined = taggedQual;
    else if (typeFilter === "tech-stack") combined = taggedTs;
    else combined = [...taggedQual, ...taggedTs];

    // Client-side sort by created_at desc (both lists are already sorted server-side,
    // merge needs a single pass to maintain overall order).
    return combined.sort(
      (a, b) => new Date(b.created_at) - new Date(a.created_at),
    );
  }, [qualSignals, tsSignals, typeFilter]);

  const isLoading = qualLoading || tsLoading;
  const hasError = qualError || tsError;

  /** Count badges for type toggle buttons */
  const counts = useMemo(
    () => ({
      qualification: qualSignals.length,
      "tech-stack": tsSignals.length,
      all: qualSignals.length + tsSignals.length,
    }),
    [qualSignals, tsSignals],
  );

  // ==============================|| REVALIDATE BOTH LISTS ||============================== //

  const mutateAll = useCallback(() => {
    mutateQual();
    mutateTs();
  }, [mutateQual, mutateTs]);

  // ==============================|| FILTER HANDLERS ||============================== //

  const handleTypeChange = useCallback((_e, newValue) => {
    if (newValue !== null) setTypeFilter(newValue);
  }, []);

  const handleStatusChange = useCallback((e) => {
    setStatusFilter(e.target.value);
  }, []);

  const handleSearchChange = useCallback((e) => {
    setSearch(e.target.value);
  }, []);

  // ==============================|| ACTION HANDLERS ||============================== //

  /** Open FormSignalAdd for manual creation */
  const handleAdd = useCallback(() => {
    setAddModal({ open: true, supersedeTarget: null });
  }, []);

  /** Open FormSignalAdd in supersede mode */
  const handleSupersede = useCallback((signal, signalType) => {
    setAddModal({ open: true, supersedeTarget: { signal, signalType } });
  }, []);

  const handleAddClose = useCallback(() => {
    setAddModal({ open: false, supersedeTarget: null });
  }, []);

  const handleAddSuccess = useCallback(() => {
    setAddModal({ open: false, supersedeTarget: null });
    mutateAll();
    displaySuccessSnackbar("Signal created successfully");
  }, [mutateAll]);

  /** Open FormSignalEdit */
  const handleEdit = useCallback((signal, signalType) => {
    setEditModal({ open: true, signal, signalType });
  }, []);

  const handleEditClose = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleEditSuccess = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
    mutateAll();
    displaySuccessSnackbar("Signal updated successfully");
  }, [mutateAll]);

  /** Open AlertSignalReject */
  const handleRejectOpen = useCallback((signal, signalType) => {
    setRejectModal({ open: true, signal, signalType });
  }, []);

  const handleRejectClose = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleRejectSuccess = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
    mutateAll();
    displaySuccessSnackbar("Signal rejected");
  }, [mutateAll]);

  /** Validate inline — no modal needed */
  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        mutateAll();
        displaySuccessSnackbar("Signal validated");
      } else {
        displayErrorSnackbar(result.error || "Failed to validate signal");
      }
    },
    [mutateAll],
  );

  /** Delete — no confirmation modal for MVP (destructive but signals are cheap to recreate) */
  const handleDelete = useCallback(
    async (signal, signalType) => {
      const result = await deleteSignal(signalType, signal.id);
      if (result.success) {
        mutateAll();
        displaySuccessSnackbar("Signal deleted");
      } else {
        displayErrorSnackbar(result.error || "Failed to delete signal");
      }
    },
    [mutateAll],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* ==================== TOOLBAR ==================== */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={2}
        alignItems={{ xs: "stretch", sm: "center" }}
        justifyContent="space-between"
        sx={{ mb: 2 }}
      >
        {/* Left: type toggle + status filter + search */}
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1.5}
          alignItems="center"
        >
          {/* Signal type toggle */}
          <ToggleButtonGroup
            value={typeFilter}
            exclusive
            onChange={handleTypeChange}
            size="small"
            aria-label="Filter by signal type"
          >
            {TYPE_OPTIONS.map((opt) => (
              <ToggleButton
                key={opt.value}
                value={opt.value}
                sx={{ textTransform: "none", px: 1.5 }}
              >
                {opt.label}
                {counts[opt.value] > 0 && (
                  <Chip
                    label={counts[opt.value]}
                    size="small"
                    sx={{
                      ml: 0.75,
                      height: 18,
                      fontSize: "0.65rem",
                      pointerEvents: "none",
                    }}
                  />
                )}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>

          {/* Status filter */}
          <Select
            value={statusFilter}
            onChange={handleStatusChange}
            size="small"
            displayEmpty
            sx={{ minWidth: 140 }}
          >
            {STATUS_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>

          {/* Search */}
          <TextField
            size="small"
            placeholder="Search signals…"
            value={search}
            onChange={handleSearchChange}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchOutlined style={{ fontSize: 14 }} />
                </InputAdornment>
              ),
            }}
            sx={{ minWidth: 200 }}
          />
        </Stack>

        {/* Right: add button */}
        <Button
          variant="contained"
          startIcon={<PlusOutlined />}
          onClick={handleAdd}
          size="small"
        >
          Add Signal
        </Button>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* ==================== SIGNAL LIST ==================== */}
      <SignalList
        signals={signals}
        loading={isLoading}
        error={hasError}
        onValidate={handleValidate}
        onReject={handleRejectOpen}
        onEdit={handleEdit}
        onSupersede={handleSupersede}
        onDelete={handleDelete}
        emptyMessage={
          search || statusFilter
            ? "No signals match your filters"
            : "No signals yet for this account"
        }
        emptyDescription={
          !search && !statusFilter
            ? "Add a signal manually or extract them from a call transcript"
            : undefined
        }
      />

      {/* ==================== MODALS ==================== */}

      {/* Create / Supersede */}
      <FormSignalAdd
        open={addModal.open}
        onClose={handleAddClose}
        onSuccess={handleAddSuccess}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
        supersedeTarget={addModal.supersedeTarget}
      />

      {/* Edit (PATCH) */}
      <FormSignalEdit
        open={editModal.open}
        onClose={handleEditClose}
        onSuccess={handleEditSuccess}
        signal={editModal.signal}
        signalType={editModal.signalType}
        choices={choices}
        choicesLoading={choicesLoading}
      />

      {/* Reject confirmation */}
      <AlertSignalReject
        open={rejectModal.open}
        onClose={handleRejectClose}
        onSuccess={handleRejectSuccess}
        signal={rejectModal.signal}
        signalType={rejectModal.signalType}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

AccountSignalsTab.propTypes = {
  /** Account UUID — required to scope all signal fetches */
  accountId: PropTypes.string.isRequired,
  /** Full account object — passed to FormSignalAdd for display context */
  account: PropTypes.object,
};
