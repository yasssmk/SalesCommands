// frontend/src/sections/activities/workspace/ActivityNotesTab.jsx

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';
import { format } from 'date-fns';

// material-ui
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// project imports
import EditableTextBlock from 'components/EditableTextBlock';
import { PIPELINE_STATE } from 'hooks/usePipelineRunner';
import RunAIWizard from 'sections/activities/workspace/RunAIWizard';

// assets
import ExperimentOutlined from '@ant-design/icons/ExperimentOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';

// ==============================|| CONSTANTS ||============================== //

const MIN_TRANSCRIPT_LENGTH = 50;

// ==============================|| ACTIVITY NOTES TAB ||============================== //

export default function ActivityNotesTab({
  activity,
  onSave,
  isLocked,
  pipelineRunner,
  lastRun,
  runsByPipeline,
}) {
  const activityId = activity?.id ?? null;
  const transcript = activity?.transcript ?? '';
  const outcomeNotes = activity?.outcome_notes ?? '';

  const { run, state: pipelineState, result: pipelineResult, error: pipelineError } = pipelineRunner;

  // --- Wizard open state ---
  const [wizardOpen, setWizardOpen] = useState(false);

  // --- Derive effective display state from pipelineState + lastRun ---
  const effectiveState = deriveEffectiveState(pipelineState, lastRun);

  // --- Run AI Analysis ---
  const trimmedTranscript = transcript.trim();
  const canRunAI =
    !isLocked &&
    trimmedTranscript.length >= MIN_TRANSCRIPT_LENGTH &&
    pipelineState !== PIPELINE_STATE.RUNNING;

  const handleOpenWizard = () => {
    if (canRunAI) {
      setWizardOpen(true);
    }
  };

  const handleCancelWizard = () => {
    setWizardOpen(false);
  };

  const handleConfirmWizard = (curatedTranscript) => {
    setWizardOpen(false);
    run(activityId, curatedTranscript);
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
      return (
        <Button
          variant="contained"
          disabled
          startIcon={<CircularProgress size={16} color="inherit" />}
        >
          Analyzing…
        </Button>
      );
    }

    if (effectiveState === 'success' || effectiveState === 'partial') {
      const qualCount = getQualCount(pipelineState, pipelineResult, lastRun);
      const nsCount = getNsCount(pipelineState, pipelineResult, lastRun);
      const isPartial = effectiveState === 'partial';

      const label = isPartial
        ? `Partial · qualif (${qualCount}) + next-step (${nsCount})`
        : `Last run · qualif (${qualCount}) + next-step (${nsCount})`;

      return (
        <Tooltip title={canRunAI ? 'Re-run with current transcript' : tooltipTitle}>
          <span>
            <Button
              variant="outlined"
              onClick={handleOpenWizard}
              disabled={!canRunAI}
              startIcon={isPartial ? <WarningOutlined /> : <CheckCircleOutlined />}
              color={isPartial ? 'warning' : 'success'}
            >
              {label}
            </Button>
          </span>
        </Tooltip>
      );
    }

    if (effectiveState === 'error') {
      return (
        <Tooltip title={canRunAI ? 'Retry extraction' : tooltipTitle}>
          <span>
            <Button
              variant="outlined"
              color="error"
              onClick={handleOpenWizard}
              disabled={!canRunAI}
              startIcon={<CloseCircleOutlined />}
            >
              Run failed · Retry
            </Button>
          </span>
        </Tooltip>
      );
    }

    // idle — no lastRun
    return (
      <Tooltip title={tooltipTitle}>
        <span>
          <Button
            variant="contained"
            onClick={handleOpenWizard}
            disabled={!canRunAI}
            startIcon={<ExperimentOutlined />}
          >
            Run AI Analysis
          </Button>
        </span>
      </Tooltip>
    );
  };

  const renderExtractionResult = () => {
    if (pipelineState !== PIPELINE_STATE.SUCCESS && pipelineState !== PIPELINE_STATE.PARTIAL) {
      return null;
    }

    const qualCount = pipelineResult?.qualification_run?.created_signals_count ?? 0;
    const nsCount = pipelineResult?.next_steps_run?.created_signals_count ?? 0;
    const isPartial = pipelineState === PIPELINE_STATE.PARTIAL;

    return (
      <Alert severity={isPartial ? 'warning' : 'success'} sx={{ mt: 1 }}>
        {isPartial
          ? `Partial extraction completed — ${qualCount} qualification signal(s) + ${nsCount} next-step suggestion(s).`
          : `${qualCount} qualification signal(s) + ${nsCount} next-step suggestion(s) extracted.`}
      </Alert>
    );
  };

  const renderLastRunCaption = () => {
    if (!lastRun?.last_run_at) return null;

    const dateStr = format(new Date(lastRun.last_run_at), 'MMM d, yyyy HH:mm');
    const byStr = lastRun.last_run_by?.full_name
      ? ` by ${lastRun.last_run_by.full_name}`
      : '';

    return (
      <Typography variant="caption" color="text.secondary">
        Last analyzed on {dateStr}{byStr}
      </Typography>
    );
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Box sx={{ p: 0 }}>
      <Stack spacing={3}>
        {/* Notes section */}
        <EditableTextBlock
          label="Notes"
          field="outcome_notes"
          initialValue={outcomeNotes}
          rows={5}
          placeholder="Capture key takeaways, observations, decisions made during the call..."
          onSave={onSave}
          isLocked={isLocked}
        />

        {/* Transcript section */}
        <EditableTextBlock
          label="Transcript"
          field="transcript"
          initialValue={transcript}
          rows={15}
          placeholder="Paste the call transcript or email content here..."
          showCharCount
          onSave={onSave}
          isLocked={isLocked}
        />

        {/* Last analyzed caption */}
        {renderLastRunCaption()}

        {/* Extraction error */}
        {pipelineState === PIPELINE_STATE.ERROR && pipelineError && (
          <Alert severity="error">{pipelineError}</Alert>
        )}

        {/* Extraction result */}
        {renderExtractionResult()}

        {/* Run AI Analysis button */}
        <Box display="flex" justifyContent="flex-end">
          {renderRunButton()}
        </Box>
      </Stack>

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
      />
    </Box>
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

function getQualCount(pipelineState, pipelineResult, lastRun) {
  if (pipelineState === PIPELINE_STATE.SUCCESS || pipelineState === PIPELINE_STATE.PARTIAL) {
    return pipelineResult?.qualification_run?.created_signals_count ?? 0;
  }
  return lastRun?.created_signals_count ?? 0;
}

function getNsCount(pipelineState, pipelineResult, lastRun) {
  if (pipelineState === PIPELINE_STATE.SUCCESS || pipelineState === PIPELINE_STATE.PARTIAL) {
    return pipelineResult?.next_steps_run?.created_signals_count ?? 0;
  }
  return 0;
}

// ==============================|| PROP TYPES ||============================== //

ActivityNotesTab.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    transcript: PropTypes.string,
    outcome_notes: PropTypes.string,
    status: PropTypes.string,
  }),
  onSave: PropTypes.func.isRequired,
  isLocked: PropTypes.bool,
  pipelineRunner: PropTypes.shape({
    run: PropTypes.func.isRequired,
    state: PropTypes.string.isRequired,
    result: PropTypes.object,
    error: PropTypes.string,
    reset: PropTypes.func.isRequired,
  }).isRequired,
  lastRun: PropTypes.object,
  runsByPipeline: PropTypes.object,
};
