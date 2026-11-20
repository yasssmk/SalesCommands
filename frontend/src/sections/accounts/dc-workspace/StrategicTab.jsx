// frontend/src/sections/accounts/dc-workspace/StrategicTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  ExperimentOutlined,
  InboxOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

// Project imports
import {
  DEAL_HEALTH_RUN_LABELS,
  canRunDealHealth,
  dealHealthBlockedReason,
  isDealHealthClosed,
  useGetDealHealthSnapshot,
} from "api/aiPipelines/dealHealth";
import { useGetReadiness } from "api/accounts/decisionCycles";
import useDealHealthRunner from "hooks/useDealHealthRunner";
import DealHealthFreshnessAlert from "components/display/DealHealthFreshnessAlert";

// Section imports
import ReadinessScoreGauge from "./ReadinessScoreGauge";
import DealHealthView from "./DealHealthView";
import ThemesView from "./ThemesView";

// ==============================|| STRATEGIC TAB ||============================== //

export default function StrategicTab({ cycleId, accountId, cycle }) {
  const { snapshot, freshness, snapshotLoading, snapshotError } =
    useGetDealHealthSnapshot(cycleId);
  const { readiness, readinessLoading } = useGetReadiness(cycleId);

  const [subTab, setSubTab] = useState("deal-health");

  // The run and its « in progress » state are shared with the DC header's
  // button (hooks/useDealHealthRunner.js, sprint « Deal health v2 », 5c): a
  // run that outlasts the client timeout keeps every trigger disabled until
  // the new snapshot arrives (the view refreshes, no reload) or the polling
  // window ends (INFO).
  const { run: handleRun, running: busy } = useDealHealthRunner(cycleId);
  // Step 8: « new information to analyse » next to Run / Re-run — the
  // server's freshness (read with the latest snapshot), a warning, never red.
  // Step 6 (A10): a closed cycle is not analysed again; 6b: only an admin, a
  // manager or the cycle's owner runs it — the triggers are disabled with the
  // reason on hover; the last diagnostic stays readable.
  const blockedReason = dealHealthBlockedReason({
    closed: isDealHealthClosed(cycle),
    allowed: canRunDealHealth(cycle),
  });
  const blocked = Boolean(blockedReason);

  // Loading
  if (snapshotLoading || readinessLoading) {
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

  // Error
  if (snapshotError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <Typography color="error">Failed to load strategic data</Typography>
      </Box>
    );
  }

  // Empty state — no snapshot yet
  if (!snapshot) {
    return (
      <Box>
        <Stack
          spacing={3}
          alignItems="center"
          justifyContent="center"
          sx={{ minHeight: 350, py: 4 }}
        >
          <ReadinessScoreGauge
            score={readiness?.score ?? cycle?.readiness_score ?? 0}
            dimensions={readiness?.dimensions}
          />

          <Stack spacing={1} alignItems="center">
            <Typography color="text.secondary">
              No deal health diagnostic has been run yet.
            </Typography>
            <Typography variant="caption" color="text.secondary">
              The diagnostic analyses validated signals and transcripts to
              assess deal maturity across 7 dimensions.
            </Typography>
          </Stack>

          <Stack direction="row" spacing={1.5} alignItems="center">
            <DealHealthFreshnessAlert freshness={freshness} />
            <Tooltip title={blockedReason ?? ""}>
              <span>
                <Button
                  variant="contained"
                  startIcon={
                    busy ? (
                      <CircularProgress size={14} />
                    ) : (
                      <ExperimentOutlined style={{ fontSize: 14 }} />
                    )
                  }
                  onClick={handleRun}
                  disabled={busy || blocked}
                >
                  {busy
                    ? DEAL_HEALTH_RUN_LABELS.RUNNING
                    : DEAL_HEALTH_RUN_LABELS.RUN}
                </Button>
              </span>
            </Tooltip>
          </Stack>
        </Stack>
      </Box>
    );
  }

  // Has snapshot — show sub-navigation
  return (
    <Box>
      {/* Sub-tabs */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2.5 }}
      >
        <Tabs
          value={subTab}
          onChange={(_, v) => setSubTab(v)}
          sx={{ minHeight: 36 }}
        >
          <Tab
            value="deal-health"
            label="Deal Health"
            icon={<ThunderboltOutlined style={{ fontSize: 14 }} />}
            iconPosition="start"
            sx={{ minHeight: 36, py: 0, textTransform: "none" }}
          />
          <Tab
            value="themes"
            label="Themes"
            icon={<InboxOutlined style={{ fontSize: 14 }} />}
            iconPosition="start"
            sx={{ minHeight: 36, py: 0, textTransform: "none" }}
          />
        </Tabs>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <DealHealthFreshnessAlert freshness={freshness} />
          <Tooltip title={blockedReason ?? ""}>
            <span>
              <Button
                size="small"
                variant="outlined"
                startIcon={
                  busy ? (
                    <CircularProgress size={12} />
                  ) : (
                    <ExperimentOutlined style={{ fontSize: 12 }} />
                  )
                }
                onClick={handleRun}
                disabled={busy || blocked}
              >
                {busy
                  ? DEAL_HEALTH_RUN_LABELS.RUNNING
                  : DEAL_HEALTH_RUN_LABELS.RERUN}
              </Button>
            </span>
          </Tooltip>
        </Stack>
      </Stack>

      {/* Sub-tab content */}
      {subTab === "deal-health" && (
        <DealHealthView snapshot={snapshot} cycleId={cycleId} />
      )}
      {subTab === "themes" && (
        <ThemesView cycleId={cycleId} accountId={accountId} />
      )}
    </Box>
  );
}

StrategicTab.propTypes = {
  cycleId: PropTypes.string.isRequired,
  accountId: PropTypes.string.isRequired,
  cycle: PropTypes.shape({
    readiness_score: PropTypes.number,
    outcome: PropTypes.string,
    can_run_deal_health: PropTypes.bool,
  }),
};
