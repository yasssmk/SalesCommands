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
// transcript », next steps only (5.12 B). `variant` (5.12c) — the trigger:
// "button" (default, the Source band) or "pill" (the shared ClickablePill,
// the Next steps band's actions). Only the trigger changes: the same
// availability predicate, wizard, runner and "Analyzing…" state.
//
// The lock (5.12c, PO): the AI action is locked ONLY on a CANCELLED activity —
// isActivitySignalsLocked (utils/activitySignalsLock), the lock of the signal
// bands, read HERE from the activity so every entry point (the Source band,
// the Next steps band) applies the same one. The backend accepts a run on a
// COMPLETED activity.
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
import { isActivitySignalsLocked } from 'utils/activitySignalsLock';
import RunAIWizard from 'sections/activities/workspace/RunAIWizard';

// assets
import ExperimentOutlined from '@ant-design/icons/ExperimentOutlined';
import ClickablePill from 'components/chips/ClickablePill';

// ==============================|| CONSTANTS ||============================== //

export const MIN_TRANSCRIPT_LENGTH = 50;

// The trigger of the action.
export const RUN_AI_TRIGGER_VARIANTS = { BUTTON: 'button', PILL: 'pill' };

// The Run AI action is available: the activity not locked (CANCELLED only,
// isActivitySignalsLocked), a long enough transcript, no run in progress.
export function canRunAIAnalysis(activity, pipelineState) {
  return (
    !isActivitySignalsLocked(activity) &&
    (activity?.transcript ?? '').trim().length >= MIN_TRANSCRIPT_LENGTH &&
    pipelineState !== PIPELINE_STATE.RUNNING
  );
}

// ==============================|| RUN AI ANALYSIS BUTTON ||============================== //

export default function RunAIAnalysisButton({
  activity,
  pipelineRunner,
  lastRun,
  runsByPipeline,
  open: controlledOpen,
  onOpenChange,
  label = 'Run AI Analysis',
  defaultObjectives,
  variant = RUN_AI_TRIGGER_VARIANTS.BUTTON,
}) {
  const { run, state: pipelineState, pollProgress } = pipelineRunner;
  const activityId = activity?.id ?? null;
  const transcript = activity?.transcript ?? '';
  const outcomeNotes = activity?.outcome_notes ?? '';
  const isLocked = isActivitySignalsLocked(activity);

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
  const canRunAI = canRunAIAnalysis(activity, pipelineState);

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

    const isPill = variant === RUN_AI_TRIGGER_VARIANTS.PILL;

    if (effectiveState === 'running') {
      const isPolling = Boolean(pollProgress && pollProgress.max > 0);
      return (
        <Stack spacing={0.5} alignItems={isPill ? 'flex-start' : 'flex-end'}>
          {isPill ? (
            <ClickablePill label="Analyzing…" active disabled />
          ) : (
            <Button
              variant="contained"
              disabled
              startIcon={<CircularProgress size={16} color="inherit" />}
            >
              Analyzing…
            </Button>
          )}
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
          {isPill ? (
            <ClickablePill
              label={label}
              active
              onClick={handleOpenWizard}
              disabled={!canRunAI}
            />
          ) : (
            <Button
              variant="contained"
              onClick={handleOpenWizard}
              disabled={!canRunAI}
              startIcon={<ExperimentOutlined />}
            >
              {label}
            </Button>
          )}
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
  /** The activity: its id, transcript, notes and status (the lock). */
  activity: PropTypes.shape({
    id: PropTypes.string,
    transcript: PropTypes.string,
    outcome_notes: PropTypes.string,
    status: PropTypes.string,
  }),
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
  /** The trigger: "button" (default) or "pill" (RUN_AI_TRIGGER_VARIANTS). */
  variant: PropTypes.oneOf(Object.values(RUN_AI_TRIGGER_VARIANTS)),
  /** The objectives checked when the wizard opens (RunAIWizard). */
  defaultObjectives: PropTypes.shape({
    qualification: PropTypes.bool,
    nextSteps: PropTypes.bool,
  }),
};
