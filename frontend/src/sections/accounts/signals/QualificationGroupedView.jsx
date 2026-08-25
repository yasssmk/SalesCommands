// frontend/src/sections/accounts/signals/QualificationGroupedView.jsx
/**
 * QualificationGroupedView — the grouped "Qualification" synthesis surface.
 *
 * A reusable container parameterised by SURFACE and SCOPE, rendered as a
 * separate tab alongside the flat "Signals" tab on both the Account and the
 * Decision-Cycle workspaces.
 *
 * Sections
 * --------
 *   1. QUALIFICATION CLUSTERS — the clustered pain / objective / impact
 *      signals (real clusters from SignalClusterService), scoped to the
 *      account (Account surface) or to the decision cycle (DC surface).
 *      Each cluster renders as a SignalClusterCard (priority, freshness,
 *      lifecycle); clicking it opens the SignalClusterDetailDrawer, where
 *      members render as shared SignalLine rows with full CRUD (validate /
 *      reject / edit / reopen) and a per-member quick drawer showing the
 *      source quote + origin-activity link.
 *   2. TECH STACK — a typed section (NOT clustered): the account's / cycle's
 *      tech-stack signals, fetched via the aggregated endpoint with a
 *      signal_type filter and rendered as SignalLine rows.
 *   3. BLOCKERS — DC surface ONLY, a typed section of the cycle's blocker
 *      signals. Never shown on the Account surface (blockers are
 *      deal-scoped, not durable account facts).
 *
 * Surface differences
 * -------------------
 *   Account : clusters + tech
 *   DC      : clusters + tech + blockers
 *
 * Empty states are neutral information, never error styling. Technical
 * failures use the standard error surface.
 */

"use client";

import PropTypes from "prop-types";
import { useCallback, useMemo, useState } from "react";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { InboxOutlined } from "@ant-design/icons";

// project imports
import SignalClusterCard from "components/cards/signals/SignalClusterCard";
import SignalClusterDetailDrawer from "./SignalClusterDetailDrawer";
import AlertSignalReject from "./AlertSignalReject";
import SignalEditDialog from "./SignalEditDialog";
import SignalLine from "components/signals/SignalLine";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";

import {
  useGetClustersByAccount,
  archiveCluster,
  unarchiveCluster,
} from "api/signals/signalClusters";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import {
  useGetSignalChoices,
  validateSignal,
  reopenSignal,
} from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// The qualification section always groups all three clusterable types.
const CLUSTER_TYPES = ["pain", "objective", "impact"];
const SECTION_PAGE_SIZE = 100;

// ==============================|| SMALL PRESENTATION HELPERS ||============================== //

function SectionHeader({ title, count }) {
  return (
    <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
      {title}
      {count > 0 && (
        <Typography
          component="span"
          variant="caption"
          color="text.secondary"
          sx={{ ml: 1 }}
        >
          ({count})
        </Typography>
      )}
    </Typography>
  );
}

SectionHeader.propTypes = {
  title: PropTypes.string.isRequired,
  count: PropTypes.number,
};

function NeutralEmpty({ label }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      sx={{
        py: 3,
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        borderStyle: "dashed",
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

NeutralEmpty.propTypes = {
  label: PropTypes.string.isRequired,
};

/**
 * A typed (non-clustered) section: a titled list of SignalLine rows for a
 * single signal type. Used for Tech Stack and Blockers.
 */
function TypedSignalSection({
  title,
  signals,
  loading,
  error,
  emptyLabel,
  onSelect,
  onValidate,
  onReject,
  onEdit,
  onReopen,
}) {
  if (error) {
    return (
      <Box>
        <SectionHeader title={title} />
        <Typography variant="body2" color="error" sx={{ py: 1 }}>
          Failed to load {title.toLowerCase()}.
        </Typography>
      </Box>
    );
  }

  if (loading && signals.length === 0) {
    return (
      <Box>
        <SectionHeader title={title} />
        <Stack alignItems="center" py={2}>
          <CircularProgress size={20} />
        </Stack>
      </Box>
    );
  }

  return (
    <Box>
      <SectionHeader title={title} count={signals.length} />
      {signals.length === 0 ? (
        <NeutralEmpty label={emptyLabel} />
      ) : (
        <Stack spacing={0.5}>
          {signals.map((signal) => (
            <SignalLine
              key={signal.id}
              signal={signal}
              signalType={signal._signalType}
              onSelect={onSelect}
              onValidate={onValidate}
              onReject={onReject}
              onEdit={onEdit}
              onReopen={onReopen}
            />
          ))}
        </Stack>
      )}
    </Box>
  );
}

TypedSignalSection.propTypes = {
  title: PropTypes.string.isRequired,
  signals: PropTypes.array.isRequired,
  loading: PropTypes.bool,
  error: PropTypes.any,
  emptyLabel: PropTypes.string.isRequired,
  onSelect: PropTypes.func,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
};

// ==============================|| QUALIFICATION GROUPED VIEW ||============================== //

export default function QualificationGroupedView({
  surface,
  accountId,
  decisionCycleId,
}) {
  const isDC = surface === "dc";

  // ---- Clusters (pain / objective / impact) ----
  const { clusters, clustersLoading, clustersError, mutateClusters } =
    useGetClustersByAccount(accountId, {
      signalType: CLUSTER_TYPES,
      decisionCycleId: isDC ? decisionCycleId : undefined,
    });

  // ---- Typed sections via the aggregated endpoint ----
  // Tech: scoped to the account (Account) or the decision cycle (DC).
  const tech = useAggregatedSignals({
    accountId: isDC ? undefined : accountId,
    decisionCycleId: isDC ? decisionCycleId : undefined,
    signalTypes: ["tech-stack"],
    pageSize: SECTION_PAGE_SIZE,
  });

  // Blockers: DC surface only. On the Account surface the scope is null so
  // the hook stays disabled (and the section is not rendered anyway).
  const blockers = useAggregatedSignals({
    decisionCycleId: isDC ? decisionCycleId : undefined,
    signalTypes: ["blockers"],
    pageSize: SECTION_PAGE_SIZE,
  });

  const { choices, choicesLoading } = useGetSignalChoices();

  const mutateSections = useCallback(() => {
    tech.mutate();
    blockers.mutate();
  }, [tech, blockers]);

  // ---- Cluster drawer state ----
  const [clusterDrawer, setClusterDrawer] = useState({
    open: false,
    summary: null,
  });

  const handleClusterClick = useCallback((cluster) => {
    setClusterDrawer({ open: true, summary: cluster });
  }, []);

  const handleClusterDrawerClose = useCallback(() => {
    setClusterDrawer({ open: false, summary: null });
  }, []);

  const handleArchive = useCallback(
    async (cluster) => {
      const result = await archiveCluster({
        account: accountId,
        canonicalKey: cluster.canonical_key,
        signalType: cluster.signal_type,
      });
      if (result.success) {
        mutateClusters();
        displaySuccessSnackbar("Cluster archived");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [accountId, mutateClusters],
  );

  const handleUnarchive = useCallback(
    async (cluster) => {
      const result = await unarchiveCluster({
        account: accountId,
        canonicalKey: cluster.canonical_key,
        signalType: cluster.signal_type,
      });
      if (result.success) {
        mutateClusters();
        displaySuccessSnackbar("Cluster unarchived");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [accountId, mutateClusters],
  );

  // ---- Typed-section CRUD (tech / blockers) ----
  const [memberDrawer, setMemberDrawer] = useState({
    open: false,
    signal: null,
    signalType: null,
  });
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

  const handleSelect = useCallback((signal, signalType) => {
    setMemberDrawer({ open: true, signal, signalType });
  }, []);

  const handleDrawerClose = useCallback(() => {
    setMemberDrawer({ open: false, signal: null, signalType: null });
  }, []);

  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal validated");
        mutateSections();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateSections],
  );

  const handleReopen = useCallback(
    async (signal, signalType) => {
      const result = await reopenSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateSections();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateSections],
  );

  const handleRejectOpen = useCallback((signal, signalType) => {
    setRejectModal({ open: true, signal, signalType });
  }, []);

  const handleRejectClose = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleRejectSuccess = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
    displaySuccessSnackbar("Signal rejected");
    mutateSections();
  }, [mutateSections]);

  const handleEditOpen = useCallback((signal, signalType) => {
    setEditModal({ open: true, signal, signalType });
  }, []);

  const handleEditClose = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleEditSuccess = useCallback(() => {
    mutateSections();
  }, [mutateSections]);

  const clusterList = useMemo(() => clusters ?? [], [clusters]);

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Left column — Qualification clusters */}
        <Grid item xs={12} md={7}>
          <SectionHeader title="Qualification" count={clusterList.length} />

          {clustersError ? (
            <Typography variant="body2" color="error" sx={{ py: 1 }}>
              Failed to load qualification clusters.
            </Typography>
          ) : clustersLoading && clusterList.length === 0 ? (
            <Stack alignItems="center" py={3}>
              <CircularProgress size={22} />
            </Stack>
          ) : clusterList.length === 0 ? (
            <Box
              display="flex"
              flexDirection="column"
              alignItems="center"
              gap={1}
              sx={{
                py: 5,
                border: 1,
                borderColor: "divider",
                borderRadius: 1.5,
                borderStyle: "dashed",
              }}
            >
              <InboxOutlined style={{ fontSize: 32, color: "#bfbfbf" }} />
              <Typography variant="body2" color="text.secondary">
                No qualification clusters yet
              </Typography>
              <Typography variant="caption" color="text.disabled">
                Pain, Objective and Impact signals group automatically here.
              </Typography>
            </Box>
          ) : (
            <Stack spacing={1.5}>
              {clusterList.map((cluster) => (
                <SignalClusterCard
                  key={`${cluster.signal_type}:${cluster.canonical_key}`}
                  cluster={cluster}
                  onClick={handleClusterClick}
                  onArchive={handleArchive}
                  onUnarchive={handleUnarchive}
                />
              ))}
            </Stack>
          )}
        </Grid>

        {/* Right column — typed sections */}
        <Grid item xs={12} md={5}>
          <TypedSignalSection
            title="Tech Stack"
            signals={tech.signals}
            loading={tech.loading}
            error={tech.error}
            emptyLabel="No tech stack signals captured"
            onSelect={handleSelect}
            onValidate={handleValidate}
            onReject={handleRejectOpen}
            onEdit={handleEditOpen}
            onReopen={handleReopen}
          />

          {isDC && (
            <>
              <Divider sx={{ my: 3 }} />
              <TypedSignalSection
                title="Blockers"
                signals={blockers.signals}
                loading={blockers.loading}
                error={blockers.error}
                emptyLabel="No blockers or objections captured"
                onSelect={handleSelect}
                onValidate={handleValidate}
                onReject={handleRejectOpen}
                onEdit={handleEditOpen}
                onReopen={handleReopen}
              />
            </>
          )}
        </Grid>
      </Grid>

      {/* Cluster detail drawer — self-contained member CRUD (incl. reopen) */}
      <SignalClusterDetailDrawer
        open={clusterDrawer.open}
        onClose={handleClusterDrawerClose}
        clusterSummary={clusterDrawer.summary}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
        onClusterChange={mutateClusters}
      />

      {/* Typed-section member drawer + modals */}
      <SignalQuickDrawer
        open={memberDrawer.open}
        signal={memberDrawer.signal}
        signalType={memberDrawer.signalType}
        onClose={handleDrawerClose}
        onValidate={handleValidate}
        onReject={handleRejectOpen}
        onEdit={handleEditOpen}
      />

      <AlertSignalReject
        open={rejectModal.open}
        onClose={handleRejectClose}
        onSuccess={handleRejectSuccess}
        signal={rejectModal.signal}
        signalType={rejectModal.signalType}
      />

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
    </Box>
  );
}

QualificationGroupedView.propTypes = {
  /** "account" → clusters + tech; "dc" → clusters + tech + blockers */
  surface: PropTypes.oneOf(["account", "dc"]).isRequired,
  /** Account UUID — required on both surfaces (clusters are account-scoped). */
  accountId: PropTypes.string.isRequired,
  /** Decision-cycle UUID — required on the DC surface. */
  decisionCycleId: PropTypes.string,
};
