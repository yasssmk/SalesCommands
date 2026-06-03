// frontend/src/sections/activities/workspace/ActivityNotesExtractionPreviewModal.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
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

// ==============================|| EXTRACTION PREVIEW MODAL ||============================== //

export default function ActivityNotesExtractionPreviewModal({
  open,
  transcript,
  onCancel,
  onConfirm,
  loading,
}) {
  const [curatedText, setCuratedText] = useState('');

  useEffect(() => {
    if (open) {
      setCuratedText(transcript || '');
    }
  }, [open, transcript]);

  const trimmedLength = curatedText.trim().length;
  const isTooShort = trimmedLength > 0 && trimmedLength < MIN_TRANSCRIPT_LENGTH;
  const isEmpty = trimmedLength === 0;
  const canSend = !isEmpty && !isTooShort && !loading;

  const handleConfirm = () => {
    if (canSend) {
      onConfirm(curatedText.trim());
    }
  };

  const sendButtonTooltip = isEmpty
    ? 'Transcript cannot be empty'
    : isTooShort
      ? `Transcript too short (min ${MIN_TRANSCRIPT_LENGTH} characters)`
      : '';

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
  transcript: PropTypes.string,
  onCancel: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};
