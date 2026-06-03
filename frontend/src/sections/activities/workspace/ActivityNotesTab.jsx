// frontend/src/sections/activities/workspace/ActivityNotesTab.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useRef, useEffect } from 'react';

// material-ui
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// project imports
import { updateActivity } from 'api/accounts/activities';
import {
  runActivityExtraction,
  EXTRACTION_STATUS,
  EXTRACTION_OUTCOME_CODES,
} from 'api/aiPipelines/activityExtraction';
import { displayErrorSnackbar } from 'utils/displayError';
import ActivityNotesExtractionPreviewModal from 'sections/activities/workspace/ActivityNotesExtractionPreviewModal';

// assets
import ExperimentOutlined from '@ant-design/icons/ExperimentOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import LoadingOutlined from '@ant-design/icons/LoadingOutlined';

// ==============================|| CONSTANTS ||============================== //

const AUTOSAVE_DEBOUNCE_MS = 1500;
const MIN_TRANSCRIPT_LENGTH = 50;

// ==============================|| AUTOSAVE STATES ||============================== //

const SAVE_STATE = {
  IDLE: 'idle',
  SAVING: 'saving',
  SAVED: 'saved',
  ERROR: 'error',
};

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
  // --- Transcript local state ---
  const [localTranscript, setLocalTranscript] = useState(activity?.transcript || '');
  const [saveState, setSaveState] = useState(SAVE_STATE.IDLE);
  const debounceRef = useRef(null);
  const lastSavedRef = useRef(activity?.transcript || '');

  // --- Extraction state ---
  const [extractionState, setExtractionState] = useState(EXTRACTION_STATE.IDLE);
  const [extractionResult, setExtractionResult] = useState(null);
  const [extractionError, setExtractionError] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [lastExtractedHash, setLastExtractedHash] = useState(null);

  // Sync from parent when activity data changes (e.g. SWR revalidation)
  useEffect(() => {
    if (activity?.transcript != null && activity.transcript !== lastSavedRef.current) {
      setLocalTranscript(activity.transcript);
      lastSavedRef.current = activity.transcript;
    }
  }, [activity?.transcript]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  // --- Autosave logic ---
  const persistTranscript = useCallback(
    async (value) => {
      if (isLocked) return;
      if (extractionState === EXTRACTION_STATE.RUNNING) return;

      const trimmed = value.trim();
      if (trimmed === (lastSavedRef.current || '').trim()) {
        return;
      }

      setSaveState(SAVE_STATE.SAVING);
      try {
        const success = await onSave('transcript', trimmed || null);
        if (success) {
          lastSavedRef.current = trimmed;
          setSaveState(SAVE_STATE.SAVED);
          setTimeout(() => setSaveState((s) => (s === SAVE_STATE.SAVED ? SAVE_STATE.IDLE : s)), 3000);
        } else {
          setSaveState(SAVE_STATE.ERROR);
        }
      } catch {
        setSaveState(SAVE_STATE.ERROR);
      }
    },
    [isLocked, extractionState, onSave],
  );

  const handleTranscriptChange = useCallback(
    (e) => {
      const value = e.target.value;
      setLocalTranscript(value);

      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      debounceRef.current = setTimeout(() => {
        persistTranscript(value);
      }, AUTOSAVE_DEBOUNCE_MS);
    },
    [persistTranscript],
  );

  const handleTranscriptBlur = useCallback(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    persistTranscript(localTranscript);
  }, [persistTranscript, localTranscript]);

  // --- Run AI Analysis ---
  const trimmedTranscript = localTranscript.trim();
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
      if (!activity?.id) return;

      setPreviewLoading(true);
      setPreviewOpen(false);
      setExtractionState(EXTRACTION_STATE.RUNNING);
      setExtractionResult(null);
      setExtractionError(null);

      try {
        const result = await runActivityExtraction(
          activity.id,
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
          setLastExtractedHash(trimmedTranscript);
        } else if (result.code === EXTRACTION_OUTCOME_CODES.ALREADY_EXTRACTED) {
          setExtractionState(EXTRACTION_STATE.ALREADY_EXTRACTED);
          setExtractionResult(result.data || null);
          setLastExtractedHash(trimmedTranscript);
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
    [activity?.id, trimmedTranscript],
  );

  // Transcript modified since last extraction?
  const transcriptModifiedSinceRun =
    lastExtractedHash != null && trimmedTranscript !== lastExtractedHash;

  // --- Render helpers ---
  const renderSaveIndicator = () => {
    if (isLocked) return null;

    switch (saveState) {
      case SAVE_STATE.SAVING:
        return (
          <Typography variant="caption" color="text.secondary">
            <LoadingOutlined style={{ marginRight: 4 }} />
            Saving…
          </Typography>
        );
      case SAVE_STATE.SAVED:
        return (
          <Typography variant="caption" color="success.main">
            <CheckCircleOutlined style={{ marginRight: 4 }} />
            Saved
          </Typography>
        );
      case SAVE_STATE.ERROR:
        return (
          <Typography variant="caption" color="error.main">
            <CloseCircleOutlined style={{ marginRight: 4 }} />
            Error saving
          </Typography>
        );
      default:
        return null;
    }
  };

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

  // ==============================|| RENDER ||============================== //

  return (
    <Box sx={{ p: 0 }}>
      <Stack spacing={3}>
        {/* Transcript section */}
        <Stack spacing={1.5}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle1" fontWeight={600}>
              Transcript
            </Typography>
            {renderSaveIndicator()}
          </Stack>

          <TextField
            multiline
            minRows={10}
            maxRows={30}
            fullWidth
            value={localTranscript}
            onChange={handleTranscriptChange}
            onBlur={handleTranscriptBlur}
            placeholder={
              isLocked
                ? 'No transcript recorded.'
                : 'Paste your call transcript here…'
            }
            disabled={isLocked}
            inputProps={{
              'data-testid': 'transcript-input',
              style: { fontSize: 14, lineHeight: 1.7 },
            }}
          />
        </Stack>

        {/* Transcript modified warning */}
        {transcriptModifiedSinceRun && (
          <Alert severity="info" variant="outlined">
            Transcript modified since last run — re-running will create new signals
            alongside existing ones.
          </Alert>
        )}

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
        transcript={localTranscript}
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
    status: PropTypes.string,
  }),
  onSave: PropTypes.func.isRequired,
  isLocked: PropTypes.bool,
};
