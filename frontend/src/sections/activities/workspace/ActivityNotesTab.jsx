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
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// project imports
import EditableTextBlock from 'components/EditableTextBlock';
import { PIPELINE_STATE } from 'hooks/usePipelineRunner';
import RunAIWizard from 'sections/activities/workspace/RunAIWizard';

// assets
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import ExperimentOutlined from '@ant-design/icons/ExperimentOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';

// ==============================|| CONSTANTS ||============================== //

const MIN_TRANSCRIPT_LENGTH = 50;

// ==============================|| ACTIVITY NOTES TAB ||============================== //

const FAILED_STATUSES = new Set(['PARSE_ERROR', 'LLM_ERROR', 'TIMEOUT']);

export default function ActivityNotesTab({
  activity,
  onSave,
  isLocked,
  pipelineRunner,
  lastRun,
  latestRun,
  runsByPipeline,
}) {
  const activityId = activity?.id ?? null;
  const transcript = activity?.transcript ?? '';
  const outcomeNotes = activity?.outcome_notes ?? '';

  const { run, state: pipelineState, result: pipelineResult, error: pipelineError, pollProgress, reset: resetPipeline } = pipelineRunner;

  // --- Wizard open state ---
  const [wizardOpen, setWizardOpen] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);

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

  const renderLatestRunBanner = () => {
    if (bannerDismissed || pipelineState !== PIPELINE_STATE.IDLE) return null;
    if (!latestRun) return null;

    const isStuck = latestRun.status === 'RUNNING';
    const isFailed = FAILED_STATUSES.has(latestRun.status);
    if (!isStuck && !isFailed) return null;
    if (lastRun) return null;

    const dateStr = latestRun.last_run_at
      ? format(new Date(latestRun.last_run_at), 'MMM d, yyyy HH:mm')
      : '';
    const bannerMessage = isStuck
      ? `Last extraction stuck (${dateStr}). Extraction is still pending.`
      : `Last extraction failed (${dateStr}). Click Try Again to retry.`;

    return (
      <Alert
        severity="warning"
        icon={<WarningOutlined />}
        action={
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Button color="warning" size="small" onClick={handleOpenWizard}>
              Try again
            </Button>
            <IconButton size="small" aria-label="dismiss" color="inherit" onClick={() => setBannerDismissed(true)}>
              <CloseOutlined />
            </IconButton>
          </Stack>
        }
      >
        {bannerMessage}
      </Alert>
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

        {/* Failed/stuck run banner */}
        {renderLatestRunBanner()}

        {/* Extraction error */}
        {pipelineState === PIPELINE_STATE.ERROR && pipelineError && (
          <Alert
            severity="error"
            action={
              <Stack direction="row" spacing={0.5} alignItems="center">
                <Button color="error" size="small" onClick={handleOpenWizard}>
                  Try again
                </Button>
                <IconButton size="small" aria-label="close" color="inherit" onClick={resetPipeline}>
                  <CloseOutlined />
                </IconButton>
              </Stack>
            }
          >
            {pipelineError}
          </Alert>
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
    pollProgress: PropTypes.shape({
      attempt: PropTypes.number,
      max: PropTypes.number,
    }),
    reset: PropTypes.func.isRequired,
  }).isRequired,
  lastRun: PropTypes.object,
  latestRun: PropTypes.object,
  runsByPipeline: PropTypes.object,
};
