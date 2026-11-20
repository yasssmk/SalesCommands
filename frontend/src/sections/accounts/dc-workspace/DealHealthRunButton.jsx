"use client";

import PropTypes from "prop-types";

// MUI
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Tooltip from "@mui/material/Tooltip";

// Icons
import ExperimentOutlined from "@ant-design/icons/ExperimentOutlined";

// Project imports
import { DEAL_HEALTH_RUN_LABELS } from "api/aiPipelines/dealHealth";
import useDealHealthRunner from "hooks/useDealHealthRunner";

// ==============================|| DEAL HEALTH RUN BUTTON ||============================== //

// The run (long: client timeout -> polling -> snapshot or INFO) and its
// « in progress » state are shared with the Strategic tab's triggers
// (hooks/useDealHealthRunner.js, sprint « Deal health v2 », 5c). A closed
// cycle (step 6, A10) is not analysed again: disabled, with the reason on
// hover.
export default function DealHealthRunButton({ cycleId, disabled = false, closed = false }) {
  const { run, running } = useDealHealthRunner(cycleId);

  return (
    <Tooltip title={closed ? DEAL_HEALTH_RUN_LABELS.CLOSED : DEAL_HEALTH_RUN_LABELS.TOOLTIP}>
      <span>
        <Button
          size="small"
          variant="outlined"
          color="secondary"
          startIcon={
            running ? (
              <CircularProgress size={16} color="inherit" />
            ) : (
              <ExperimentOutlined />
            )
          }
          onClick={run}
          disabled={disabled || closed || running || !cycleId}
        >
          {running ? DEAL_HEALTH_RUN_LABELS.RUNNING : DEAL_HEALTH_RUN_LABELS.HEADER}
        </Button>
      </span>
    </Tooltip>
  );
}

DealHealthRunButton.propTypes = {
  cycleId: PropTypes.string,
  disabled: PropTypes.bool,
  /** The decision cycle is closed (an outcome): no new analysis (A10). */
  closed: PropTypes.bool,
};
