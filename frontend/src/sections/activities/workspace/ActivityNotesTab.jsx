// frontend/src/sections/activities/workspace/ActivityNotesTab.jsx

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';
import { format } from 'date-fns';

// material-ui
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import EditableTextBlock from 'components/EditableTextBlock';
import { PIPELINE_STATE } from 'hooks/usePipelineRunner';
import RunAIAnalysisButton, { canRunAIAnalysis } from 'sections/activities/workspace/RunAIAnalysisButton';

// assets
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';

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

  const { state: pipelineState, result: pipelineResult, error: pipelineError, reset: resetPipeline } = pipelineRunner;

  // --- Wizard open state (controlled: "Try again" opens it too) ---
  const [wizardOpen, setWizardOpen] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  // "Try again" opens the wizard under the same predicate as the button.
  const handleOpenWizard = () => {
    if (canRunAIAnalysis({ isLocked, transcript, pipelineState })) {
      setWizardOpen(true);
    }
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

        {/* Run AI Analysis button (+ its 2-step wizard) */}
        <Box display="flex" justifyContent="flex-end">
          <RunAIAnalysisButton
            activityId={activityId}
            transcript={transcript}
            outcomeNotes={outcomeNotes}
            isLocked={isLocked}
            pipelineRunner={pipelineRunner}
            lastRun={lastRun}
            runsByPipeline={runsByPipeline}
            open={wizardOpen}
            onOpenChange={setWizardOpen}
          />
        </Box>
      </Stack>
    </Box>
  );
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
