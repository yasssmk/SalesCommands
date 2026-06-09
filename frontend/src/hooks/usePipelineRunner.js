// frontend/src/hooks/usePipelineRunner.js

import { useState, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  runActivityExtraction,
  EXTRACTION_STATUS,
  EXTRACTION_OUTCOME_CODES,
} from 'api/aiPipelines/activityExtraction';

// ==============================|| CONSTANTS ||============================== //

export const PIPELINE_STATE = {
  IDLE: 'idle',
  RUNNING: 'running',
  SUCCESS: 'success',
  PARTIAL: 'partial',
  ERROR: 'error',
};

// ==============================|| HOOK ||============================== //

/**
 * State-machine hook for the activity extraction pipeline.
 *
 * Lifecycle: idle -> running -> success | partial | error
 * State is purely local React — lost on page refresh.
 * After run() success, state stays `success` until next run() or reset().
 * Long-term source of truth is lastRun (persisted in DB via AIPipelineRun).
 *
 * @param {Object} options
 * @param {Function} options.onSuccess - Called after a successful or partial run.
 * @param {Function} options.onError - Called after an error.
 * @returns {Object} { run, state, result, error, reset }
 */
export default function usePipelineRunner({ onSuccess, onError } = {}) {
  const [state, setState] = useState(PIPELINE_STATE.IDLE);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [pollProgress, setPollProgress] = useState(null);
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  onSuccessRef.current = onSuccess;
  onErrorRef.current = onError;

  const handlePollProgress = useCallback((attempt, maxAttempts) => {
    setPollProgress({ attempt, max: maxAttempts });
  }, []);

  const run = useCallback(async (activityId, curatedTranscript, pipelineFlags = null) => {
    if (!activityId) return;

    setState(PIPELINE_STATE.RUNNING);
    setResult(null);
    setError(null);
    setPollProgress(null);

    try {
      const res = await runActivityExtraction(activityId, curatedTranscript, handlePollProgress, pipelineFlags);

      if (res.success) {
        const data = res.data || {};
        const globalStatus = data.status;

        if (globalStatus === EXTRACTION_STATUS.PARTIAL) {
          setState(PIPELINE_STATE.PARTIAL);
        } else {
          setState(PIPELINE_STATE.SUCCESS);
        }
        setResult(data);
        onSuccessRef.current?.(data);
      } else if (res.code === EXTRACTION_OUTCOME_CODES.ALREADY_EXTRACTED) {
        setState(PIPELINE_STATE.SUCCESS);
        setResult(res.data || null);
        onSuccessRef.current?.(res.data || null);
      } else if (res.code === EXTRACTION_OUTCOME_CODES.TIMEOUT_PENDING) {
        setState(PIPELINE_STATE.ERROR);
        setError(
          'Analysis is taking longer than expected. It will continue in the background — check back in a moment.',
        );
        onErrorRef.current?.(res);
      } else {
        setState(PIPELINE_STATE.ERROR);
        setError(res.error || 'Extraction failed. Please try again.');
        onErrorRef.current?.(res);
      }
    } catch (err) {
      setState(PIPELINE_STATE.ERROR);
      setError(err?.message || 'An unexpected error occurred.');
      onErrorRef.current?.(err);
    }
  }, [handlePollProgress]);

  const reset = useCallback(() => {
    setState(PIPELINE_STATE.IDLE);
    setResult(null);
    setError(null);
    setPollProgress(null);
  }, []);

  return { run, state, result, error, pollProgress, reset };
}

// ==============================|| PROP TYPES (for documentation) ||============================== //

export const PipelineRunnerPropTypes = {
  run: PropTypes.func.isRequired,
  state: PropTypes.oneOf(Object.values(PIPELINE_STATE)).isRequired,
  result: PropTypes.object,
  error: PropTypes.string,
  pollProgress: PropTypes.shape({
    attempt: PropTypes.number,
    max: PropTypes.number,
  }),
  reset: PropTypes.func.isRequired,
};
