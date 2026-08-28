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
import Grid from "@mui/material/Grid";
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
// Tech is clustered too (read-time, on tech_name_normalized) — fetched through
// the SAME cluster pipeline as the narrative sections, in the backend cluster
// vocabulary (underscore). It is NOT a narrative SECTION (no domain/dimension
// nesting); it renders as a flat list of cluster rows in the right column.
const TECH_CLUSTER_TYPE = "tech_stack";
const CLUSTER_TYPES_WITH_TECH = [...CLUSTER_TYPES, TECH_CLUSTER_TYPE];
// Constraint is clustered too (read-time, on `nature`) but DC-SCOPED ONLY:
// requested alongside the others on the DC surface, never at account level.
// Same cluster pipeline / vocabulary (backend slug 'constraint', singular).
const CONSTRAINT_CLUSTER_TYPE = "constraint";
// nature code (ConstraintNature) → human label + stable display order. The
// cluster payload carries the code in `canonical_key`; there is no nature_display
// on the cluster, so the label lives here (front-only, matches the backend enum).
const CONSTRAINT_NATURES = [
  { code: "FUNCTIONAL", label: "Functional" },
  { code: "TECHNICAL", label: "Technical" },
  { code: "FINANCIAL", label: "Financial" },
  { code: "CONTRACTUAL", label: "Contractual & Legal" },
  { code: "OPERATIONAL", label: "Operational" },
  { code: "SECURITY", label: "Security" },
];
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

/**
 * TechCluster section — Tech Stack rendered through the CLUSTER pipeline (one
 * techno = one aggregated ClusterRow), NOT the flat signal list. Same themed
 * section shell (CollapsibleSection) and same row component (ClusterRow) as the
 * left narrative sections, minus the domain → dimension nesting (tech has no
 * canonical axes). Clicking a row opens the shared SignalClusterDetailDrawer.
 *
 * Staying in the cluster vocabulary end-to-end (cluster.signal_type ===
 * "tech_stack") is deliberate: the tech slug is only ever translated inside the
 * drawer. A tech cluster is never handed to a flat-vocabulary component
 * (SignalLine / SignalTypeChip) here.
 */
function TechClusterSection({
  title,
  testId,
  emptyLabel,
  clusters,
  loading,
  surface,
  onClusterClick,
}) {
  return (
    <CollapsibleSection
      title={title}
      count={clusters.length}
      level="section"
      testId={testId}
    >
      {loading && clusters.length === 0 ? (
        <Stack alignItems="center" py={2}>
          <CircularProgress size={18} />
        </Stack>
      ) : clusters.length === 0 ? (
        <NeutralEmpty label={emptyLabel} />
      ) : (
        <Stack spacing={0}>
          {clusters.map((cluster) => (
            <ClusterRow
              key={`${cluster.signal_type}:${cluster.canonical_key}`}
              cluster={cluster}
              surface={surface}
              onClick={onClusterClick}
            />
          ))}
        </Stack>
      )}
    </CollapsibleSection>
  );
}

TechClusterSection.propTypes = {
  title: PropTypes.string.isRequired,
  testId: PropTypes.string.isRequired,
  emptyLabel: PropTypes.string.isRequired,
  clusters: PropTypes.array.isRequired,
  loading: PropTypes.bool,
  surface: PropTypes.oneOf(["account", "dc"]).isRequired,
  onClusterClick: PropTypes.func.isRequired,
};

/**
 * ConstraintSection — the requirements (constraints) of one decision cycle,
 * rendered through the CLUSTER pipeline (one nature = one aggregated cluster),
 * GROUPED BY NATURE. Same themed shell (CollapsibleSection) and row component
 * (ClusterRow) as the tech section; the constraint cluster's `canonical_key`
 * IS its nature code, so it maps 1:1 to a nature group header. A nature with no
 * cluster is not shown. Clicking a row opens the shared SignalClusterDetailDrawer
 * (the 'constraint' → 'constraints' member-slug translation lives inside it).
 */
function ConstraintSection({
  title,
  testId,
  emptyLabel,
  clusters,
  loading,
  surface,
  onClusterClick,
}) {
  // Bucket the constraint clusters by nature (their canonical_key), in the
  // stable CONSTRAINT_NATURES order. One cluster per nature in practice.
  const byNature = useMemo(() => {
    const map = new Map();
    for (const c of clusters) {
      const list = map.get(c.canonical_key) || [];
      list.push(c);
      map.set(c.canonical_key, list);
    }
    return CONSTRAINT_NATURES.map((n) => ({
      ...n,
      clusters: map.get(n.code) || [],
    })).filter((n) => n.clusters.length > 0);
  }, [clusters]);

  return (
    <CollapsibleSection
      title={title}
      count={clusters.length}
      level="section"
      testId={testId}
    >
      {loading && clusters.length === 0 ? (
        <Stack alignItems="center" py={2}>
          <CircularProgress size={18} />
        </Stack>
      ) : byNature.length === 0 ? (
        <NeutralEmpty label={emptyLabel} />
      ) : (
        byNature.map((nature) => (
          <Box key={nature.code} sx={{ mb: 1.5 }} data-testid={`nature-${nature.code}`}>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: "block", mb: 0.75, fontWeight: 600 }}
            >
              {nature.label}
            </Typography>
            {nature.clusters.map((cluster) => (
              <ClusterRow
                key={`${cluster.signal_type}:${cluster.canonical_key}`}
                cluster={cluster}
                surface={surface}
                onClick={onClusterClick}
              />
            ))}
          </Box>
        ))
      )}
    </CollapsibleSection>
  );
}

ConstraintSection.propTypes = {
  title: PropTypes.string.isRequired,
  testId: PropTypes.string.isRequired,
  emptyLabel: PropTypes.string.isRequired,
  clusters: PropTypes.array.isRequired,
  loading: PropTypes.bool,
  surface: PropTypes.oneOf(["account", "dc"]).isRequired,
  onClusterClick: PropTypes.func.isRequired,
};

// ==============================|| QUALIFICATION GROUPED VIEW ||============================== //

export default function QualificationGroupedView({
  surface,
  accountId,
  decisionCycleId,
  perimeter = undefined,
  whats = undefined,
  dimensions = undefined,
  contacts = undefined,
  statuses = undefined,
}) {
  const isDC = surface === "dc";

  // There is NO type filter in the grouped view — the structure IS by type
  // section. Clusters always cover the full clusterable set; Tech / Objections
  // sections always render.
  const showTech = true;
  const showObjections = isDC;
  // Constraints (requirements) are DC-scoped only — never at account level.
  const showConstraints = isDC;

  // The QUALIFICATION-family filters (perimeter = scope=BUSINESS OR
  // target_department; what / dimension = subject; contact = source; status)
  // are honored by the cluster endpoint on the filtered members; the cluster
  // then forms and its meta recomputes on that filtered set.
  // ONE cluster fetch for both columns. Tech is requested alongside the
  // narrative types (same hook, same scope: account vs DC via decisionCycleId).
  // The backend ignores the subject filters (perimeter / what / dimension) for
  // tech — it has no such axes — so the tech rows are unaffected by the
  // Qualification filters, while pain/objective/impact honour them.
  // Constraint is added to the fetch ONLY on the DC surface (DC-scoped type).
  const fetchSignalTypes = isDC
    ? [...CLUSTER_TYPES_WITH_TECH, CONSTRAINT_CLUSTER_TYPE]
    : CLUSTER_TYPES_WITH_TECH;
  const { clusters, clustersLoading, clustersError, mutateClusters } =
    useGetClustersByAccount(accountId, {
      signalType: fetchSignalTypes,
      decisionCycleId: isDC ? decisionCycleId : undefined,
      perimeter,
      whats,
      dimensions,
      contacts,
      statuses,
    });

  // Objections (blockers): DC surface only. Still the flat aggregated path —
  // the Objection family is not clustered (out of scope for this sprint).
  const blockers = useAggregatedSignals({
    decisionCycleId: isDC ? decisionCycleId : undefined,
    signalTypes: ["blockers"],
    statuses: GROUPED_STATUSES,
    pageSize: SECTION_PAGE_SIZE,
  });

  const { choices, choicesLoading } = useGetSignalChoices();

  const mutateSections = useCallback(() => {
    blockers.mutate();
  }, [blockers]);

  // Split the flat cluster list into the three narrative sections. Tech is
  // bucketed separately (same list, same signal_type bucketing as the left) —
  // the narrative map intentionally ignores tech_stack so the left column is
  // byte-identical to before.
  const bySection = useMemo(() => {
    const map = { objective: [], pain: [], impact: [] };
    for (const c of clusters ?? []) {
      if (map[c.signal_type]) map[c.signal_type].push(c);
    }
    return map;
  }, [clusters]);

  // Right column: the tech clusters from the SAME fetch (one techno = one row).
  const techClusters = useMemo(
    () => (clusters ?? []).filter((c) => c.signal_type === TECH_CLUSTER_TYPE),
    [clusters],
  );

  // Right column: the constraint clusters from the SAME fetch (one nature = one
  // cluster). DC-scoped, so this is empty on the account surface.
  const constraintClusters = useMemo(
    () =>
      (clusters ?? []).filter(
        (c) => c.signal_type === CONSTRAINT_CLUSTER_TYPE,
      ),
    [clusters],
  );

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
      {/* Same two-column layout as the Activity reference: narrative sections
          on the left, Tech Stack + Objections on the right. The only
          difference vs Activity is the domain → dimension → cluster nesting
          inside the left narrative sections. */}
      <Grid container spacing={3}>
        {/* Left column — narrative sections (nested by domain → dimension).
            No Type filter in grouped — every narrative section always shows. */}
        <Grid item xs={12} md={6}>
          {SECTIONS.map((section) => (
            <NarrativeSection
              key={section.type}
              title={section.title}
              clusters={bySection[section.type]}
              surface={surface}
              onClusterClick={handleClusterClick}
            />
          ))}
        </Grid>

        {/* Right column — Tech Stack (clustered) + Objections (flat). */}
        <Grid item xs={12} md={6}>
          {showTech && (
            <TechClusterSection
              title="Tech Stack"
              testId="section-tech-stack"
              emptyLabel="No tech stack signals captured"
              clusters={techClusters}
              loading={clustersLoading}
              surface={surface}
              onClusterClick={handleClusterClick}
            />
          )}

          {/* Objections — DC surface only (blockers are deal-scoped). */}
          {showObjections && (
            <TypedSection
              title="Objections"
              testId="section-objections"
              emptyLabel="No objections captured"
              signals={blockers.signals}
              loading={blockers.loading}
              onSelect={handleSelect}
            />
          )}

          {/* Constraints (requirements) — DC surface only, clustered by nature. */}
          {showConstraints && (
            <ConstraintSection
              title="Constraints"
              testId="section-constraints"
              emptyLabel="No constraints captured"
              clusters={constraintClusters}
              loading={clustersLoading}
              surface={surface}
              onClusterClick={handleClusterClick}
            />
          )}
        </Grid>
      </Grid>

      {/* Cluster detail drawer — self-contained member CRUD. */}
      <SignalClusterDetailDrawer
        open={clusterDrawer.open}
        onClose={handleClusterDrawerClose}
        clusterSummary={clusterDrawer.summary}
        accountId={accountId}
        decisionCycleId={isDC ? decisionCycleId : undefined}
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
  /** Unified PERIMETER (OR) — 'BUSINESS' sentinel and/or department ids. */
  perimeter: PropTypes.arrayOf(
    PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  ),
  /** Domain (`what`) filter values (SignalWhat). */
  whats: PropTypes.arrayOf(PropTypes.string),
  /** Dimension filter values (SignalDimension). */
  dimensions: PropTypes.arrayOf(PropTypes.string),
  /** SOURCE filter — Contact ids (source_activity.contacts), multi. */
  contacts: PropTypes.arrayOf(PropTypes.string),
  /** Status filter values; empty/undefined = grouped default (pending+validated). */
  statuses: PropTypes.arrayOf(PropTypes.string),
};
