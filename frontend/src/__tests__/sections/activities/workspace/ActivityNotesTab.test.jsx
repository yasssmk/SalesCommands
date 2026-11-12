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
    <div data-testid={`editable-text-block-${field}`} data-has-onsave={String(Boolean(onSave))}>
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
import AphoriqTheme from '../../../_utils/aphoriqTheme';

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
};

// ==============================|| HELPERS ||============================== //

function renderTab(overrides = {}) {
  return render(<AphoriqTheme><ActivityNotesTab {...defaultProps} {...overrides} /></AphoriqTheme>);
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

  // « Source / Notes » 1.5 (PO) — ONE note per activity, filled throughout its
  // lifecycle: the notes follow the transcript's lock, isActivitySignalsLocked
  // (CANCELLED only) — read from the activity, whatever the page lock says.
  it('locks the notes and the transcript on CANCELLED only', () => {
    renderTab({ isLocked: true, activity: { ...mockActivity, status: 'CANCELLED' } });

    expect(screen.getByTestId('etb-input-transcript')).toBeDisabled();
    expect(screen.getByTestId('etb-input-outcome_notes')).toBeDisabled();
  });

  // N6 — the note is written in the notes panel: READ-ONLY in the band on
  // every status; the transcript keeps its own rule (editable on COMPLETED).
  it('on a COMPLETED activity: the transcript stays editable, the note is read-only', () => {
    renderTab({ isLocked: true, activity: { ...mockActivity, status: 'COMPLETED' } });

    expect(screen.getByTestId('etb-input-outcome_notes')).toBeDisabled();
    expect(screen.getByTestId('etb-input-transcript')).not.toBeDisabled();
  });

  // N6b — onSave is optional: the read-only note gets none; the transcript keeps it.
  it('the read-only note is given no onSave; the transcript keeps its own', () => {
    renderTab();
    expect(screen.getByTestId('editable-text-block-outcome_notes')).toHaveAttribute('data-has-onsave', 'false');
    expect(screen.getByTestId('editable-text-block-transcript')).toHaveAttribute('data-has-onsave', 'true');
  });

  it('on a PLANNED activity too, the note is read-only (written in the notes panel)', () => {
    renderTab({ activity: { ...mockActivity, status: 'PLANNED' } });
    expect(screen.getByTestId('etb-input-outcome_notes')).toBeDisabled();
  });

  it('shows the error alert after pipeline error', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.ERROR,
        error: 'LLM provider error',
      }),
    });

    expect(screen.getByText('LLM provider error')).toBeInTheDocument();
  });

  // « Source / Notes » 1.6 — « already analysed » is a business rule: the
  // server's refusal is shown as INFORMATION (InfoNotice), never as a red
  // error, and offers no « Try again » (an analysis is never re-run).
  it('shows the « already analysed » refusal as information, not an error', () => {
    renderTab({
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.INFO,
        error: 'This activity has already been analysed.',
      }),
    });

    const notice = screen.getByTestId('analysis-already-done-notice');
    expect(notice).toHaveTextContent('This activity has already been analysed.');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByText('Try again')).toBeNull();
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

  // Lot 3 / 11 (TD-302): the wizard is the band header pill's (the page owns
  // its open state) — "Try again" asks for it, under the pill's predicate.
  it('clicking "Try again" opens the wizard (onOpenWizard)', async () => {
    const onOpenWizard = vi.fn();
    renderTab({
      onOpenWizard,
      pipelineRunner: makePipelineRunner({
        state: PIPELINE_STATE.ERROR,
        error: 'Network error',
      }),
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Try again'));
    });

    expect(onOpenWizard).toHaveBeenCalledTimes(1);
  });

  // « Source / Notes » 3.2 — the same predicate: everything available already
  // analysed (qualification + next steps on a DC activity) → no wizard.
  it('"Try again" does nothing when everything available is already analysed', async () => {
    const onOpenWizard = vi.fn();
    const run = { last_run_at: '2026-11-01T10:00:00Z' };
    renderTab({
      onOpenWizard,
      activity: { ...mockActivity, decision_cycle: 'dc-1' },
      runsByPipeline: { TRANSCRIPT_SIGNALS: run, NEXT_STEPS: run },
      pipelineRunner: makePipelineRunner({ state: PIPELINE_STATE.ERROR, error: 'Network error' }),
    });
    await act(async () => {
      fireEvent.click(screen.getByText('Try again'));
    });
    expect(onOpenWizard).not.toHaveBeenCalled();
  });

  it('"Try again" does nothing when the AI action is unavailable (CANCELLED)', async () => {
    const onOpenWizard = vi.fn();
    renderTab({
      onOpenWizard,
      activity: { ...mockActivity, status: 'CANCELLED' },
      pipelineRunner: makePipelineRunner({ state: PIPELINE_STATE.ERROR, error: 'Network error' }),
    });
    await act(async () => {
      fireEvent.click(screen.getByText('Try again'));
    });
    expect(onOpenWizard).not.toHaveBeenCalled();
  });

  it('no Run AI action in the tab any more (it is in the band header)', () => {
    renderTab();
    expect(screen.queryByText('Run AI Analysis')).toBeNull();
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
  // F8-3-FIX: Failed/stuck run banner
  it('shows warning banner with static message when latestRun is failed', () => {
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

    expect(screen.getByText(/Last extraction failed.*Click Try Again to retry/)).toBeInTheDocument();
    expect(screen.queryByText(/provider_error/)).not.toBeInTheDocument();
  });

  it('shows warning banner with pending message when latestRun is stuck RUNNING', () => {
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

    expect(screen.getByText(/Last extraction stuck.*Extraction is still pending/)).toBeInTheDocument();
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

    expect(screen.getByText(/Last extraction failed.*Click Try Again to retry/)).toBeInTheDocument();

    const dismissBtn = screen.getByRole('button', { name: /dismiss/i });
    fireEvent.click(dismissBtn);

    expect(screen.queryByText(/Last extraction failed/)).not.toBeInTheDocument();
  });
});
