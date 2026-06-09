// frontend/src/__tests__/sections/activities/workspace/ActivityNotesTab.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({
    className: 'mock-public-sans',
    style: { fontFamily: 'mock' },
  }),
}));

vi.mock('components/MainCard', () => ({
  default: ({ children, ...props }) => <div data-testid="main-card" {...props}>{children}</div>,
}));

vi.mock('components/EditableTextBlock', () => ({
  default: ({ label, field, initialValue, onSave, isLocked, placeholder, showCharCount }) => (
    <div data-testid={`editable-text-block-${field}`}>
      <span data-testid={`etb-label-${field}`}>{label}</span>
      <textarea
        data-testid={`etb-input-${field}`}
        defaultValue={initialValue || ''}
        disabled={isLocked}
        placeholder={placeholder}
        readOnly
      />
      {showCharCount && (
        <span data-testid={`etb-charcount-${field}`}>
          {(initialValue || '').length} characters
        </span>
      )}
    </div>
  ),
}));

vi.mock('utils/displayError', () => ({
  displayErrorSnackbar: vi.fn(),
  displaySuccessSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivityNotesTab from 'sections/activities/workspace/ActivityNotesTab';
import { PIPELINE_STATE } from 'hooks/usePipelineRunner';

// ==============================|| TEST DATA ||============================== //

const LONG_TRANSCRIPT = 'B'.repeat(200);

const mockActivity = {
  id: 'act-111',
  transcript: LONG_TRANSCRIPT,
  outcome_notes: 'Some important notes',
  status: 'PLANNED',
};

const mockOnSave = vi.fn();
const mockRun = vi.fn();
const mockReset = vi.fn();

function makePipelineRunner(overrides = {}) {
  return {
    run: mockRun,
    state: PIPELINE_STATE.IDLE,
    result: null,
    error: null,
    reset: mockReset,
    ...overrides,
  };
}

const defaultProps = {
  activity: mockActivity,
  onSave: mockOnSave,
  isLocked: false,
  pipelineRunner: makePipelineRunner(),
  lastRun: null,
  runsByPipeline: { TRANSCRIPT_SIGNALS: null, NEXT_STEPS: null },
};

// ==============================|| HELPERS ||============================== //

function renderTab(overrides = {}) {
  return render(<ActivityNotesTab {...defaultProps} {...overrides} />);
}

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
  mockOnSave.mockResolvedValue(true);
});

afterEach(() => {
  cleanup();
});

describe('ActivityNotesTab', () => {
  it('renders Notes and Transcript EditableTextBlocks', () => {
    renderTab();

    expect(screen.getByTestId('editable-text-block-outcome_notes')).toBeInTheDocument();
    expect(screen.getByTestId('editable-text-block-transcript')).toBeInTheDocument();
    expect(screen.getByTestId('etb-label-outcome_notes')).toHaveTextContent('Notes');
    expect(screen.getByTestId('etb-label-transcript')).toHaveTextContent('Transcript');
  });

  it('pre-fills transcript and notes from activity', () => {
    renderTab();

    expect(screen.getByTestId('etb-input-transcript')).toHaveValue(LONG_TRANSCRIPT);
    expect(screen.getByTestId('etb-input-outcome_notes')).toHaveValue('Some important notes');
  });

  it('shows character count on transcript block', () => {
    renderTab();

    expect(screen.getByTestId('etb-charcount-transcript')).toBeInTheDocument();
  });

  it('enables Run AI Analysis button with sufficient transcript', () => {
    renderTab();

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).not.toBeDisabled();
  });

  it('disables Run AI Analysis when transcript is empty', () => {
    renderTab({ activity: { ...mockActivity, transcript: '' } });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  it('disables Run AI Analysis when transcript < 50 chars', () => {
    renderTab({ activity: { ...mockActivity, transcript: 'Short' } });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  it('disables text blocks when isLocked', () => {
    renderTab({ isLocked: true });

    expect(screen.getByTestId('etb-input-transcript')).toBeDisabled();
    expect(screen.getByTestId('etb-input-outcome_notes')).toBeDisabled();
  });

  it('disables Run AI Analysis when isLocked', () => {
    renderTab({ isLocked: true });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  it('opens wizard when Run AI Analysis is clicked', async () => {
    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    expect(screen.getByText(/Select objectives/)).toBeInTheDocument();
  });

  it('shows "Analyzing…" button when pipeline is running', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({ state: PIPELINE_STATE.RUNNING }),
    });

    const btn = screen.getByText('Analyzing…').closest('button');
    expect(btn).toBeDisabled();
  });

  it('shows Run AI Analysis button after pipeline success', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.SUCCESS,
        result: {
          qualification_run: { created_signals_count: 5 },
          next_steps_run: { created_signals_count: 3 },
        },
      }),
    });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).not.toBeDisabled();
  });

  it('shows Run AI Analysis button after pipeline partial', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.PARTIAL,
        result: {
          qualification_run: { created_signals_count: 3 },
          next_steps_run: { created_signals_count: 0 },
        },
      }),
    });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).not.toBeDisabled();
  });

  it('shows error alert and Run AI Analysis button after pipeline error', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.ERROR,
        error: 'LLM provider error',
      }),
    });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).not.toBeDisabled();
    expect(screen.getByText('LLM provider error')).toBeInTheDocument();
  });

  it('shows success result alert after pipeline success', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.SUCCESS,
        result: {
          qualification_run: { created_signals_count: 4 },
          next_steps_run: { created_signals_count: 2 },
        },
      }),
    });

    expect(screen.getByText(/4 qualification signal\(s\) \+ 2 next-step suggestion\(s\) extracted/)).toBeInTheDocument();
  });

  it('shows last analyzed caption when lastRun exists and pipeline is idle', () => {
    renderTab({
      lastRun: {
        last_run_at: '2026-06-03T14:32:00Z',
        last_run_by: { id: 'u1', full_name: 'Yacine' },
        input_hash: 'a'.repeat(64),
        status: 'SUCCESS',
        created_signals_count: 5,
      },
    });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).not.toBeDisabled();
    expect(screen.getByText(/Last analyzed on/)).toBeInTheDocument();
  });

  it('renders empty blocks when activity has no transcript or notes', () => {
    renderTab({ activity: { ...mockActivity, transcript: null, outcome_notes: null } });

    expect(screen.getByTestId('etb-input-transcript')).toHaveValue('');
    expect(screen.getByTestId('etb-input-outcome_notes')).toHaveValue('');
  });

  // F8-3: "Try again" button on error
  it('shows "Try again" button when pipeline has error', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.ERROR,
        error: 'Network error',
      }),
    });

    expect(screen.getByText('Try again')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('clicking "Try again" opens the wizard', async () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.ERROR,
        error: 'Network error',
      }),
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Try again'));
    });

    expect(screen.getByText(/Select objectives/)).toBeInTheDocument();
  });

  // F8-3: Dismissible error Alert
  it('error alert is dismissible via close button', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.ERROR,
        error: 'Some error',
      }),
    });

    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);

    expect(mockReset).toHaveBeenCalled();
  });

  // F8-3: Polling progress caption
  it('shows polling progress when running with pollProgress', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.RUNNING,
        pollProgress: { attempt: 3, max: 12 },
      }),
    });

    expect(screen.getByText('Analyzing…')).toBeInTheDocument();
    expect(screen.getByText('Polling for result (3/12)…')).toBeInTheDocument();
  });

  it('does not show polling progress when running without pollProgress', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.RUNNING,
      }),
    });

    expect(screen.getByText('Analyzing…')).toBeInTheDocument();
    expect(screen.queryByText(/Polling for result/)).not.toBeInTheDocument();
  });

  // F8-3-FIX: Failed/stuck run banner
  it('shows warning banner when latestRun is failed and no lastRun', () => {
    renderTab({
      lastRun: null,
      latestRun: {
        last_run_at: '2026-06-07T10:00:00Z',
        last_run_by: null,
        input_hash: 'a'.repeat(64),
        status: 'LLM_ERROR',
        created_signals_count: 0,
        error_message: 'provider_error: connection refused',
      },
    });

    expect(screen.getByText(/Last extraction failed/)).toBeInTheDocument();
    expect(screen.getByText(/provider_error: connection refused/)).toBeInTheDocument();
  });

  it('shows warning banner when latestRun is stuck RUNNING', () => {
    renderTab({
      lastRun: null,
      latestRun: {
        last_run_at: '2026-06-07T10:00:00Z',
        last_run_by: null,
        input_hash: 'a'.repeat(64),
        status: 'RUNNING',
        created_signals_count: 0,
        error_message: '',
      },
    });

    expect(screen.getByText(/Last extraction stuck/)).toBeInTheDocument();
  });

  it('does NOT show banner when lastRun exists (successful run overshadows)', () => {
    renderTab({
      lastRun: {
        last_run_at: '2026-06-08T10:00:00Z',
        last_run_by: null,
        input_hash: 'a'.repeat(64),
        status: 'SUCCESS',
        created_signals_count: 5,
        error_message: '',
      },
      latestRun: {
        last_run_at: '2026-06-07T10:00:00Z',
        last_run_by: null,
        input_hash: 'a'.repeat(64),
        status: 'LLM_ERROR',
        created_signals_count: 0,
        error_message: 'old failure',
      },
    });

    expect(screen.queryByText(/Last extraction failed/)).not.toBeInTheDocument();
  });

  it('banner is dismissible via close button', () => {
    renderTab({
      lastRun: null,
      latestRun: {
        last_run_at: '2026-06-07T10:00:00Z',
        last_run_by: null,
        input_hash: 'a'.repeat(64),
        status: 'LLM_ERROR',
        created_signals_count: 0,
        error_message: '',
      },
    });

    expect(screen.getByText(/Last extraction failed/)).toBeInTheDocument();

    const dismissBtn = screen.getByRole('button', { name: /dismiss/i });
    fireEvent.click(dismissBtn);

    expect(screen.queryByText(/Last extraction failed/)).not.toBeInTheDocument();
  });
});
