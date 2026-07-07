// frontend/src/sections/accounts/dc-workspace/StrategicTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";

// Icons
import {
  ExperimentOutlined,
  InboxOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

// Project imports
import {
  useGetDealHealthSnapshot,
  runDealHealth,
  pollForNewSnapshot,
} from "api/aiPipelines/dealHealth";
import { useGetReadiness } from "api/accounts/decisionCycles";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

// Section imports
import ReadinessScoreGauge from "./ReadinessScoreGauge";
import DealHealthView from "./DealHealthView";
import ThemesView from "./ThemesView";

// ==============================|| STRATEGIC TAB ||============================== //

export default function StrategicTab({ cycleId, accountId, cycle }) {
  const { snapshot, snapshotLoading, snapshotError, mutateSnapshot } =
    useGetDealHealthSnapshot(cycleId);
  const { readiness, readinessLoading } = useGetReadiness(cycleId);

  const [subTab, setSubTab] = useState("deal-health");
  const [runLoading, setRunLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  const busy = runLoading || polling;

  const handleRun = useCallback(async () => {
    const previousSnapshotId = snapshot?.id ?? snapshot?.snapshot_date ?? null;

    setRunLoading(true);
    const result = await runDealHealth(cycleId);
    setRunLoading(false);

    if (result.success) {
      displaySuccessSnackbar("Deal health diagnostic completed");
      mutateSnapshot();
      return;
    }

    // The pipeline is synchronous server-side but can outlast the client
    // timeout. On a timeout the snapshot may still have been written — poll
    // for a new one before surfacing an error.
    if (result.isTimeout || result.status === 408) {
      setPolling(true);
      const polled = await pollForNewSnapshot(cycleId, previousSnapshotId);
      setPolling(false);

      if (polled.success) {
        displaySuccessSnackbar("Deal health diagnostic completed");
        mutateSnapshot();
      } else {
        displayWarningSnackbar(
          "Analysis is taking longer than expected — please retry in a moment.",
        );
      }
      return;
    }

    displayErrorSnackbar(result);
  }, [cycleId, snapshot?.id, snapshot?.snapshot_date, mutateSnapshot]);

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
            disabled={busy}
          >
            {polling
              ? "Analysis still running…"
              : runLoading
                ? "Running diagnostic…"
                : "Run Deal Health"}
          </Button>
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
          disabled={busy}
        >
          {polling ? "Analysis still running…" : runLoading ? "Running…" : "Re-run"}
        </Button>
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
  }),
};
