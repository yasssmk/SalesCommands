// frontend/src/sections/activities/workspace/ActivityNotesTab.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';
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
import {
  runActivityExtraction,
  EXTRACTION_STATUS,
  EXTRACTION_OUTCOME_CODES,
} from 'api/aiPipelines/activityExtraction';
import { useGetLastExtractionRun } from 'api/aiPipelines/lastRun';
import ActivityNotesExtractionPreviewModal from 'sections/activities/workspace/ActivityNotesExtractionPreviewModal';

// assets
import ExperimentOutlined from '@ant-design/icons/ExperimentOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';

// ==============================|| CONSTANTS ||============================== //

const MIN_TRANSCRIPT_LENGTH = 50;

// ==============================|| EXTRACTION STATES ||============================== //

const EXTRACTION_STATE = {
  IDLE: 'idle',
  RUNNING: 'running',
  SUCCESS: 'success',
  PARTIAL: 'partial',
  ALREADY_EXTRACTED: 'already_extracted',
  ERROR: 'error',
};

// ==============================|| ACTIVITY NOTES TAB ||============================== //

export default function ActivityNotesTab({ activity, onSave, isLocked }) {
  const activityId = activity?.id ?? null;
  const transcript = activity?.transcript ?? '';
  const outcomeNotes = activity?.outcome_notes ?? '';

  // --- Last run metadata ---
  const { lastRun, mutateLastRun } = useGetLastExtractionRun(activityId);

  // --- Extraction state ---
  const [extractionState, setExtractionState] = useState(EXTRACTION_STATE.IDLE);
  const [extractionResult, setExtractionResult] = useState(null);
  const [extractionError, setExtractionError] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  // --- Run AI Analysis ---
  const trimmedTranscript = transcript.trim();
  const canRunAI =
    !isLocked &&
    trimmedTranscript.length >= MIN_TRANSCRIPT_LENGTH &&
    extractionState !== EXTRACTION_STATE.RUNNING;

  const handleOpenPreview = () => {
    if (canRunAI) {
      setPreviewOpen(true);
    }
  };

  const handleCancelPreview = () => {
    setPreviewOpen(false);
  };

  const handleConfirmExtraction = useCallback(
    async (curatedTranscript) => {
      if (!activityId) return;

      setPreviewLoading(true);
      setPreviewOpen(false);
      setExtractionState(EXTRACTION_STATE.RUNNING);
      setExtractionResult(null);
      setExtractionError(null);

      try {
        const result = await runActivityExtraction(
          activityId,
          curatedTranscript,
          null,
        );

        if (result.success) {
          const data = result.data || {};
          const globalStatus = data.status;

          if (globalStatus === EXTRACTION_STATUS.PARTIAL) {
            setExtractionState(EXTRACTION_STATE.PARTIAL);
          } else {
            setExtractionState(EXTRACTION_STATE.SUCCESS);
          }
          setExtractionResult(data);
          mutateLastRun();
        } else if (result.code === EXTRACTION_OUTCOME_CODES.ALREADY_EXTRACTED) {
          setExtractionState(EXTRACTION_STATE.ALREADY_EXTRACTED);
          setExtractionResult(result.data || null);
        } else if (result.code === EXTRACTION_OUTCOME_CODES.TIMEOUT_PENDING) {
          setExtractionState(EXTRACTION_STATE.ERROR);
          setExtractionError(
            'Analysis is taking longer than expected. It will continue in the background — check back in a moment.',
          );
        } else {
          setExtractionState(EXTRACTION_STATE.ERROR);
          setExtractionError(result.error || 'Extraction failed. Please try again.');
        }
      } catch (err) {
        setExtractionState(EXTRACTION_STATE.ERROR);
        setExtractionError(err?.message || 'An unexpected error occurred.');
      } finally {
        setPreviewLoading(false);
      }
    },
    [activityId, mutateLastRun],
  );

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

    if (extractionState === EXTRACTION_STATE.RUNNING) {
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

    if (
      extractionState === EXTRACTION_STATE.SUCCESS ||
      extractionState === EXTRACTION_STATE.PARTIAL ||
      extractionState === EXTRACTION_STATE.ALREADY_EXTRACTED
    ) {
      const qualCount =
        extractionResult?.qualification_run?.created_signals_count ?? 0;
      const nsCount =
        extractionResult?.next_steps_run?.created_signals_count ?? 0;

      const label =
        extractionState === EXTRACTION_STATE.ALREADY_EXTRACTED
          ? 'Already extracted'
          : extractionState === EXTRACTION_STATE.PARTIAL
            ? `Partial · qualif (${qualCount}) + next-step (${nsCount})`
            : `Last run · qualif (${qualCount}) + next-step (${nsCount})`;

      return (
        <Tooltip title={canRunAI ? 'Re-run with current transcript' : tooltipTitle}>
          <span>
            <Button
              variant="outlined"
              onClick={handleOpenPreview}
              disabled={!canRunAI}
              startIcon={
                extractionState === EXTRACTION_STATE.PARTIAL ? (
                  <WarningOutlined />
                ) : (
                  <CheckCircleOutlined />
                )
              }
              color={extractionState === EXTRACTION_STATE.PARTIAL ? 'warning' : 'success'}
            >
              {label}
            </Button>
          </span>
        </Tooltip>
      );
    }

    if (extractionState === EXTRACTION_STATE.ERROR) {
      return (
        <Tooltip title={canRunAI ? 'Retry extraction' : tooltipTitle}>
          <span>
            <Button
              variant="outlined"
              color="error"
              onClick={handleOpenPreview}
              disabled={!canRunAI}
              startIcon={<CloseCircleOutlined />}
            >
              Run failed · Retry
            </Button>
          </span>
        </Tooltip>
      );
    }

    return (
      <Tooltip title={tooltipTitle}>
        <span>
          <Button
            variant="contained"
            onClick={handleOpenPreview}
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
    if (
      extractionState !== EXTRACTION_STATE.SUCCESS &&
      extractionState !== EXTRACTION_STATE.PARTIAL &&
      extractionState !== EXTRACTION_STATE.ALREADY_EXTRACTED
    ) {
      return null;
    }

    const qualCount =
      extractionResult?.qualification_run?.created_signals_count ?? 0;
    const nsCount =
      extractionResult?.next_steps_run?.created_signals_count ?? 0;

    const isAlready = extractionState === EXTRACTION_STATE.ALREADY_EXTRACTED;
    const isPartial = extractionState === EXTRACTION_STATE.PARTIAL;

    return (
      <Alert
        severity={isPartial ? 'warning' : isAlready ? 'info' : 'success'}
        sx={{ mt: 1 }}
      >
        {isAlready
          ? 'This transcript was already processed.'
          : isPartial
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
        {extractionState === EXTRACTION_STATE.ERROR && extractionError && (
          <Alert severity="error">{extractionError}</Alert>
        )}

        {/* Extraction result */}
        {renderExtractionResult()}

        {/* Run AI Analysis button */}
        <Box display="flex" justifyContent="flex-end">
          {renderRunButton()}
        </Box>
      </Stack>

      {/* Curation modal */}
      <ActivityNotesExtractionPreviewModal
        open={previewOpen}
        activityId={activityId}
        transcript={transcript}
        outcomeNotes={outcomeNotes}
        lastRun={lastRun}
        onCancel={handleCancelPreview}
        onConfirm={handleConfirmExtraction}
        loading={previewLoading}
      />
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
};
