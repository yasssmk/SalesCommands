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
import { runDealHealth } from "api/aiPipelines/dealHealth";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| DEAL HEALTH RUN BUTTON ||============================== //

export default function DealHealthRunButton({ cycleId, disabled = false }) {
  const [loading, setLoading] = useState(false);

  const handleRun = async () => {
    if (!cycleId || loading) return;

    setLoading(true);
    try {
      const result = await runDealHealth(cycleId);
      if (result.success) {
        displaySuccessSnackbar("Deal health diagnostic completed");
      } else {
        displayErrorSnackbar(result);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setLoading(false);
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
            loading ? (
              <CircularProgress size={16} color="inherit" />
            ) : (
              <ExperimentOutlined />
            )
          }
          onClick={handleRun}
          disabled={disabled || loading || !cycleId}
        >
          {loading ? "Analyzing..." : "Deal Health"}
        </Button>
      </span>
    </Tooltip>
  );
}

DealHealthRunButton.propTypes = {
  cycleId: PropTypes.string,
  disabled: PropTypes.bool,
};
