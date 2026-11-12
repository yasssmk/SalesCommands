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
import InfoNotice from 'components/display/InfoNotice';
import useUnsavedChanges from 'hooks/useUnsavedChanges';
import { UNSAVED_SCOPE } from 'utils/unsavedChanges';
import { PIPELINE_STATE } from 'hooks/usePipelineRunner';
import { canRunAIAnalysis } from 'sections/activities/workspace/RunAIAnalysisButton';
import {
  isTranscriptLocked,
  NOTES_FIELD,
  TRANSCRIPT_FIELD,
} from 'utils/activitySignalsLock';

// assets
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';

// ==============================|| ACTIVITY NOTES TAB ||============================== //

const FAILED_STATUSES = new Set(['PARSE_ERROR', 'LLM_ERROR', 'TIMEOUT']);
/** N6 — the read-only note's placeholder (it is written in the notes panel). */
export const NOTES_READ_PLACEHOLDER = 'No notes yet.';

export default function ActivityNotesTab({
  activity,
  onSave,
  pipelineRunner,
  lastRun,
  latestRun,
  runsByPipeline,
  onOpenWizard,
}) {
  const transcript = activity?.transcript ?? '';
  const outcomeNotes = activity?.outcome_notes ?? '';

  const { state: pipelineState, result: pipelineResult, error: pipelineError, reset: resetPipeline } = pipelineRunner;

  const [bannerDismissed, setBannerDismissed] = useState(false);

  // « Source / Notes » 2.4 — the transcript being edited is a PAGE source of
  // unsaved changes: an internal link asks first (2.3) and beforeunload is
  // prevented (2.2); a drawer opening keeps it (the page stays mounted).
  // N6: no longer the note — it is written (and autosaved) in the notes panel.
  const [transcriptDirty, setTranscriptDirty] = useState(false);
  useUnsavedChanges(transcriptDirty, { scope: UNSAVED_SCOPE.PAGE });

  // "Try again" opens the wizard of the band's Run AI pill (in the Source
  // header, lot 3 / 11 — the page owns its open state) under the same
  // predicate as the pill (3.2: runsByPipeline included).
  const handleOpenWizard = () => {
    if (canRunAIAnalysis(activity, pipelineState, runsByPipeline)) {
      onOpenWizard?.();
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
        {/* Notes section — ONE note per activity (« Source / Notes » 1.5),
            written in the notes panel (N6: the band's « Open notes » pill,
            the floating Notes button): READ-ONLY here — EditableTextBlock's
            read mode. It follows the activity's cache, which the panel's
            autosave updates. */}
        <EditableTextBlock
          label="Notes"
          field={NOTES_FIELD}
          initialValue={outcomeNotes}
          rows={5}
          placeholder={NOTES_READ_PLACEHOLDER}
          isLocked
        />

        {/* Transcript section — its own lock (5.12d: CANCELLED, so a
            transcript can be added after the call; 8g-7: or ANALYSED — no
            re-run, the transcript stays the analysed one). */}
        <EditableTextBlock
          label="Transcript"
          field={TRANSCRIPT_FIELD}
          initialValue={transcript}
          rows={15}
          placeholder="Paste the call transcript or email content here..."
          showCharCount
          onSave={onSave}
          isLocked={isTranscriptLocked(activity, lastRun)}
          onDirtyChange={setTranscriptDirty}
        />
        {lastRun && (
          <InfoNotice data-testid="transcript-analysed-notice">
            This transcript has already been analysed: it can no longer be changed.
          </InfoNotice>
        )}

        {/* Last analyzed caption */}
        {renderLastRunCaption()}

        {/* Failed/stuck run banner */}
        {renderLatestRunBanner()}

        {/* Already analysed (« Source / Notes » 1.6): the server's refusal is
            a business rule — INFORMATION (the shared InfoNotice, as the
            transcript-analysed notice above), never a red error, no
            « Try again » (an analysis is never re-run). */}
        {pipelineState === PIPELINE_STATE.INFO && pipelineError && (
          <InfoNotice data-testid="analysis-already-done-notice">{pipelineError}</InfoNotice>
        )}

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
  /** The per-pipeline successful runs (server state) — the Run AI predicate. */
  runsByPipeline: PropTypes.object,
  /** Opens the wizard of the Source band's Run AI pill ("Try again"). */
  onOpenWizard: PropTypes.func,
};
