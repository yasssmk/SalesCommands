// frontend/src/hooks/useDealHealthRunner.js
//
// Sprint « Deal health v2 », sub-step 5c — THE run of a deal health, shared by
// every trigger of the page (the DC header button, the Strategic tab's Run /
// Re-run): one cycle runs at most once at a time from this page, and every
// trigger shows the same « in progress » state.
//
// The usePipelineRunner pattern (the Activity Run AI): a long AI run whose
// client request may time out while the server keeps working — then poll for
// the result (DEAL_HEALTH_POLL_CONFIG, ~3 min) instead of reporting an error.
//   * success, or a new snapshot found by the poll → SUCCESS snackbar; the
//     snapshot caches are revalidated (api/aiPipelines/dealHealth.js), the
//     view updates without a reload;
//   * end of the polling window, no snapshot → INFO (never red), the
//     triggers are active again;
//   * a genuine error → the standard error snackbar.
// The run state is local to the browser tab (lost on reload); the server-side
// guard against concurrent runs is step 6 (Redis).

import { useCallback, useSyncExternalStore } from "react";

import {
  DEAL_HEALTH_POLL_CONFIG,
  DEAL_HEALTH_RUN_LABELS,
  getLatestSnapshotId,
  pollForNewSnapshot,
  runDealHealth,
} from "api/aiPipelines/dealHealth";
import {
  displayErrorSnackbar,
  displayInfoSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

// ==============================|| SHARED RUN STATE ||============================== //

const runningCycles = new Set();
const listeners = new Set();

function notify() {
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// ==============================|| HOOK ||============================== //

/**
 * @param {string} cycleId - UUID of the DecisionCycle.
 * @returns {{ run: Function, running: boolean }}
 */
export default function useDealHealthRunner(cycleId) {
  const running = useSyncExternalStore(
    subscribe,
    () => runningCycles.has(cycleId),
    () => false,
  );

  const run = useCallback(async () => {
    if (!cycleId || runningCycles.has(cycleId)) return;
    runningCycles.add(cycleId);
    notify();
    try {
      // Baseline: a poll tells a newly written snapshot from this one.
      const previousSnapshotId = await getLatestSnapshotId(cycleId);
      const result = await runDealHealth(cycleId);
      if (result.success) {
        displaySuccessSnackbar(DEAL_HEALTH_RUN_LABELS.DONE);
        return;
      }
      // The client timed out; the server keeps working: not an error.
      if (result.isTimeout || result.status === 408) {
        const polled = await pollForNewSnapshot(
          cycleId,
          previousSnapshotId,
          DEAL_HEALTH_POLL_CONFIG,
        );
        if (polled.success) {
          displaySuccessSnackbar(DEAL_HEALTH_RUN_LABELS.DONE);
        } else {
          displayInfoSnackbar(DEAL_HEALTH_RUN_LABELS.STILL_RUNNING);
        }
        return;
      }
      displayErrorSnackbar(result);
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      runningCycles.delete(cycleId);
      notify();
    }
  }, [cycleId]);

  return { run, running };
}
