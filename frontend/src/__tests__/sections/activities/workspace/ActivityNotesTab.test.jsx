// frontend/src/__tests__/sections/activities/workspace/ActivityNotesTab.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor, act } from '@testing-library/react';

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

const mockRunExtraction = vi.fn();
vi.mock('api/aiPipelines/activityExtraction', () => ({
  runActivityExtraction: (...args) => mockRunExtraction(...args),
  EXTRACTION_STATUS: {
    SUCCESS: 'SUCCESS',
    PARTIAL: 'PARTIAL',
    FAILED: 'FAILED',
  },
  EXTRACTION_OUTCOME_CODES: {
    ALREADY_EXTRACTED: 'ALREADY_EXTRACTED',
    IDEMPOTENCY_CONFLICT: 'IDEMPOTENCY_CONFLICT',
    TIMEOUT_PENDING: 'TIMEOUT_PENDING',
    POLL_FAILED: 'POLL_FAILED',
  },
}));

const mockLastRun = { last_run_at: null, last_run_by: null, input_hash: null };
const mockMutateLastRun = vi.fn();
vi.mock('api/aiPipelines/lastRun', () => ({
  useGetLastExtractionRun: () => ({
    lastRun: mockLastRun,
    lastRunLoading: false,
    lastRunError: null,
    mutateLastRun: mockMutateLastRun,
  }),
}));

vi.mock('utils/displayError', () => ({
  displayErrorSnackbar: vi.fn(),
  displaySuccessSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivityNotesTab from 'sections/activities/workspace/ActivityNotesTab';

// ==============================|| TEST DATA ||============================== //

const LONG_TRANSCRIPT = 'B'.repeat(200);

const mockActivity = {
  id: 'act-111',
  transcript: LONG_TRANSCRIPT,
  outcome_notes: 'Some important notes',
  status: 'PLANNED',
};

const mockOnSave = vi.fn();

const defaultProps = {
  activity: mockActivity,
  onSave: mockOnSave,
  isLocked: false,
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
  // ------------------------------------------------------------------
  // 1. Renders Notes and Transcript EditableTextBlocks
  // ------------------------------------------------------------------
  it('renders Notes and Transcript EditableTextBlocks', () => {
    renderTab();

    expect(screen.getByTestId('editable-text-block-outcome_notes')).toBeInTheDocument();
    expect(screen.getByTestId('editable-text-block-transcript')).toBeInTheDocument();
    expect(screen.getByTestId('etb-label-outcome_notes')).toHaveTextContent('Notes');
    expect(screen.getByTestId('etb-label-transcript')).toHaveTextContent('Transcript');
  });

  // ------------------------------------------------------------------
  // 2. Pre-fills transcript and notes from activity
  // ------------------------------------------------------------------
  it('pre-fills transcript and notes from activity', () => {
    renderTab();

    expect(screen.getByTestId('etb-input-transcript')).toHaveValue(LONG_TRANSCRIPT);
    expect(screen.getByTestId('etb-input-outcome_notes')).toHaveValue('Some important notes');
  });

  // ------------------------------------------------------------------
  // 3. Shows character count on transcript
  // ------------------------------------------------------------------
  it('shows character count on transcript block', () => {
    renderTab();

    expect(screen.getByTestId('etb-charcount-transcript')).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 4. Run AI button enabled with long transcript
  // ------------------------------------------------------------------
  it('enables Run AI Analysis button with sufficient transcript', () => {
    renderTab();

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).not.toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 5. Run AI button disabled when transcript empty
  // ------------------------------------------------------------------
  it('disables Run AI Analysis when transcript is empty', () => {
    renderTab({ activity: { ...mockActivity, transcript: '' } });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 6. Run AI button disabled when transcript too short
  // ------------------------------------------------------------------
  it('disables Run AI Analysis when transcript < 50 chars', () => {
    renderTab({ activity: { ...mockActivity, transcript: 'Short' } });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 7. Locked state — textarea disabled
  // ------------------------------------------------------------------
  it('disables text blocks when isLocked', () => {
    renderTab({ isLocked: true });

    expect(screen.getByTestId('etb-input-transcript')).toBeDisabled();
    expect(screen.getByTestId('etb-input-outcome_notes')).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 8. Locked state — Run AI button disabled
  // ------------------------------------------------------------------
  it('disables Run AI Analysis when isLocked', () => {
    renderTab({ isLocked: true });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 9. Opens preview modal on Run AI click
  // ------------------------------------------------------------------
  it('opens preview modal when Run AI Analysis is clicked', async () => {
    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    expect(screen.getByText('Review before sending to AI')).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 10. Successful extraction — shows success alert
  // ------------------------------------------------------------------
  it('shows success alert after successful extraction', async () => {
    mockRunExtraction.mockResolvedValue({
      success: true,
      data: {
        status: 'SUCCESS',
        qualification_run: { created_signals_count: 5 },
        next_steps_run: { created_signals_count: 3 },
      },
    });

    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(screen.getByText(/5 qualification signal\(s\) \+ 3 next-step suggestion\(s\) extracted/)).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 11. Extraction error — shows error alert
  // ------------------------------------------------------------------
  it('shows error alert after failed extraction', async () => {
    mockRunExtraction.mockResolvedValue({
      success: false,
      error: 'LLM provider error',
    });

    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(screen.getByText('LLM provider error')).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 12. ALREADY_EXTRACTED — shows info alert
  // ------------------------------------------------------------------
  it('shows info alert for ALREADY_EXTRACTED', async () => {
    mockRunExtraction.mockResolvedValue({
      success: false,
      code: 'ALREADY_EXTRACTED',
      data: {
        qualification_run: { created_signals_count: 2 },
        next_steps_run: { created_signals_count: 1 },
      },
    });

    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(screen.getByText(/already processed/)).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 13. PARTIAL extraction — shows warning alert
  // ------------------------------------------------------------------
  it('shows warning alert for partial extraction', async () => {
    mockRunExtraction.mockResolvedValue({
      success: true,
      data: {
        status: 'PARTIAL',
        qualification_run: { created_signals_count: 3 },
        next_steps_run: { created_signals_count: 0 },
      },
    });

    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(screen.getByText(/Partial extraction completed/)).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 14. Button state after success — shows "Last run"
  // ------------------------------------------------------------------
  it('shows "Last run" button label after successful extraction', async () => {
    mockRunExtraction.mockResolvedValue({
      success: true,
      data: {
        status: 'SUCCESS',
        qualification_run: { created_signals_count: 4 },
        next_steps_run: { created_signals_count: 2 },
      },
    });

    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(screen.getByText(/Last run · qualif \(4\) \+ next-step \(2\)/)).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 15. Button state after error — shows "Run failed · Retry"
  // ------------------------------------------------------------------
  it('shows retry button after extraction error', async () => {
    mockRunExtraction.mockResolvedValue({
      success: false,
      error: 'timeout',
    });

    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(screen.getByText(/Run failed · Retry/)).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 16. Mutates lastRun after successful extraction
  // ------------------------------------------------------------------
  it('mutates lastRun after successful extraction', async () => {
    mockRunExtraction.mockResolvedValue({
      success: true,
      data: {
        status: 'SUCCESS',
        qualification_run: { created_signals_count: 1 },
        next_steps_run: { created_signals_count: 0 },
      },
    });

    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(mockMutateLastRun).toHaveBeenCalled();
    });
  });

  // ------------------------------------------------------------------
  // 17. Empty activity — renders empty blocks
  // ------------------------------------------------------------------
  it('renders empty blocks when activity has no transcript or notes', () => {
    renderTab({ activity: { ...mockActivity, transcript: null, outcome_notes: null } });

    expect(screen.getByTestId('etb-input-transcript')).toHaveValue('');
    expect(screen.getByTestId('etb-input-outcome_notes')).toHaveValue('');
  });

  // ------------------------------------------------------------------
  // 18. Passes outcomeNotes to preview modal
  // ------------------------------------------------------------------
  it('passes outcomeNotes and lastRun to the preview modal', async () => {
    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    expect(screen.getByText('Review before sending to AI')).toBeInTheDocument();
    expect(screen.getByText(/Include my notes/)).toBeInTheDocument();
  });
});
