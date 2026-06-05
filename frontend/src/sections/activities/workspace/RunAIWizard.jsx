// frontend/src/sections/activities/workspace/RunAIWizard.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect, useRef, useCallback } from 'react';
import { formatDistanceToNow } from 'date-fns';

// material-ui
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
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
import ArrowLeftOutlined from '@ant-design/icons/ArrowLeftOutlined';
import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';

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

function formatTimeAgo(isoDate) {
  if (!isoDate) return '';
  try {
    return formatDistanceToNow(new Date(isoDate), { addSuffix: true });
  } catch {
    return '';
  }
}

// ==============================|| STEP 1 — OBJECTIVES ||============================== //

function StepObjectives({
  qualificationChecked,
  setQualificationChecked,
  nextStepsChecked,
  setNextStepsChecked,
  runsByPipeline,
  onContinue,
  onCancel,
}) {
  const qualRun = runsByPipeline?.TRANSCRIPT_SIGNALS;
  const nsRun = runsByPipeline?.NEXT_STEPS;
  const qualAlreadyExtracted = Boolean(qualRun);
  const nsAlreadyExtracted = Boolean(nsRun);

  const hasActiveSelection =
    (qualificationChecked && !qualAlreadyExtracted) ||
    (nextStepsChecked && !nsAlreadyExtracted);

  return (
    <Box sx={{ p: 2.5 }}>
      <Stack spacing={2.5}>
        <Typography variant="body1" fontWeight={500}>
          What do you want to extract from this transcript?
        </Typography>

        <Stack spacing={1}>
          <FormControlLabel
            control={
              <Checkbox
                checked={qualificationChecked || qualAlreadyExtracted}
                onChange={(e) => setQualificationChecked(e.target.checked)}
                disabled={qualAlreadyExtracted}
                size="small"
              />
            }
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="body2">
                  Qualification signals (Pain, Objective, Impact, TechStack, Blocker)
                </Typography>
                {qualAlreadyExtracted && (
                  <Typography variant="caption" color="success.main" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <CheckCircleOutlined style={{ fontSize: 12 }} />
                    Already extracted · {formatTimeAgo(qualRun.last_run_at)}
                  </Typography>
                )}
              </Stack>
            }
          />

          <FormControlLabel
            control={
              <Checkbox
                checked={nextStepsChecked || nsAlreadyExtracted}
                onChange={(e) => setNextStepsChecked(e.target.checked)}
                disabled={nsAlreadyExtracted}
                size="small"
              />
            }
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="body2">
                  Next-step suggestions
                </Typography>
                {nsAlreadyExtracted && (
                  <Typography variant="caption" color="success.main" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <CheckCircleOutlined style={{ fontSize: 12 }} />
                    Already extracted · {formatTimeAgo(nsRun.last_run_at)}
                  </Typography>
                )}
              </Stack>
            }
          />
        </Stack>

        <Stack direction="row" spacing={2} justifyContent="flex-end">
          <Button color="error" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={onContinue}
            disabled={!hasActiveSelection}
          >
            Continue
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

StepObjectives.propTypes = {
  qualificationChecked: PropTypes.bool.isRequired,
  setQualificationChecked: PropTypes.func.isRequired,
  nextStepsChecked: PropTypes.bool.isRequired,
  setNextStepsChecked: PropTypes.func.isRequired,
  runsByPipeline: PropTypes.object,
  onContinue: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};

// ==============================|| STEP 2 — CURATION ||============================== //

function StepCuration({
  activityId,
  curatedText,
  setCuratedText,
  includeNotes,
  setIncludeNotes,
  hasNotes,
  lastRun,
  buildFinalContent,
  onBack,
  onConfirm,
}) {
  const [dupWarning, setDupWarning] = useState(false);
  const hashDebounceRef = useRef(null);

  useEffect(() => {
    if (!lastRun?.input_hash || !activityId) {
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
  }, [curatedText, includeNotes, activityId, lastRun?.input_hash, buildFinalContent]);

  const trimmedLength = curatedText.trim().length;
  const isTooShort = trimmedLength > 0 && trimmedLength < MIN_TRANSCRIPT_LENGTH;
  const isEmpty = trimmedLength === 0;
  const canSend = !isEmpty && !isTooShort;

  const handleConfirm = () => {
    if (canSend) {
      onConfirm(buildFinalContent(curatedText, includeNotes));
    }
  };

  const dupAlertMessage = (() => {
    if (!dupWarning || !lastRun) return null;
    let msg = 'Analysis already performed';
    if (lastRun.last_run_at) {
      msg += ` · ${formatTimeAgo(lastRun.last_run_at)}`;
    }
    return msg;
  })();

  return (
    <Box sx={{ p: 2.5 }}>
      <Stack spacing={2.5}>
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

        {dupWarning && dupAlertMessage && (
          <Alert severity="warning">{dupAlertMessage}</Alert>
        )}

        <TextField
          multiline
          rows={15}
          fullWidth
          value={curatedText}
          onChange={(e) => setCuratedText(e.target.value)}
          placeholder="Transcript content..."
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

        <Typography variant="caption" color="text.secondary">
          {trimmedLength.toLocaleString()} characters
        </Typography>

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

        <Stack direction="row" spacing={2} justifyContent="flex-end">
          <Button
            onClick={onBack}
            startIcon={<ArrowLeftOutlined />}
          >
            Back
          </Button>
          <Button
            variant="contained"
            onClick={handleConfirm}
            disabled={!canSend}
            startIcon={<SendOutlined />}
          >
            Run analysis
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

StepCuration.propTypes = {
  activityId: PropTypes.string,
  curatedText: PropTypes.string.isRequired,
  setCuratedText: PropTypes.func.isRequired,
  includeNotes: PropTypes.bool.isRequired,
  setIncludeNotes: PropTypes.func.isRequired,
  hasNotes: PropTypes.bool.isRequired,
  lastRun: PropTypes.object,
  buildFinalContent: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
};

// ==============================|| RUN AI WIZARD ||============================== //

export default function RunAIWizard({
  open,
  activityId,
  transcript,
  outcomeNotes,
  lastRun,
  runsByPipeline,
  onCancel,
  onConfirm,
}) {
  const [step, setStep] = useState(1);
  const [qualificationChecked, setQualificationChecked] = useState(true);
  const [nextStepsChecked, setNextStepsChecked] = useState(true);
  const [curatedText, setCuratedText] = useState('');
  const [includeNotes, setIncludeNotes] = useState(false);

  const hasNotes = Boolean(outcomeNotes?.trim());

  useEffect(() => {
    if (open) {
      setStep(1);
      setQualificationChecked(true);
      setNextStepsChecked(true);
      setCuratedText(transcript || '');
      setIncludeNotes(false);
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

  const handleConfirm = (finalContent) => {
    onConfirm(finalContent, {
      qualification: qualificationChecked,
      nextSteps: nextStepsChecked,
    });
  };

  const stepTitles = {
    1: 'Run AI Analysis — Select objectives',
    2: 'Run AI Analysis — Review before sending',
  };

  return (
    <Modal
      open={open}
      onClose={onCancel}
      aria-labelledby="modal-run-ai-wizard-title"
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
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h5" id="modal-run-ai-wizard-title">
              {stepTitles[step]}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Step {step} of 2
            </Typography>
          </Stack>
        </Box>

        <Divider />

        {/* Body */}
        {step === 1 && (
          <StepObjectives
            qualificationChecked={qualificationChecked}
            setQualificationChecked={setQualificationChecked}
            nextStepsChecked={nextStepsChecked}
            setNextStepsChecked={setNextStepsChecked}
            runsByPipeline={runsByPipeline}
            onContinue={() => setStep(2)}
            onCancel={onCancel}
          />
        )}

        {step === 2 && (
          <StepCuration
            activityId={activityId}
            curatedText={curatedText}
            setCuratedText={setCuratedText}
            includeNotes={includeNotes}
            setIncludeNotes={setIncludeNotes}
            hasNotes={hasNotes}
            lastRun={lastRun}
            buildFinalContent={buildFinalContent}
            onBack={() => setStep(1)}
            onConfirm={handleConfirm}
          />
        )}
      </MainCard>
    </Modal>
  );
}

// ==============================|| PROP TYPES ||============================== //

RunAIWizard.propTypes = {
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
  runsByPipeline: PropTypes.shape({
    TRANSCRIPT_SIGNALS: PropTypes.object,
    NEXT_STEPS: PropTypes.object,
  }),
  onCancel: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
};
