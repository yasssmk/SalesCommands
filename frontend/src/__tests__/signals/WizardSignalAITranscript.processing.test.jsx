// frontend/src/__tests__/signals/WizardSignalAITranscript.processing.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({
    className: 'mock-public-sans',
    style: { fontFamily: 'mock' },
  }),
}));

vi.mock('api/signals/signals', () => ({
  validateSignal: vi.fn(),
  deleteSignal: vi.fn(),
}));

const mockExtract = vi.fn();
vi.mock('api/aiPipelines/transcriptSignals', () => ({
  extractTranscriptSignals: (...args) => mockExtract(...args),
  EXTRACTION_OUTCOME_CODES: {
    ALREADY_EXTRACTED: 'ALREADY_EXTRACTED',
    IDEMPOTENCY_CONFLICT: 'IDEMPOTENCY_CONFLICT',
    IDEMPOTENCY_REPLAY_FAILED: 'IDEMPOTENCY_REPLAY_FAILED',
    IDEMPOTENCY_UNKNOWN_STATE: 'IDEMPOTENCY_UNKNOWN_STATE',
    TIMEOUT_PENDING: 'TIMEOUT_PENDING',
    POLL_FAILED: 'POLL_FAILED',
  },
}));

vi.mock('utils/displayError', () => ({
  displaySuccessSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import WizardSignalAITranscript from 'sections/activities/signals/wizard/WizardSignalAITranscript';

// ==============================|| TEST DATA ||============================== //

const LONG_TRANSCRIPT = 'A'.repeat(200);

const defaultProps = {
  open: true,
  activityId: 'act-111',
  accountId: 'acc-111',
  initialTranscript: LONG_TRANSCRIPT,
  initialNotes: '',
  onClose: vi.fn(),
  onSuccess: vi.fn(),
  onSignalEdit: vi.fn(),
};

// ==============================|| HELPERS ||============================== //

function renderWizard(overrides = {}) {
  return render(<WizardSignalAITranscript {...defaultProps} {...overrides} />);
}

async function goToProcessingWithResult(extractionResult) {
  mockExtract.mockResolvedValue(extractionResult);
  renderWizard();

  // Click "Send to AI" to trigger extraction
  await act(async () => {
    fireEvent.click(screen.getByText('Send to AI'));
  });

  // Wait for extraction to complete and result to render
  await act(async () => {
    await vi.waitFor(() => {
      expect(mockExtract).toHaveBeenCalled();
    });
  });
}

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe('WizardSignalAITranscript — ProcessingStep retry buttons', () => {
  it('shows Retry button on TIMEOUT_PENDING', async () => {
    await goToProcessingWithResult({
      success: false,
      code: 'TIMEOUT_PENDING',
      isPending: true,
      error: 'Extraction is taking longer than expected.',
    });

    expect(screen.getByText('Operation still running')).toBeInTheDocument();
    expect(screen.getByText('Retry')).toBeInTheDocument();
    expect(screen.getByText('Back to transcript')).toBeInTheDocument();
  });

  it('shows Retry button on IDEMPOTENCY_REPLAY_FAILED', async () => {
    await goToProcessingWithResult({
      success: false,
      code: 'IDEMPOTENCY_REPLAY_FAILED',
      error: 'Previous attempt failed.',
    });

    expect(screen.getByText('Previous attempt failed')).toBeInTheDocument();
    expect(screen.getByText('Retry')).toBeInTheDocument();
    expect(screen.getByText('Back to transcript')).toBeInTheDocument();
  });

  it('shows Retry button on generic error', async () => {
    await goToProcessingWithResult({
      success: false,
      error: 'Some unexpected error occurred.',
    });

    expect(screen.getByText('Extraction failed')).toBeInTheDocument();
    expect(screen.getByText('Retry')).toBeInTheDocument();
    expect(screen.getByText('Back to transcript')).toBeInTheDocument();
  });

  it('does NOT show Retry button on ALREADY_EXTRACTED', async () => {
    await goToProcessingWithResult({
      success: false,
      code: 'ALREADY_EXTRACTED',
      data: { created_at: '2026-01-01', created_signals_count: 5 },
    });

    expect(screen.getByText('This transcript was already processed')).toBeInTheDocument();
    expect(screen.queryByText('Retry')).not.toBeInTheDocument();
    expect(screen.getByText('Back to transcript')).toBeInTheDocument();
  });
});
