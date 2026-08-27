// frontend/src/sections/accounts/signals/ClusterRow.jsx
//
// One cluster = one informational row in the rich DC/Account Qualification
// view. Shows the representative message plus EPURATED, factual meta:
//   - signal_count            ("N signals")
//   - pending_count           ("N to validate", only when > 0)
//   - freshness_status        (Fresh / Dormant / Stale, light chip)
//   - temporal pertinence     (period_start → period_end, from C1)
//   - departments involved    (distinct target_department names, from C4)
//   - DC count                (Account surface only; decision_cycle_ids.length)
//
// Deliberately NO urgency/priority, NO max scope level, NO impacted contacts.
// The row is informational (no action buttons); clicking it opens the cluster
// drawer where the members and their actions live.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import {
  ClockCircleOutlined,
  TeamOutlined,
  BranchesOutlined,
} from "@ant-design/icons";

import { resolveFreshness } from "sections/accounts/signals/signalClusters";

function formatShortDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

// ==============================|| CLUSTER ROW ||============================== //

export default function ClusterRow({ cluster, surface, onClick }) {
  const {
    signal_type: clusterSignalType,
    summary,
    signal_count: signalCount = 0,
    pending_count: pendingCount = 0,
    freshness_status: freshnessStatus,
    period_start: periodStart,
    period_end: periodEnd,
    last_confirmed_at: lastConfirmedAt,
    departments = [],
    decision_cycle_ids: decisionCycleIds = [],
  } = cluster;

  // TechStack cluster rows are deliberately barer than the axis-based ones
  // (PO decision): tool name + "N signals" + last confirmation only — no
  // priority (there is none), no freshness/period/departments/DC noise.
  const isTech = clusterSignalType === "tech_stack";

  const freshness = resolveFreshness(freshnessStatus);
  const FreshnessIcon = freshness.icon;

  const start = formatShortDate(periodStart);
  const end = formatShortDate(periodEnd);
  const period = start && end ? (start === end ? start : `${start} → ${end}`) : null;

  const lastConfirmed = formatShortDate(lastConfirmedAt);

  const dcCount = Array.isArray(decisionCycleIds) ? decisionCycleIds.length : 0;

  return (
    <Box
      data-testid="cluster-row"
      role="button"
      tabIndex={0}
      aria-label="Open cluster details"
      onClick={() => onClick?.(cluster)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(cluster);
        }
      }}
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: 0.75,
        width: "100%",
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        px: 2,
        py: 1.25,
        mb: 1,
        cursor: "pointer",
        transition: "background-color 0.12s",
        "&:hover": { bgcolor: "action.hover" },
      }}
    >
      {/* Line 1: representative message (full text, wraps) */}
      <Typography
        variant="body2"
        sx={{ fontWeight: 500, whiteSpace: "normal", overflowWrap: "anywhere" }}
      >
        {summary || "—"}
      </Typography>

      {/* Line 2: epurated meta */}
      <Stack
        direction="row"
        alignItems="center"
        gap={1}
        flexWrap="wrap"
        useFlexGap
        sx={{ width: "100%" }}
      >
        {/* signal count */}
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
          {signalCount} signal{signalCount === 1 ? "" : "s"}
        </Typography>

        {/* TechStack — last confirmation only (epurated tech row) */}
        {isTech && lastConfirmed && (
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flexShrink: 0 }}>
            <ClockCircleOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            <Typography variant="caption" color="text.secondary" noWrap>
              Last confirmed {lastConfirmed}
            </Typography>
          </Stack>
        )}

        {/*
          Axis-based cluster meta (pain / objective / impact) — unchanged.
          Gated off for TechStack, whose row shows only the count + last
          confirmation above.
        */}
        {!isTech && (
          <>
            {/* pending — "N to validate" */}
            {pendingCount > 0 && (
              <Chip
                label={`${pendingCount} to validate`}
                color="warning"
                variant="light"
                size="small"
                sx={{ height: 20, fontSize: "0.68rem" }}
              />
            )}

            {/* freshness */}
            {freshnessStatus && (
              <Chip
                icon={<FreshnessIcon style={{ fontSize: 12 }} />}
                label={freshness.label}
                color={freshness.color}
                variant="light"
                size="small"
                sx={{ height: 20, fontSize: "0.68rem" }}
              />
            )}

            {/* temporal pertinence — covered period */}
            {period && (
              <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flexShrink: 0 }}>
                <ClockCircleOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
                <Typography variant="caption" color="text.secondary" noWrap>
                  {period}
                </Typography>
              </Stack>
            )}

            {/* departments involved */}
            {departments.length > 0 && (
              <Stack
                direction="row"
                spacing={0.5}
                alignItems="center"
                flexWrap="wrap"
                useFlexGap
                sx={{ minWidth: 0 }}
              >
                <TeamOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
                {departments.map((d) => (
                  <Chip
                    key={d.id}
                    label={d.name}
                    size="small"
                    variant="outlined"
                    sx={{ height: 18, fontSize: "0.62rem" }}
                  />
                ))}
              </Stack>
            )}

            {/* Account only: number of decision cycles this cluster spans */}
            {surface === "account" && dcCount > 0 && (
              <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flexShrink: 0 }}>
                <BranchesOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
                <Typography variant="caption" color="text.secondary" noWrap>
                  {dcCount} DC{dcCount === 1 ? "" : "s"}
                </Typography>
              </Stack>
            )}
          </>
        )}
      </Stack>
    </Box>
  );
}

ClusterRow.propTypes = {
  cluster: PropTypes.shape({
    canonical_key: PropTypes.string,
    signal_type: PropTypes.string,
    summary: PropTypes.string,
    signal_count: PropTypes.number,
    pending_count: PropTypes.number,
    freshness_status: PropTypes.string,
    period_start: PropTypes.string,
    period_end: PropTypes.string,
    last_confirmed_at: PropTypes.string,
    departments: PropTypes.arrayOf(
      PropTypes.shape({ id: PropTypes.string, name: PropTypes.string }),
    ),
    decision_cycle_ids: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
  /** "account" shows the DC count; "dc" hides it (single cycle). */
  surface: PropTypes.oneOf(["account", "dc"]).isRequired,
  onClick: PropTypes.func,
};
