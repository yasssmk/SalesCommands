// frontend/src/sections/activities/workspace/ActivityNotesExtractionPreviewModal.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect, useRef, useCallback } from 'react';
import { format } from 'date-fns';

// material-ui
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';

// assets
import SendOutlined from '@ant-design/icons/SendOutlined';
import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';

// ==============================|| CONSTANTS ||============================== //

const MIN_TRANSCRIPT_LENGTH = 50;
const NOTES_SEPARATOR = '\n\n---\nSDR Notes:\n';
const HASH_DEBOUNCE_MS = 300;

// ==============================|| HELPERS ||============================== //

async function computeContentHash(activityId, content) {
  if (!activityId || !content) return null;
  try {
    const text = `${activityId}::${content}`;
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  } catch {
    return null;
  }
}

// ==============================|| EXTRACTION PREVIEW MODAL ||============================== //

export default function ActivityNotesExtractionPreviewModal({
  open,
  activityId,
  transcript,
  outcomeNotes,
  lastRun,
  onCancel,
  onConfirm,
  loading,
}) {
  const [curatedText, setCuratedText] = useState('');
  const [includeNotes, setIncludeNotes] = useState(false);
  const [dupWarning, setDupWarning] = useState(false);
  const hashDebounceRef = useRef(null);

  const hasNotes = Boolean(outcomeNotes?.trim());

  useEffect(() => {
    if (open) {
      setCuratedText(transcript || '');
      setIncludeNotes(false);
      setDupWarning(false);
    }
  }, [open, transcript]);

  const buildFinalContent = useCallback(
    (text, withNotes) => {
      const trimmed = text.trim();
      if (withNotes && hasNotes) {
        return trimmed + NOTES_SEPARATOR + outcomeNotes.trim();
      }
      return trimmed;
    },
    [hasNotes, outcomeNotes],
  );

  // Debounced hash comparison
  useEffect(() => {
    if (!open || !lastRun?.input_hash || !activityId) {
      setDupWarning(false);
      return;
    }

    if (hashDebounceRef.current) {
      clearTimeout(hashDebounceRef.current);
    }

    hashDebounceRef.current = setTimeout(async () => {
      const finalContent = buildFinalContent(curatedText, includeNotes);
      const hash = await computeContentHash(activityId, finalContent);
      setDupWarning(hash !== null && hash === lastRun.input_hash);
    }, HASH_DEBOUNCE_MS);

    return () => {
      if (hashDebounceRef.current) {
        clearTimeout(hashDebounceRef.current);
      }
    };
  }, [open, curatedText, includeNotes, activityId, lastRun?.input_hash, buildFinalContent]);

  const trimmedLength = curatedText.trim().length;
  const isTooShort = trimmedLength > 0 && trimmedLength < MIN_TRANSCRIPT_LENGTH;
  const isEmpty = trimmedLength === 0;
  const canSend = !isEmpty && !isTooShort && !loading;

  const handleConfirm = () => {
    if (canSend) {
      onConfirm(buildFinalContent(curatedText, includeNotes));
    }
  };

  const sendButtonTooltip = isEmpty
    ? 'Transcript cannot be empty'
    : isTooShort
      ? `Transcript too short (min ${MIN_TRANSCRIPT_LENGTH} characters)`
      : '';

  const dupAlertMessage = (() => {
    if (!dupWarning || !lastRun) return null;
    const parts = ['Analysis already performed'];
    if (lastRun.last_run_at) {
      parts[0] += ` on ${format(new Date(lastRun.last_run_at), 'MMM d, yyyy HH:mm')}`;
    }
    if (lastRun.last_run_by?.full_name) {
      parts[0] += ` by ${lastRun.last_run_by.full_name}`;
    }
    return parts[0];
  })();

  return (
    <Modal
      open={open}
      onClose={loading ? undefined : onCancel}
      aria-labelledby="modal-extraction-preview-title"
      sx={{
        '& .MuiPaper-root:focus': { outline: 'none' },
      }}
    >
      <MainCard
        sx={{
          width: 'calc(100% - 48px)',
          minWidth: 400,
          maxWidth: 680,
          maxHeight: 'calc(100vh - 48px)',
          overflow: 'auto',
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
        }}
        modal
        content={false}
      >
        {/* Header */}
        <Box sx={{ p: 2.5, pb: 2 }}>
          <Typography variant="h5" id="modal-extraction-preview-title">
            Review before sending to AI
          </Typography>
        </Box>

        <Divider />

        {/* Body */}
        <Box sx={{ p: 2.5 }}>
          <Stack spacing={2.5}>
            {/* Info banner */}
            <Stack
              direction="row"
              spacing={1}
              sx={{
                p: 1.5,
                borderRadius: 1,
                bgcolor: 'info.lighter',
                color: 'info.dark',
              }}
            >
              <InfoCircleOutlined style={{ fontSize: 16, marginTop: 2, flexShrink: 0 }} />
              <Typography variant="body2">
                Edit below to remove anything you don&apos;t want to send to the AI
                (confidential names, third parties, NDA details, etc.).
                Your original transcript stays untouched.
              </Typography>
            </Stack>

            {/* Dedup warning */}
            {dupWarning && dupAlertMessage && (
              <Alert severity="warning">{dupAlertMessage}</Alert>
            )}

            {/* Editable transcript */}
            <TextField
              multiline
              rows={15}
              fullWidth
              value={curatedText}
              onChange={(e) => setCuratedText(e.target.value)}
              placeholder="Transcript content..."
              disabled={loading}
              inputProps={{
                'data-testid': 'curated-transcript-input',
                style: { fontFamily: 'monospace', fontSize: 13 },
              }}
              error={isTooShort}
              helperText={
                isTooShort
                  ? `Transcript too short (min ${MIN_TRANSCRIPT_LENGTH} characters)`
                  : undefined
              }
            />

            {/* Character count */}
            <Typography variant="caption" color="text.secondary">
              {trimmedLength.toLocaleString()} characters
            </Typography>

            {/* Include notes checkbox */}
            <FormControlLabel
              control={
                <Checkbox
                  checked={includeNotes}
                  onChange={(e) => setIncludeNotes(e.target.checked)}
                  disabled={!hasNotes}
                  size="small"
                />
              }
              label={
                <Typography variant="body2" color="text.secondary">
                  Include my notes{' '}
                  {hasNotes
                    ? '(available on this activity)'
                    : '(none on this activity)'}
                </Typography>
              }
            />
          </Stack>
        </Box>

        <Divider />

        {/* Actions */}
        <Box sx={{ p: 2.5 }}>
          <Stack direction="row" spacing={2} justifyContent="flex-end">
            <Button color="error" onClick={onCancel} disabled={loading}>
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleConfirm}
              disabled={!canSend}
              title={sendButtonTooltip}
              startIcon={
                loading ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <SendOutlined />
                )
              }
            >
              {loading ? 'Sending...' : 'Send for analysis'}
            </Button>
          </Stack>
        </Box>
      </MainCard>
    </Modal>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityNotesExtractionPreviewModal.propTypes = {
  open: PropTypes.bool.isRequired,
  activityId: PropTypes.string,
  transcript: PropTypes.string,
  outcomeNotes: PropTypes.string,
  lastRun: PropTypes.shape({
    last_run_at: PropTypes.string,
    last_run_by: PropTypes.shape({
      id: PropTypes.string,
      full_name: PropTypes.string,
    }),
    input_hash: PropTypes.string,
  }),
  onCancel: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};
