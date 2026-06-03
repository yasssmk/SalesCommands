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

const mockUpdateActivity = vi.fn();
vi.mock('api/accounts/activities', () => ({
  updateActivity: (...args) => mockUpdateActivity(...args),
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
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockOnSave.mockResolvedValue(true);
});

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

describe('ActivityNotesTab', () => {
  // ------------------------------------------------------------------
  // 1. Render OK
  // ------------------------------------------------------------------
  it('renders transcript textarea and Run AI Analysis button', () => {
    renderTab();

    expect(screen.getByTestId('transcript-input')).toBeInTheDocument();
    expect(screen.getByText('Transcript')).toBeInTheDocument();
    expect(screen.getByText('Run AI Analysis')).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 2. Pre-fills transcript from activity
  // ------------------------------------------------------------------
  it('pre-fills textarea with activity.transcript', () => {
    renderTab();

    const input = screen.getByTestId('transcript-input');
    expect(input.value).toBe(LONG_TRANSCRIPT);
  });

  // ------------------------------------------------------------------
  // 3. Autosave debounce — fires after 1.5s
  // ------------------------------------------------------------------
  it('calls onSave after debounce delay on text change', async () => {
    renderTab();

    const input = screen.getByTestId('transcript-input');
    const newText = 'C'.repeat(100);

    await act(async () => {
      fireEvent.change(input, { target: { value: newText } });
    });

    expect(mockOnSave).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(1500);
    });

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith('transcript', newText);
    });
  });

  // ------------------------------------------------------------------
  // 4. Autosave on blur (immediate)
  // ------------------------------------------------------------------
  it('calls onSave immediately on blur', async () => {
    renderTab();

    const input = screen.getByTestId('transcript-input');
    const newText = 'D'.repeat(100);

    await act(async () => {
      fireEvent.change(input, { target: { value: newText } });
      fireEvent.blur(input);
    });

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith('transcript', newText);
    });
  });

  // ------------------------------------------------------------------
  // 5. Shows saving indicator
  // ------------------------------------------------------------------
  it('shows "Saving…" indicator while persisting', async () => {
    let resolveOnSave;
    mockOnSave.mockReturnValue(new Promise((r) => { resolveOnSave = r; }));
    renderTab();

    const input = screen.getByTestId('transcript-input');

    await act(async () => {
      fireEvent.change(input, { target: { value: 'E'.repeat(100) } });
      fireEvent.blur(input);
    });

    await waitFor(() => {
      expect(screen.getByText(/Saving/)).toBeInTheDocument();
    });

    await act(async () => {
      resolveOnSave(true);
    });

    await waitFor(() => {
      expect(screen.getByText(/Saved/)).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 6. Shows save error indicator
  // ------------------------------------------------------------------
  it('shows "Error saving" when onSave returns false', async () => {
    mockOnSave.mockResolvedValue(false);
    renderTab();

    const input = screen.getByTestId('transcript-input');

    await act(async () => {
      fireEvent.change(input, { target: { value: 'F'.repeat(100) } });
      fireEvent.blur(input);
    });

    await waitFor(() => {
      expect(screen.getByText(/Error saving/)).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 7. Run AI button disabled when transcript empty
  // ------------------------------------------------------------------
  it('disables Run AI Analysis when transcript is empty', () => {
    renderTab({ activity: { ...mockActivity, transcript: '' } });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 8. Run AI button disabled when transcript too short
  // ------------------------------------------------------------------
  it('disables Run AI Analysis when transcript < 50 chars', () => {
    renderTab({ activity: { ...mockActivity, transcript: 'Short' } });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 9. Locked state — textarea disabled
  // ------------------------------------------------------------------
  it('disables textarea when isLocked', () => {
    renderTab({ isLocked: true });

    const input = screen.getByTestId('transcript-input');
    expect(input).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 10. Locked state — Run AI button disabled
  // ------------------------------------------------------------------
  it('disables Run AI Analysis when isLocked', () => {
    renderTab({ isLocked: true });

    const btn = screen.getByText('Run AI Analysis').closest('button');
    expect(btn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 11. Opens preview modal on Run AI click
  // ------------------------------------------------------------------
  it('opens preview modal when Run AI Analysis is clicked', async () => {
    renderTab();

    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    expect(screen.getByText('Review before sending to AI')).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 12. Successful extraction — shows success alert
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

    // Open modal
    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });

    // Send for analysis
    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(screen.getByText(/5 qualification signal\(s\) \+ 3 next-step suggestion\(s\) extracted/)).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // 13. Extraction error — shows error alert
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
  // 14. ALREADY_EXTRACTED — shows info alert
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
  // 15. PARTIAL extraction — shows warning alert
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
  // 16. Button state after success — shows "Last run"
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
  // 17. Button state after error — shows "Run failed · Retry"
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
  // 18. Transcript modified after run — shows warning
  // ------------------------------------------------------------------
  it('shows "Transcript modified" warning when text changes after extraction', async () => {
    mockRunExtraction.mockResolvedValue({
      success: true,
      data: {
        status: 'SUCCESS',
        qualification_run: { created_signals_count: 1 },
        next_steps_run: { created_signals_count: 0 },
      },
    });

    renderTab();

    // Run extraction
    await act(async () => {
      fireEvent.click(screen.getByText('Run AI Analysis'));
    });
    await act(async () => {
      fireEvent.click(screen.getByText('Send for analysis'));
    });

    await waitFor(() => {
      expect(screen.getByText(/extracted/)).toBeInTheDocument();
    });

    // Modify transcript
    const input = screen.getByTestId('transcript-input');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'G'.repeat(200) } });
    });

    expect(screen.getByText(/Transcript modified since last run/)).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 19. No autosave when locked
  // ------------------------------------------------------------------
  it('does not call onSave when locked', async () => {
    renderTab({ isLocked: true });

    // Textarea is disabled so we can't type, but let's verify onSave not called
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    expect(mockOnSave).not.toHaveBeenCalled();
  });

  // ------------------------------------------------------------------
  // 20. Empty activity transcript — renders empty textarea
  // ------------------------------------------------------------------
  it('renders empty textarea when activity has no transcript', () => {
    renderTab({ activity: { ...mockActivity, transcript: null } });

    const input = screen.getByTestId('transcript-input');
    expect(input.value).toBe('');
  });
});
