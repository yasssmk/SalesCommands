// frontend/src/sections/activities/workspace/RunAIAnalysisButton.jsx
//
// Sprint Next steps 5.12 B — the "Run AI Analysis" action, extracted AS IS
// from ActivityNotesTab (the Source band) to be shared: the button (disabled
// with its tooltip when the activity is locked, the transcript empty or too
// short; "Analyzing…" + the polling progress while the pipeline runs) and the
// 2-step RunAIWizard, whose confirmation runs the page's pipelineRunner.
//
// `label` and `defaultObjectives` (the objectives checked when the wizard
// opens) let another entry point reuse it — the Next steps band: « Run AI on
// transcript to extract next steps », next steps only (5.12 B).
//
// The wizard open state is uncontrolled by default; a caller that opens it
// from elsewhere too (the Source band's "Try again") controls it with
// `open` / `onOpenChange` — the CollapsibleStrip pattern — and gates its own
// openings with canRunAIAnalysis, the one predicate of the button.

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// project imports
import { PIPELINE_STATE } from 'hooks/usePipelineRunner';
import RunAIWizard from 'sections/activities/workspace/RunAIWizard';

// assets
import ExperimentOutlined from '@ant-design/icons/ExperimentOutlined';

// ==============================|| CONSTANTS ||============================== //

export const MIN_TRANSCRIPT_LENGTH = 50;

// The Run AI action is available: not locked, a long enough transcript, no
// run in progress.
export function canRunAIAnalysis({ isLocked, transcript, pipelineState }) {
  return (
    !isLocked &&
    (transcript ?? '').trim().length >= MIN_TRANSCRIPT_LENGTH &&
    pipelineState !== PIPELINE_STATE.RUNNING
  );
}

// ==============================|| RUN AI ANALYSIS BUTTON ||============================== //

export default function RunAIAnalysisButton({
  activityId,
  transcript = '',
  outcomeNotes = '',
  isLocked,
  pipelineRunner,
  lastRun,
  runsByPipeline,
  open: controlledOpen,
  onOpenChange,
  label = 'Run AI Analysis',
  defaultObjectives,
}) {
  const { run, state: pipelineState, pollProgress } = pipelineRunner;

  // --- Wizard open state (controlled when `open` is passed) ---
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const isControlled = controlledOpen !== undefined;
  const wizardOpen = isControlled ? controlledOpen : uncontrolledOpen;
  const setWizardOpen = (next) => {
    if (!isControlled) setUncontrolledOpen(next);
    onOpenChange?.(next);
  };

  // --- Derive effective display state from pipelineState + lastRun ---
  const effectiveState = deriveEffectiveState(pipelineState, lastRun);

  // --- Run AI Analysis ---
  const trimmedTranscript = transcript.trim();
  const canRunAI = canRunAIAnalysis({ isLocked, transcript, pipelineState });

  const handleOpenWizard = () => {
    if (canRunAI) {
      setWizardOpen(true);
    }
  };

  const handleCancelWizard = () => {
    setWizardOpen(false);
  };

  const handleConfirmWizard = (curatedTranscript, objectives) => {
    setWizardOpen(false);
    run(activityId, curatedTranscript, {
      run_qualification: objectives?.qualification ?? true,
      run_next_steps: objectives?.nextSteps ?? true,
    });
  };

  // --- Render helpers ---
  const renderRunButton = () => {
    const tooltipTitle =
      isLocked
        ? 'Activity is locked'
        : trimmedTranscript.length === 0
          ? 'Paste a transcript first'
          : trimmedTranscript.length < MIN_TRANSCRIPT_LENGTH
            ? `Transcript too short (min ${MIN_TRANSCRIPT_LENGTH} characters)`
            : '';

    if (effectiveState === 'running') {
      const isPolling = Boolean(pollProgress && pollProgress.max > 0);
      return (
        <Stack spacing={0.5} alignItems="flex-end">
          <Button
            variant="contained"
            disabled
            startIcon={<CircularProgress size={16} color="inherit" />}
          >
            Analyzing…
          </Button>
          {isPolling && (
            <Typography variant="caption" color="text.secondary">
              Polling for result ({pollProgress.attempt}/{pollProgress.max})…
            </Typography>
          )}
        </Stack>
      );
    }

    return (
      <Tooltip title={canRunAI ? '' : tooltipTitle}>
        <span>
          <Button
            variant="contained"
            onClick={handleOpenWizard}
            disabled={!canRunAI}
            startIcon={<ExperimentOutlined />}
          >
            {label}
          </Button>
        </span>
      </Tooltip>
    );
  };

  // ==============================|| RENDER ||============================== //

  return (
    <>
      {renderRunButton()}

      {/* Run AI Wizard (2-step) */}
      <RunAIWizard
        open={wizardOpen}
        activityId={activityId}
        transcript={transcript}
        outcomeNotes={outcomeNotes}
        lastRun={lastRun}
        runsByPipeline={runsByPipeline}
        onCancel={handleCancelWizard}
        onConfirm={handleConfirmWizard}
        defaultObjectives={defaultObjectives}
      />
    </>
  );
}

// ==============================|| HELPERS ||============================== //

/**
 * Derive the effective display state for the Run AI button.
 * pipelineState (transient) takes priority over lastRun (persisted).
 */
function deriveEffectiveState(pipelineState, lastRun) {
  if (pipelineState === PIPELINE_STATE.RUNNING) return 'running';
  if (pipelineState === PIPELINE_STATE.ERROR) return 'error';
  if (pipelineState === PIPELINE_STATE.SUCCESS) return 'success';
  if (pipelineState === PIPELINE_STATE.PARTIAL) return 'partial';

  // pipelineState is idle — fall back to lastRun
  if (!lastRun) return 'idle';
  if (lastRun.status === 'SUCCESS') return 'success';
  if (lastRun.status === 'PARTIAL') return 'partial';
  return 'idle';
}

// ==============================|| PROP TYPES ||============================== //

RunAIAnalysisButton.propTypes = {
  activityId: PropTypes.string,
  transcript: PropTypes.string,
  outcomeNotes: PropTypes.string,
  isLocked: PropTypes.bool,
  pipelineRunner: PropTypes.shape({
    run: PropTypes.func.isRequired,
    state: PropTypes.string.isRequired,
    pollProgress: PropTypes.shape({
      attempt: PropTypes.number,
      max: PropTypes.number,
    }),
  }).isRequired,
  lastRun: PropTypes.object,
  runsByPipeline: PropTypes.object,
  /** Controlled wizard open state (optional). */
  open: PropTypes.bool,
  /** Fired with the next open state (controlled or not). */
  onOpenChange: PropTypes.func,
  /** The button label (default: "Run AI Analysis"). */
  label: PropTypes.string,
  /** The objectives checked when the wizard opens (RunAIWizard). */
  defaultObjectives: PropTypes.shape({
    qualification: PropTypes.bool,
    nextSteps: PropTypes.bool,
  }),
};
