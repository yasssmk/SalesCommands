// frontend/src/sections/accounts/workspace/AccountSignalsTab.jsx
/**
 * AccountSignalsTab — container for the Signals tab in Account Workspace.
 *
 * Responsibilities:
 *   - Fetch all 4 signal types for the account (4 SWR calls)
 *   - Own all modal/drawer states (wizard add, reject)
 *   - Dispatch validate / reject / delete to the API layer
 *   - Render one SignalList at a time based on the active section
 *   - Status filter applied server-side via SWR filters
 *
 * Edit is deferred from MVP — onEdit handler is a no-op with a TODO.
 * Modal state lives here so it persists across open/close cycles.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// ant-design icons
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import SignalList from "../signals/SignalList";
import AlertSignalReject from "../signals/AlertSignalReject";
import SignalEditDialog from "../signals/SignalEditDialog";
import SignalClusterDetailDrawer from "../signals/SignalClusterDetailDrawer";
import WizardSignalAdd from "../signals/wizard/WizardSignalAdd";
import SignalClusterCard from "components/cards/signals/SignalClusterCard";

import {
  useGetSignalsByAccount,
  useGetSignalChoices,
  validateSignal,
  deleteSignal,
} from "api/signals/signals";
import {
  useGetClustersByAccount,
  archiveCluster,
  unarchiveCluster,
} from "api/signals/signalClusters";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

/** Section toggle options — 4 signal types */
const TYPE_OPTIONS = [
  { value: "people", label: "People" },
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "tech-stack", label: "Tech Stack" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "PENDING", label: "Pending" },
  { value: "VALIDATED", label: "Validated" },
  { value: "REJECTED", label: "Rejected" },
];

// ==============================|| PAIN CLUSTERS SECTION ||============================== //

/**
 * Dedicated renderer for the Pain cluster grid.
 *
 * Encapsulates the three states (loading / error / empty / list) so the
 * main tab render stays readable. Kept in the same file because it is
 * tightly coupled to the tab's state/handlers and has no other caller.
 */
function PainClustersSection({
  clusters,
  loading,
  error,
  includeArchived,
  onClusterClick,
  onClusterArchive,
  onClusterUnarchive,
}) {
  if (loading) {
    return (
      <Stack spacing={1.5}>
        <Skeleton variant="rounded" height={180} />
        <Skeleton variant="rounded" height={180} />
      </Stack>
    );
  }

  if (error) {
    return (
      <Stack alignItems="center" py={6} spacing={1}>
        <Typography variant="body2" color="error">
          Failed to load pain clusters. Please refresh and try again.
        </Typography>
      </Stack>
    );
  }

  if (!clusters || clusters.length === 0) {
    return (
      <Stack alignItems="center" py={6} spacing={1.5}>
        <InboxOutlined style={{ fontSize: 36, color: "#bfbfbf" }} />
        <Typography variant="body1" color="text.secondary" fontWeight={500}>
          {includeArchived
            ? "No pain clusters for this account"
            : "No active pain clusters for this account"}
        </Typography>
        <Typography
          variant="body2"
          color="text.disabled"
          textAlign="center"
          maxWidth={380}
        >
          Pain signals recorded from calls group automatically into canonical
          clusters. Capture a few pains via the wizard to see them surface here.
        </Typography>
      </Stack>
    );
  }

  return (
    <Stack spacing={1.5}>
      {clusters.map((cluster) => (
        <SignalClusterCard
          key={cluster.canonical_key}
          cluster={cluster}
          onClick={onClusterClick}
          onArchive={onClusterArchive}
          onUnarchive={onClusterUnarchive}
        />
      ))}
      <Stack direction="row" justifyContent="flex-end" sx={{ pt: 0.5 }}>
        <Chip
          label={`${clusters.length} cluster${
            clusters.length === 1 ? "" : "s"
          }`}
          size="small"
          variant="outlined"
          sx={{ fontSize: "0.7rem" }}
        />
      </Stack>
    </Stack>
  );
}

PainClustersSection.propTypes = {
  clusters: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.any,
  includeArchived: PropTypes.bool,
  onClusterClick: PropTypes.func.isRequired,
  onClusterArchive: PropTypes.func.isRequired,
  onClusterUnarchive: PropTypes.func.isRequired,
};

// ==============================|| ACCOUNT SIGNALS TAB ||============================== //

/**
 * AccountSignalsTab
 *
 * @param {string} accountId - Account UUID (required)
 * @param {Object} account   - Full account object (optional, for form context)
 */
export default function AccountSignalsTab({ accountId, account }) {
  // ==============================|| FILTER STATE ||============================== //

  const [activeType, setActiveType] = useState("pain");
  const [statusFilter, setStatusFilter] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

  // ==============================|| MODAL STATE ||============================== //

  const [wizardOpen, setWizardOpen] = useState(false);

  const [rejectModal, setRejectModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  const [editModal, setEditModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  /**
   * Cluster drill-down drawer state — only used when activeType === 'pain'.
   */
  const [clusterDrawer, setClusterDrawer] = useState({
    open: false,
    clusterSummary: null,
  });

  // ==============================|| DATA FETCHING ||============================== //

  const sharedFilters = useMemo(
    () => ({ status: statusFilter || undefined }),
    [statusFilter],
  );

  const sharedOptions = useMemo(
    () => ({ ordering: "-created_at", filters: sharedFilters }),
    [sharedFilters],
  );

  const {
    signals: peopleSignals,
    signalsLoading: peopleLoading,
    signalsError: peopleError,
    mutateSignals: mutatePeople,
  } = useGetSignalsByAccount(accountId, "people", sharedOptions);

  /**
   * Pain uses the cluster endpoint instead of the individual signal list.
   * The Wizard still creates individual PainSignals — they are routed
   * into clusters automatically by canonical_key, which is why we still
   * need `mutatePain`-style invalidation after a Wizard success. The
   * cluster cache layer (api/signals/signalClusters.js) already revalidates
   * the pain list prefix, so calling `mutateClusters` after Wizard success
   * is sufficient.
   */
  const {
    clusters: painClusters,
    clustersLoading: painLoading,
    clustersError: painError,
    mutateClusters: mutatePainClusters,
  } = useGetClustersByAccount(accountId, {
    signalType: "pain",
    includeArchived,
  });

  const {
    signals: objectiveSignals,
    signalsLoading: objectiveLoading,
    signalsError: objectiveError,
    mutateSignals: mutateObjective,
  } = useGetSignalsByAccount(accountId, "objective", sharedOptions);

  const {
    signals: techSignals,
    signalsLoading: techLoading,
    signalsError: techError,
    mutateSignals: mutateTech,
  } = useGetSignalsByAccount(accountId, "tech-stack", sharedOptions);

  const { choices, choicesLoading } = useGetSignalChoices();

  // ==============================|| DERIVED ||============================== //

  /**
   * Revalidate all 4 sections — called after any write.
   * Pain now lives on the cluster endpoint, so we invalidate the cluster
   * cache instead of the individual pain list. The cluster cache layer
   * revalidates the underlying pain list transitively.
   */
  const mutateAll = useCallback(() => {
    mutatePeople();
    mutatePainClusters();
    mutateObjective();
    mutateTech();
  }, [mutatePeople, mutatePainClusters, mutateObjective, mutateTech]);

  /**
   * Counts per type — shown as badges in the section toggle.
   * Pain count = number of non-archived clusters (per product decision D3).
   * Archived clusters are only counted when includeArchived is on, which
   * matches what the user sees on the listing.
   */
  const counts = useMemo(
    () => ({
      people: peopleSignals.length,
      pain: painClusters.length,
      objective: objectiveSignals.length,
      "tech-stack": techSignals.length,
    }),
    [peopleSignals, painClusters, objectiveSignals, techSignals],
  );

  /**
   * Active section data.
   * Pain returns an empty `signals` array on purpose — the Pain section
   * renders a cluster grid rather than a SignalList. The `loading` and
   * `error` fields remain used by the Pain custom render.
   */
  const activeData = useMemo(() => {
    switch (activeType) {
      case "people":
        return {
          signals: peopleSignals,
          loading: peopleLoading,
          error: peopleError,
        };
      case "pain":
        return {
          signals: [],
          loading: painLoading,
          error: painError,
        };
      case "objective":
        return {
          signals: objectiveSignals,
          loading: objectiveLoading,
          error: objectiveError,
        };
      case "tech-stack":
        return {
          signals: techSignals,
          loading: techLoading,
          error: techError,
        };
      default:
        return { signals: [], loading: false, error: null };
    }
  }, [
    activeType,
    peopleSignals,
    peopleLoading,
    peopleError,
    painLoading,
    painError,
    objectiveSignals,
    objectiveLoading,
    objectiveError,
    techSignals,
    techLoading,
    techError,
  ]);

  // ==============================|| FILTER HANDLERS ||============================== //

  const handleTypeChange = useCallback((_e, newValue) => {
    if (newValue !== null) setActiveType(newValue);
  }, []);

  const handleStatusChange = useCallback((e) => {
    setStatusFilter(e.target.value);
  }, []);

  // ==============================|| ACTION HANDLERS ||============================== //

  const handleWizardOpen = useCallback(() => {
    setWizardOpen(true);
  }, []);

  const handleWizardClose = useCallback(() => {
    setWizardOpen(false);
  }, []);

  const handleWizardSuccess = useCallback(() => {
    mutateAll();
    // Wizard closes itself on full success
  }, [mutateAll]);

  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        mutateAll();
        displaySuccessSnackbar("Signal validated");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

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

  const handleEdit = useCallback((signal, signalType) => {
    setEditModal({ open: true, signal, signalType });
  }, []);

  const handleEditClose = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleEditSuccess = useCallback(() => {
    mutateAll();
    // Dialog closes itself on success
  }, [mutateAll]);

  const handleDelete = useCallback(
    async (signal, signalType) => {
      const result = await deleteSignal(signalType, signal.id);
      if (result.success) {
        mutateAll();
        displaySuccessSnackbar("Signal deleted");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  // ==============================|| CLUSTER HANDLERS ||============================== //

  /**
   * Open the drill-down drawer for a cluster.
   * The clusterSummary is the list item payload — the drawer fetches
   * its own detail separately.
   */
  const handleClusterClick = useCallback((cluster) => {
    setClusterDrawer({ open: true, clusterSummary: cluster });
  }, []);

  const handleClusterDrawerClose = useCallback(() => {
    setClusterDrawer({ open: false, clusterSummary: null });
  }, []);

  /**
   * Called by the drawer whenever a mutation changes cluster data
   * (archive, unarchive, member validation, member edit, impact CRUD).
   * We only need to revalidate the cluster list here — the drawer
   * revalidates its own detail internally.
   */
  const handleClusterChange = useCallback(() => {
    mutatePainClusters();
  }, [mutatePainClusters]);

  /**
   * Archive a cluster from the card overflow menu (no drawer open).
   * Identical logic to the drawer's archive, but initiated from the list.
   */
  const handleClusterArchive = useCallback(
    async (cluster) => {
      const result = await archiveCluster({
        account: accountId,
        canonicalKey: cluster.canonical_key,
        signalType: cluster.signal_type,
      });
      if (result.success) {
        mutatePainClusters();
        displaySuccessSnackbar("Cluster archived");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [accountId, mutatePainClusters],
  );

  const handleClusterUnarchive = useCallback(
    async (cluster) => {
      const result = await unarchiveCluster({
        account: accountId,
        canonicalKey: cluster.canonical_key,
        signalType: cluster.signal_type,
      });
      if (result.success) {
        mutatePainClusters();
        displaySuccessSnackbar("Cluster unarchived");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [accountId, mutatePainClusters],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* ==================== TOOLBAR ==================== */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ xs: "stretch", sm: "center" }}
        justifyContent="space-between"
        sx={{ mb: 2 }}
      >
        {/* Left: section toggle + status filter */}
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1.5}
          alignItems="center"
        >
          {/* Section toggle */}
          <ToggleButtonGroup
            value={activeType}
            exclusive
            onChange={handleTypeChange}
            size="small"
            aria-label="Signal section"
          >
            {TYPE_OPTIONS.map((opt) => (
              <ToggleButton
                key={opt.value}
                value={opt.value}
                sx={{ textTransform: "none", px: 1.5, fontSize: "0.78rem" }}
              >
                {opt.label}
                {counts[opt.value] > 0 && (
                  <Chip
                    label={counts[opt.value]}
                    size="small"
                    sx={{
                      ml: 0.75,
                      height: 18,
                      fontSize: "0.62rem",
                      pointerEvents: "none",
                    }}
                  />
                )}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>

          {/*
            Status filter — hidden on Pain because clusters don't expose
            a status filter (they aggregate VALIDATED + PENDING members
            natively and surface the mix via has_pending_signals). On
            the other three types, it remains useful.
          */}
          {activeType !== "pain" && (
            <Select
              value={statusFilter}
              onChange={handleStatusChange}
              size="small"
              displayEmpty
              sx={{ minWidth: 140, fontSize: "0.82rem" }}
            >
              {STATUS_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          )}

          {/*
            Show-archived toggle — only on Pain. Hidden for the other
            three types since they don't have a cluster-level archival
            concept yet.
          */}
          {activeType === "pain" && (
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={includeArchived}
                  onChange={(e) => setIncludeArchived(e.target.checked)}
                  inputProps={{ "aria-label": "Show archived clusters" }}
                />
              }
              label={
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <InboxOutlined style={{ fontSize: 12 }} />
                  <Typography variant="caption" color="text.secondary">
                    Show archived
                  </Typography>
                </Stack>
              }
              sx={{ m: 0 }}
            />
          )}
        </Stack>

        {/* Right: add button — opens wizard on the active section */}
        <Button
          variant="contained"
          size="small"
          startIcon={<PlusOutlined />}
          onClick={handleWizardOpen}
        >
          Add Signal
        </Button>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* ==================== ACTIVE SECTION ==================== */}
      {activeType === "pain" ? (
        <PainClustersSection
          clusters={painClusters}
          loading={painLoading}
          error={painError}
          includeArchived={includeArchived}
          onClusterClick={handleClusterClick}
          onClusterArchive={handleClusterArchive}
          onClusterUnarchive={handleClusterUnarchive}
        />
      ) : (
        <SignalList
          signals={activeData.signals}
          signalType={activeType}
          loading={activeData.loading}
          error={activeData.error}
          onValidate={handleValidate}
          onReject={handleRejectOpen}
          onEdit={handleEdit}
          onDelete={handleDelete}
          emptyMessage={
            statusFilter
              ? `No ${activeType} signals match this status`
              : `No ${activeType} signals yet for this account`
          }
          emptyDescription={
            !statusFilter
              ? "Open the wizard to capture signals from a conversation"
              : undefined
          }
        />
      )}

      {/* ==================== MODALS / DRAWERS ==================== */}

      {/* Signal capture wizard */}
      <WizardSignalAdd
        open={wizardOpen}
        onClose={handleWizardClose}
        onSuccess={handleWizardSuccess}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
        defaultSection={activeType}
      />

      {/* Reject confirmation */}
      <AlertSignalReject
        open={rejectModal.open}
        onClose={handleRejectClose}
        onSuccess={handleRejectSuccess}
        signal={rejectModal.signal}
        signalType={rejectModal.signalType}
      />

      {/* Edit dialog */}
      <SignalEditDialog
        open={editModal.open}
        onClose={handleEditClose}
        onSuccess={handleEditSuccess}
        signal={editModal.signal}
        signalType={editModal.signalType}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
      />

      {/* Cluster drill-down drawer — Pain only */}
      <SignalClusterDetailDrawer
        open={clusterDrawer.open}
        onClose={handleClusterDrawerClose}
        clusterSummary={clusterDrawer.clusterSummary}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
        onClusterChange={handleClusterChange}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

AccountSignalsTab.propTypes = {
  accountId: PropTypes.string.isRequired,
  account: PropTypes.object,
};
