// frontend/src/sections/accounts/dc-workspace/DecisionCycleCardsList.jsx
/**
 * Decision Cycle Cards List
 *
 * Filterable card list replacing the old cycle selector + embedded timeline.
 * Each card navigates to the full DC Workspace on click.
 *
 * Data source: useGetDecisionCyclesByAccount (timeline serializer).
 * No per-card API call.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTheme, alpha } from "@mui/material/styles";

// MUI
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import LinearProgress from "@mui/material/LinearProgress";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// @ant-design/icons
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import ClockCircleOutlined from "@ant-design/icons/ClockCircleOutlined";
import DashboardOutlined from "@ant-design/icons/DashboardOutlined";
import ExclamationCircleOutlined from "@ant-design/icons/ExclamationCircleOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";

// Project imports
import {
  CYCLE_DERIVED_STATUS_LABELS,
  CYCLE_STATUS_COLORS,
} from "api/accounts/decisionCycles";

// ==============================|| FILTERS ||============================== //

const FILTERS = [
  { value: "active", label: "Active" },
  { value: "all", label: "All" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

function filterCycles(cycles, filter) {
  if (!cycles) return [];
  switch (filter) {
    case "active":
      return cycles.filter((c) => c.is_active);
    case "won":
      return cycles.filter((c) => c.outcome === "WON");
    case "lost":
      return cycles.filter((c) => c.outcome === "LOST");
    case "all":
    default:
      return cycles;
  }
}

// ==============================|| HELPERS ||============================== //

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

function daysSince(dateStr) {
  if (!dateStr) return null;
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
  } catch {
    return null;
  }
}

function getStatusDisplay(cycle) {
  if (cycle.outcome) {
    return {
      label: CYCLE_DERIVED_STATUS_LABELS[cycle.outcome] || cycle.outcome,
      color: CYCLE_STATUS_COLORS[cycle.outcome] || "default",
    };
  }
  if (cycle.cycle_status) {
    return {
      label:
        CYCLE_DERIVED_STATUS_LABELS[cycle.cycle_status] || cycle.cycle_status,
      color: CYCLE_STATUS_COLORS[cycle.cycle_status] || "default",
    };
  }
  return { label: "Unknown", color: "default" };
}

// ==============================|| CYCLE CARD ||============================== //

function CycleCard({ cycle, accountId }) {
  const theme = useTheme();
  const router = useRouter();
  const status = getStatusDisplay(cycle);
  const age = daysSince(cycle.created_at);
  const progress = cycle.progress || {};
  const percentage = progress.percentage ?? 0;
  const stepsTotal = progress.total_steps ?? 0;
  const stepsValidated = progress.validated_steps ?? 0;
  const currentStepName = progress.current_step_name || null;
  const readiness = cycle.readiness_score;

  const handleClick = useCallback(() => {
    router.push(`/accounts/${accountId}/dc/${cycle.id}`);
  }, [router, accountId, cycle.id]);

  return (
    <Card
      variant="outlined"
      sx={{
        borderColor: cycle.is_at_risk
          ? alpha(theme.palette.error.main, 0.4)
          : theme.palette.divider,
      }}
    >
      <CardActionArea onClick={handleClick}>
        <CardContent sx={{ p: 2, "&:last-child": { pb: 2 } }}>
          {/* Row 1: Name + status chip + age */}
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            spacing={1}
            sx={{ mb: 1.5 }}
          >
            <Typography variant="subtitle1" fontWeight={600} noWrap>
              {cycle.name}
            </Typography>
            <Stack direction="row" spacing={0.75} alignItems="center">
              {cycle.is_at_risk && (
                <ExclamationCircleOutlined
                  style={{
                    fontSize: 16,
                    color: theme.palette.error.main,
                  }}
                />
              )}
              <Chip
                label={status.label}
                color={status.color}
                size="small"
                variant="outlined"
              />
              {age !== null && (
                <Chip
                  icon={
                    <ClockCircleOutlined
                      style={{ fontSize: 12 }}
                    />
                  }
                  label={`${age}d`}
                  size="small"
                  variant="outlined"
                  sx={{ borderColor: "transparent" }}
                />
              )}
            </Stack>
          </Stack>

          {/* Row 2: Progress bar + step count */}
          <Stack spacing={0.5} sx={{ mb: 1.5 }}>
            <Stack
              direction="row"
              justifyContent="space-between"
              alignItems="center"
            >
              <Stack direction="row" spacing={0.5} alignItems="center">
                <CheckCircleOutlined
                  style={{
                    fontSize: theme.iconSizes?.sm || 14,
                    color: theme.palette.text.secondary,
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  {currentStepName
                    ? `${currentStepName} · ${stepsValidated}/${stepsTotal}`
                    : `${stepsValidated}/${stepsTotal} steps`}
                </Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary">
                {percentage}%
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={percentage}
              sx={{ height: 4, borderRadius: 2 }}
            />
          </Stack>

          {/* Row 3: Info chips */}
          <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
            {/* Readiness */}
            {readiness !== null && readiness !== undefined && (
              <Stack direction="row" spacing={0.5} alignItems="center">
                <DashboardOutlined
                  style={{
                    fontSize: theme.iconSizes?.sm || 14,
                    color: theme.palette.text.secondary,
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  Readiness {readiness}%
                </Typography>
              </Stack>
            )}

            {/* Outcome date or last update */}
            {cycle.outcome_date ? (
              <Stack direction="row" spacing={0.5} alignItems="center">
                <CalendarOutlined
                  style={{
                    fontSize: theme.iconSizes?.sm || 14,
                    color: theme.palette.text.secondary,
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  Closed {formatDate(cycle.outcome_date)}
                </Typography>
              </Stack>
            ) : (
              cycle.updated_at && (
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <ThunderboltOutlined
                    style={{
                      fontSize: theme.iconSizes?.sm || 14,
                      color: theme.palette.text.secondary,
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    Updated {formatDate(cycle.updated_at)}
                  </Typography>
                </Stack>
              )
            )}

            {/* Stalled steps warning */}
            {(cycle.stalled_steps_count ?? 0) > 0 && (
              <Stack direction="row" spacing={0.5} alignItems="center">
                <ExclamationCircleOutlined
                  style={{
                    fontSize: theme.iconSizes?.sm || 14,
                    color: theme.palette.warning.main,
                  }}
                />
                <Typography variant="caption" color="warning.main">
                  {cycle.stalled_steps_count} stalled
                </Typography>
              </Stack>
            )}
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

CycleCard.propTypes = {
  cycle: PropTypes.object.isRequired,
  accountId: PropTypes.string.isRequired,
};

// ==============================|| CARDS LIST ||============================== //

export default function DecisionCycleCardsList({
  accountId,
  cycles,
  cyclesLoading,
}) {
  const [filter, setFilter] = useState("active");

  const filtered = useMemo(
    () => filterCycles(cycles, filter),
    [cycles, filter],
  );

  const handleFilterChange = useCallback((_e, newFilter) => {
    if (newFilter !== null) setFilter(newFilter);
  }, []);

  // ==============================|| LOADING ||============================== //

  if (cyclesLoading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: 200,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* Filter bar */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <ToggleButtonGroup
          value={filter}
          exclusive
          onChange={handleFilterChange}
          size="small"
        >
          {FILTERS.map((f) => (
            <ToggleButton key={f.value} value={f.value}>
              {f.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        <Typography variant="caption" color="text.secondary">
          {filtered.length} cycle{filtered.length !== 1 ? "s" : ""}
        </Typography>
      </Stack>

      {/* Cards */}
      {filtered.length === 0 ? (
        <Box sx={{ textAlign: "center", py: 4 }}>
          <Typography color="text.secondary">
            No decision cycles match this filter.
          </Typography>
        </Box>
      ) : (
        <Stack spacing={1.5}>
          {filtered.map((cycle) => (
            <CycleCard
              key={cycle.id}
              cycle={cycle}
              accountId={accountId}
            />
          ))}
        </Stack>
      )}
    </Box>
  );
}

DecisionCycleCardsList.propTypes = {
  accountId: PropTypes.string.isRequired,
  cycles: PropTypes.array,
  cyclesLoading: PropTypes.bool,
};
