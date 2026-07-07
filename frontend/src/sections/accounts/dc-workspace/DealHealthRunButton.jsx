"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Tooltip from "@mui/material/Tooltip";

// Icons
import ExperimentOutlined from "@ant-design/icons/ExperimentOutlined";

// Project imports
import {
  runDealHealth,
  pollForNewSnapshot,
  getLatestSnapshotId,
} from "api/aiPipelines/dealHealth";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

// ==============================|| DEAL HEALTH RUN BUTTON ||============================== //

export default function DealHealthRunButton({ cycleId, disabled = false }) {
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  const busy = loading || polling;

  const handleRun = async () => {
    if (!cycleId || busy) return;

    setLoading(true);
    // Baseline snapshot id so a post-timeout poll can distinguish a newly
    // written snapshot from a pre-existing one.
    const previousSnapshotId = await getLatestSnapshotId(cycleId);
    try {
      const result = await runDealHealth(cycleId);
      if (result.success) {
        displaySuccessSnackbar("Deal health diagnostic completed");
        return;
      }

      // The pipeline is synchronous server-side but can outlast the client
      // timeout. On a timeout the snapshot may still exist — poll before
      // surfacing an error.
      if (result.isTimeout || result.status === 408) {
        setLoading(false);
        setPolling(true);
        const polled = await pollForNewSnapshot(cycleId, previousSnapshotId);
        if (polled.success) {
          displaySuccessSnackbar("Deal health diagnostic completed");
        } else {
          displayWarningSnackbar(
            "Analysis is taking longer than expected — please retry in a moment.",
          );
        }
        return;
      }

      displayErrorSnackbar(result);
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setLoading(false);
      setPolling(false);
    }
  };

  return (
    <Tooltip title="Run deal health diagnostic">
      <span>
        <Button
          size="small"
          variant="outlined"
          color="secondary"
          startIcon={
            busy ? (
              <CircularProgress size={16} color="inherit" />
            ) : (
              <ExperimentOutlined />
            )
          }
          onClick={handleRun}
          disabled={disabled || busy || !cycleId}
        >
          {polling
            ? "Analysis still running…"
            : loading
              ? "Analyzing..."
              : "Deal Health"}
        </Button>
      </span>
    </Tooltip>
  );
}

DealHealthRunButton.propTypes = {
  cycleId: PropTypes.string,
  disabled: PropTypes.bool,
};
