// frontend/src/sections/accounts/signals/QualificationGroupedView.jsx
/**
 * QualificationGroupedView — the rich DC / Account Qualification synthesis.
 *
 * Three narrative sections — Objectives / Pains / Impacts — each nesting the
 * account's (or cycle's) clusters by DOMAIN (what) → DIMENSION → CLUSTER. One
 * row = one cluster (flat cluster list from the service, nested client-side).
 * Below them, the Tech Stack and Objections sections show their PLACEMENT with
 * today's simple flat content (future tech clustering is a later step).
 *
 * All sections — and the domain groups inside the narrative sections — are
 * collapsible (CollapsibleSection / MUI Accordion), open by default; open state
 * is component state only (no browser storage).
 *
 * Surface:
 *   account → clusters scoped to the account; DC count shown on rows; Tech only.
 *   dc      → clusters scoped to the decision cycle; DC count hidden; Tech +
 *             Objections (blockers are deal-scoped).
 *
 * Cluster rows are informational — clicking opens the cluster drawer. Tech /
 * objection rows are informational too — clicking opens the shared signal
 * drawer where their actions live.
 */

"use client";

import PropTypes from "prop-types";
import { useCallback, useMemo, useState } from "react";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import ClusterRow from "./ClusterRow";
import SignalClusterDetailDrawer from "./SignalClusterDetailDrawer";
import AlertSignalReject from "./AlertSignalReject";
import SignalEditDialog from "./SignalEditDialog";
import CollapsibleSection from "components/signals/CollapsibleSection";
import SignalLine from "components/signals/SignalLine";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";

import { useGetClustersByAccount } from "api/signals/signalClusters";
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

// The three narrative sections, in reading order.
const SECTIONS = [
  { type: "objective", title: "Objectives" },
  { type: "pain", title: "Pains" },
  { type: "impact", title: "Impacts" },
];
const CLUSTER_TYPES = SECTIONS.map((s) => s.type);
const GROUPED_STATUSES = ["PENDING", "VALIDATED"];
const SECTION_PAGE_SIZE = 100;

// ==============================|| NESTING ||============================== //

/**
 * Nest a flat, priority-sorted cluster list into domain → dimension groups.
 * Insertion order is preserved (clusters arrive priority-sorted).
 */
function nestByDomainDimension(clusters) {
  const domains = new Map();
  for (const c of clusters) {
    if (!domains.has(c.what)) {
      domains.set(c.what, {
        what: c.what,
        whatLabel: c.what_display || c.what || "—",
        dims: new Map(),
      });
    }
    const dom = domains.get(c.what);
    if (!dom.dims.has(c.dimension)) {
      dom.dims.set(c.dimension, {
        dimension: c.dimension,
        dimLabel: c.dimension_display || c.dimension || "—",
        clusters: [],
      });
    }
    dom.dims.get(c.dimension).clusters.push(c);
  }
  return [...domains.values()].map((d) => ({
    ...d,
    dims: [...d.dims.values()],
  }));
}

// ==============================|| PRESENTATION HELPERS ||============================== //

function NeutralEmpty({ label }) {
  return (
    <Box
      sx={{
        py: 2.5,
        px: 2,
        textAlign: "center",
        border: 1,
        borderColor: "divider",
        borderStyle: "dashed",
        borderRadius: 1.5,
        mb: 1,
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

NeutralEmpty.propTypes = { label: PropTypes.string.isRequired };

/**
 * One narrative section (collapsible), its clusters nested by domain
 * (collapsible) → dimension → cluster rows.
 */
function NarrativeSection({ title, clusters, surface, onClusterClick }) {
  const domains = useMemo(() => nestByDomainDimension(clusters), [clusters]);

  return (
    <CollapsibleSection
      title={title}
      count={clusters.length}
      level="section"
      testId={`section-${title.toLowerCase()}`}
    >
      {domains.length === 0 ? (
        <NeutralEmpty label={`No ${title.toLowerCase()} yet`} />
      ) : (
        domains.map((dom) => {
          const domainCount = dom.dims.reduce(
            (n, d) => n + d.clusters.length,
            0,
          );
          return (
            <CollapsibleSection
              key={dom.what}
              title={dom.whatLabel}
              count={domainCount}
              level="domain"
              testId={`domain-${dom.what}`}
            >
              {dom.dims.map((dim) => (
                <Box key={dim.dimension} sx={{ mb: 1.5 }}>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: "block", mb: 0.75, fontWeight: 600 }}
                  >
                    {dim.dimLabel}
                  </Typography>
                  {dim.clusters.map((cluster) => (
                    <ClusterRow
                      key={`${cluster.signal_type}:${cluster.canonical_key}`}
                      cluster={cluster}
                      surface={surface}
                      onClick={onClusterClick}
                    />
                  ))}
                </Box>
              ))}
            </CollapsibleSection>
          );
        })
      )}
    </CollapsibleSection>
  );
}

NarrativeSection.propTypes = {
  title: PropTypes.string.isRequired,
  clusters: PropTypes.array.isRequired,
  surface: PropTypes.oneOf(["account", "dc"]).isRequired,
  onClusterClick: PropTypes.func.isRequired,
};

/**
 * A typed (non-clustered) section — Tech Stack / Objections — shown with
 * today's flat content. Collapsible, open by default. Rows are informational.
 */
function TypedSection({ title, testId, emptyLabel, signals, loading, onSelect }) {
  return (
    <CollapsibleSection
      title={title}
      count={signals.length}
      level="section"
      testId={testId}
    >
      {loading && signals.length === 0 ? (
        <Stack alignItems="center" py={2}>
          <CircularProgress size={18} />
        </Stack>
      ) : signals.length === 0 ? (
        <NeutralEmpty label={emptyLabel} />
      ) : (
        <Stack spacing={0}>
          {signals.map((signal) => (
            <SignalLine
              key={signal.id}
              signal={signal}
              signalType={signal._signalType}
              onSelect={onSelect}
              showTypeChip={false}
            />
          ))}
        </Stack>
      )}
    </CollapsibleSection>
  );
}

TypedSection.propTypes = {
  title: PropTypes.string.isRequired,
  testId: PropTypes.string.isRequired,
  emptyLabel: PropTypes.string.isRequired,
  signals: PropTypes.array.isRequired,
  loading: PropTypes.bool,
  onSelect: PropTypes.func,
};

// ==============================|| QUALIFICATION GROUPED VIEW ||============================== //

export default function QualificationGroupedView({
  surface,
  accountId,
  decisionCycleId,
}) {
  const isDC = surface === "dc";

  const { clusters, clustersLoading, clustersError, mutateClusters } =
    useGetClustersByAccount(accountId, {
      signalType: CLUSTER_TYPES,
      decisionCycleId: isDC ? decisionCycleId : undefined,
    });

  // Tech: scoped to the account (Account) or the decision cycle (DC).
  const tech = useAggregatedSignals({
    accountId: isDC ? undefined : accountId,
    decisionCycleId: isDC ? decisionCycleId : undefined,
    signalTypes: ["tech-stack"],
    statuses: GROUPED_STATUSES,
    pageSize: SECTION_PAGE_SIZE,
  });

  // Objections (blockers): DC surface only.
  const blockers = useAggregatedSignals({
    decisionCycleId: isDC ? decisionCycleId : undefined,
    signalTypes: ["blockers"],
    statuses: GROUPED_STATUSES,
    pageSize: SECTION_PAGE_SIZE,
  });

  const { choices, choicesLoading } = useGetSignalChoices();

  const mutateSections = useCallback(() => {
    tech.mutate();
    blockers.mutate();
  }, [tech, blockers]);

  // Split the flat cluster list into the three narrative sections.
  const bySection = useMemo(() => {
    const map = { objective: [], pain: [], impact: [] };
    for (const c of clusters ?? []) {
      if (map[c.signal_type]) map[c.signal_type].push(c);
    }
    return map;
  }, [clusters]);

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

  // ---- Typed-section member drawer + modals ----
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

  if (clustersError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <Typography color="error">Failed to load qualification clusters</Typography>
      </Box>
    );
  }

  if (clustersLoading && (clusters ?? []).length === 0) {
    return (
      <Stack alignItems="center" py={5}>
        <CircularProgress size={22} />
      </Stack>
    );
  }

  return (
    <Box>
      {/* Narrative sections — each shows a neutral empty when it has no clusters. */}
      {SECTIONS.map((section) => (
        <NarrativeSection
          key={section.type}
          title={section.title}
          clusters={bySection[section.type]}
          surface={surface}
          onClusterClick={handleClusterClick}
        />
      ))}

      {/* Tech Stack — placement + today's flat content (both surfaces). */}
      <TypedSection
        title="Tech Stack"
        testId="section-tech-stack"
        emptyLabel="No tech stack signals captured"
        signals={tech.signals}
        loading={tech.loading}
        onSelect={handleSelect}
      />

      {/* Objections — DC surface only (blockers are deal-scoped). */}
      {isDC && (
        <TypedSection
          title="Objections"
          testId="section-objections"
          emptyLabel="No objections captured"
          signals={blockers.signals}
          loading={blockers.loading}
          onSelect={handleSelect}
        />
      )}

      {/* Cluster detail drawer — self-contained member CRUD. */}
      <SignalClusterDetailDrawer
        open={clusterDrawer.open}
        onClose={handleClusterDrawerClose}
        clusterSummary={clusterDrawer.summary}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
        onClusterChange={mutateClusters}
      />

      {/* Typed-section member drawer + modals. */}
      <SignalQuickDrawer
        open={memberDrawer.open}
        signal={memberDrawer.signal}
        signalType={memberDrawer.signalType}
        onClose={handleDrawerClose}
        onValidate={handleValidate}
        onReject={handleRejectOpen}
        onEdit={handleEditOpen}
        onReopen={handleReopen}
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
  /** "account" → account-scoped clusters + DC count + Tech; "dc" → adds Objections. */
  surface: PropTypes.oneOf(["account", "dc"]).isRequired,
  /** Account UUID — required on both surfaces (clusters are account-scoped). */
  accountId: PropTypes.string.isRequired,
  /** Decision-cycle UUID — required on the DC surface. */
  decisionCycleId: PropTypes.string,
};
