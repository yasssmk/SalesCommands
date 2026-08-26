// frontend/src/sections/accounts/signals/QualificationGroupedView.jsx
/**
 * QualificationGroupedView — the rich DC / Account Qualification synthesis.
 *
 * Three narrative sections — Objectives / Pains / Impacts — each nesting the
 * account's (or cycle's) clusters by DOMAIN (what) → DIMENSION → CLUSTER. One
 * row = one cluster (clusters already exist in the DB, identified
 * type:what:dimension); the flat cluster list from the service is nested
 * client-side here.
 *
 * Each cluster row is informational (no action buttons) and shows epurated,
 * factual meta only — signal count, "N to validate", freshness, covered
 * period, departments involved, and (Account only) the number of decision
 * cycles it spans. Clicking a row opens the existing cluster drawer, where the
 * members and their actions live.
 *
 * Surface:
 *   account → clusters scoped to the account; DC count shown on rows.
 *   dc      → clusters scoped to the decision cycle; DC count hidden.
 *
 * Tech Stack and Objections are intentionally NOT rendered here — they are a
 * separate, later step (tech clustering to build).
 */

"use client";

import PropTypes from "prop-types";
import { useCallback, useMemo, useState } from "react";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { InboxOutlined } from "@ant-design/icons";

// project imports
import ClusterRow from "./ClusterRow";
import SignalClusterDetailDrawer from "./SignalClusterDetailDrawer";
import { useGetClustersByAccount } from "api/signals/signalClusters";
import { useGetSignalChoices } from "api/signals/signals";

// The three narrative sections, in reading order.
const SECTIONS = [
  { type: "objective", title: "Objectives" },
  { type: "pain", title: "Pains" },
  { type: "impact", title: "Impacts" },
];
const CLUSTER_TYPES = SECTIONS.map((s) => s.type);

// ==============================|| NESTING ||============================== //

/**
 * Nest a flat, priority-sorted cluster list into domain → dimension groups.
 * Insertion order is preserved (clusters arrive priority-sorted), so the
 * strongest domains/dimensions surface first.
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

function SectionHeader({ title, count }) {
  return (
    <Typography
      variant="overline"
      color="text.secondary"
      sx={{ mb: 1.5, display: "block", letterSpacing: 1.5 }}
    >
      {title}
      <Typography
        component="span"
        variant="caption"
        color="text.disabled"
        sx={{ ml: 1, letterSpacing: 0 }}
      >
        ({count})
      </Typography>
    </Typography>
  );
}

SectionHeader.propTypes = {
  title: PropTypes.string.isRequired,
  count: PropTypes.number.isRequired,
};

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
        mb: 2,
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
 * One narrative section (Objectives / Pains / Impacts): its clusters nested by
 * domain → dimension → cluster rows.
 */
function NarrativeSection({ title, clusters, surface, onClusterClick }) {
  const domains = useMemo(() => nestByDomainDimension(clusters), [clusters]);

  return (
    <Box sx={{ mb: 4 }} data-testid={`section-${title.toLowerCase()}`}>
      <SectionHeader title={title} count={clusters.length} />

      {domains.length === 0 ? (
        <NeutralEmpty label={`No ${title.toLowerCase()} yet`} />
      ) : (
        domains.map((dom) => (
          <Box key={dom.what} sx={{ mb: 2 }}>
            {/* Domain sub-heading */}
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
              {dom.whatLabel}
            </Typography>

            {dom.dims.map((dim) => (
              <Box key={dim.dimension} sx={{ pl: 1.5, mb: 1.5 }}>
                {/* Dimension label */}
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
          </Box>
        ))
      )}
    </Box>
  );
}

NarrativeSection.propTypes = {
  title: PropTypes.string.isRequired,
  clusters: PropTypes.array.isRequired,
  surface: PropTypes.oneOf(["account", "dc"]).isRequired,
  onClusterClick: PropTypes.func.isRequired,
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

  const { choices, choicesLoading } = useGetSignalChoices();

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

  const totalClusters = (clusters ?? []).length;

  return (
    <Box>
      {totalClusters === 0 ? (
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
            Objective, Pain and Impact signals group automatically here.
          </Typography>
        </Box>
      ) : (
        SECTIONS.map((section) => (
          <NarrativeSection
            key={section.type}
            title={section.title}
            clusters={bySection[section.type]}
            surface={surface}
            onClusterClick={handleClusterClick}
          />
        ))
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
    </Box>
  );
}

QualificationGroupedView.propTypes = {
  /** "account" → account-scoped clusters + DC count; "dc" → cycle-scoped. */
  surface: PropTypes.oneOf(["account", "dc"]).isRequired,
  /** Account UUID — required on both surfaces (clusters are account-scoped). */
  accountId: PropTypes.string.isRequired,
  /** Decision-cycle UUID — required on the DC surface. */
  decisionCycleId: PropTypes.string,
};
