// frontend/src/sections/activities/workspace/RunAIWizard.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect, useCallback } from 'react';
import { formatDistanceToNow } from 'date-fns';

// material-ui
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
import InfoNotice from 'components/display/InfoNotice';
import { getSignalTypeLabel, QUALIFICATION_SIGNAL_TYPES } from 'utils/signalTypes';

// assets
import SendOutlined from '@ant-design/icons/SendOutlined';
import ArrowLeftOutlined from '@ant-design/icons/ArrowLeftOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';

// The qualification option names the types the analysis REALLY extracts —
// ONE list with their shared labels (utils/signalTypes, lot 3 / 11b, TD-258).
const QUALIFICATION_TYPES_LABEL = QUALIFICATION_SIGNAL_TYPES.map(getSignalTypeLabel).join(', ');

// ==============================|| CONSTANTS ||============================== //

const MIN_TRANSCRIPT_LENGTH = 50;
const NOTES_SEPARATOR = '\n\n---\nSDR Notes:\n';

// ==============================|| HELPERS ||============================== //

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
                  Qualification signals ({QUALIFICATION_TYPES_LABEL})
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

// « Source / Notes » 3.1 — no hash-based « Analysis already performed » alert
// any more: the « already analysed » state is the SERVER's (step 1 reads
// runsByPipeline), and the server never re-runs an analysed pipeline (1.6).
function StepCuration({
  curatedText,
  setCuratedText,
  includeNotes,
  setIncludeNotes,
  hasNotes,
  buildFinalContent,
  onBack,
  onConfirm,
}) {
  const trimmedLength = curatedText.trim().length;
  const isTooShort = trimmedLength > 0 && trimmedLength < MIN_TRANSCRIPT_LENGTH;
  const isEmpty = trimmedLength === 0;
  const canSend = !isEmpty && !isTooShort;

  const handleConfirm = () => {
    if (canSend) {
      onConfirm(buildFinalContent(curatedText, includeNotes));
    }
  };

  return (
    <Box sx={{ p: 2.5 }}>
      <Stack spacing={2.5}>
        <InfoNotice>
          Edit below to remove anything you don&apos;t want to send to the AI
          (confidential names, third parties, NDA details, etc.).
          Your original transcript stays untouched.
        </InfoNotice>

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
  curatedText: PropTypes.string.isRequired,
  setCuratedText: PropTypes.func.isRequired,
  includeNotes: PropTypes.bool.isRequired,
  setIncludeNotes: PropTypes.func.isRequired,
  hasNotes: PropTypes.bool.isRequired,
  buildFinalContent: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
};

// ==============================|| RUN AI WIZARD ||============================== //

// The objectives checked when the wizard opens: both, unless the entry point
// says otherwise (the Next steps band: next steps only, 5.12 B).
export const DEFAULT_OBJECTIVES = { qualification: true, nextSteps: true };

export default function RunAIWizard({
  open,
  transcript,
  outcomeNotes,
  runsByPipeline,
  onCancel,
  onConfirm,
  defaultObjectives = DEFAULT_OBJECTIVES,
}) {
  const [step, setStep] = useState(1);
  const [qualificationChecked, setQualificationChecked] = useState(defaultObjectives.qualification);
  const [nextStepsChecked, setNextStepsChecked] = useState(defaultObjectives.nextSteps);
  const [curatedText, setCuratedText] = useState('');
  const hasNotes = Boolean(outcomeNotes?.trim());
  // 3.1 (PO, Q5) — the activity's notes are sent with the transcript by
  // default when there are some (the rep can still uncheck them).
  const [includeNotes, setIncludeNotes] = useState(hasNotes);

  useEffect(() => {
    if (open) {
      setStep(1);
      setQualificationChecked(defaultObjectives.qualification);
      setNextStepsChecked(defaultObjectives.nextSteps);
      setCuratedText(transcript || '');
      setIncludeNotes(hasNotes);
    }
  }, [open, transcript, hasNotes, defaultObjectives.qualification, defaultObjectives.nextSteps]);

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

  // 3.1 — a pipeline already analysed (the SERVER state of step 1,
  // runsByPipeline — its checkbox shows checked and disabled) is NOT sent.
  const handleConfirm = (finalContent) => {
    onConfirm(finalContent, {
      qualification: qualificationChecked && !runsByPipeline?.TRANSCRIPT_SIGNALS,
      nextSteps: nextStepsChecked && !runsByPipeline?.NEXT_STEPS,
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
            curatedText={curatedText}
            setCuratedText={setCuratedText}
            includeNotes={includeNotes}
            setIncludeNotes={setIncludeNotes}
            hasNotes={hasNotes}
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
  transcript: PropTypes.string,
  outcomeNotes: PropTypes.string,
  runsByPipeline: PropTypes.shape({
    TRANSCRIPT_SIGNALS: PropTypes.object,
    NEXT_STEPS: PropTypes.object,
  }),
  onCancel: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  /** The objectives checked when the wizard opens (default: both). */
  defaultObjectives: PropTypes.shape({
    qualification: PropTypes.bool,
    nextSteps: PropTypes.bool,
  }),
};
