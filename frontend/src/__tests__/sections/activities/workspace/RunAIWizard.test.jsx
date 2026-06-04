// frontend/src/__tests__/sections/activities/workspace/RunAIWizard.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act, within } from '@testing-library/react';

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

// ==============================|| IMPORTS (after mocks) ||============================== //

import RunAIWizard from 'sections/activities/workspace/RunAIWizard';

// ==============================|| TEST DATA ||============================== //

const LONG_TRANSCRIPT = 'B'.repeat(200);

const defaultProps = {
  open: true,
  activityId: 'act-111',
  transcript: LONG_TRANSCRIPT,
  outcomeNotes: 'Some notes',
  lastRun: null,
  runsByPipeline: { TRANSCRIPT_SIGNALS: null, NEXT_STEPS: null },
  onCancel: vi.fn(),
  onConfirm: vi.fn(),
};

// ==============================|| HELPERS ||============================== //

function renderWizard(overrides = {}) {
  return render(<RunAIWizard {...defaultProps} {...overrides} />);
}

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe('RunAIWizard', () => {
  describe('Step 1 — Objectives', () => {
    it('renders step 1 with checkboxes', () => {
      renderWizard();

      expect(screen.getByText(/Select objectives/)).toBeInTheDocument();
      expect(screen.getByText('Step 1 of 2')).toBeInTheDocument();
      expect(screen.getByText(/Qualification signals/)).toBeInTheDocument();
      expect(screen.getByText(/Next-step suggestions/)).toBeInTheDocument();
    });

    it('enables Continue when at least one option is checked', () => {
      renderWizard();

      const continueBtn = screen.getByText('Continue').closest('button');
      expect(continueBtn).not.toBeDisabled();
    });

    it('disables checkbox and shows "Already extracted" when pipeline already run', () => {
      renderWizard({
        runsByPipeline: {
          TRANSCRIPT_SIGNALS: {
            last_run_at: '2026-06-03T14:32:00Z',
            status: 'SUCCESS',
            created_signals_count: 5,
          },
          NEXT_STEPS: null,
        },
      });

      expect(screen.getByText(/Already extracted/)).toBeInTheDocument();
    });

    it('disables Continue when both pipelines already extracted', () => {
      renderWizard({
        runsByPipeline: {
          TRANSCRIPT_SIGNALS: {
            last_run_at: '2026-06-03T14:32:00Z',
            status: 'SUCCESS',
          },
          NEXT_STEPS: {
            last_run_at: '2026-06-03T14:33:00Z',
            status: 'SUCCESS',
          },
        },
      });

      const continueBtn = screen.getByText('Continue').closest('button');
      expect(continueBtn).toBeDisabled();
    });

    it('calls onCancel when Cancel is clicked', async () => {
      const onCancel = vi.fn();
      renderWizard({ onCancel });

      await act(async () => {
        fireEvent.click(screen.getByText('Cancel'));
      });

      expect(onCancel).toHaveBeenCalled();
    });
  });

  describe('Step navigation', () => {
    it('navigates from Step 1 to Step 2 on Continue', async () => {
      renderWizard();

      await act(async () => {
        fireEvent.click(screen.getByText('Continue'));
      });

      expect(screen.getByText(/Review before sending/)).toBeInTheDocument();
      expect(screen.getByText('Step 2 of 2')).toBeInTheDocument();
    });

    it('navigates back from Step 2 to Step 1', async () => {
      renderWizard();

      await act(async () => {
        fireEvent.click(screen.getByText('Continue'));
      });

      expect(screen.getByText('Step 2 of 2')).toBeInTheDocument();

      await act(async () => {
        fireEvent.click(screen.getByText('Back'));
      });

      expect(screen.getByText('Step 1 of 2')).toBeInTheDocument();
    });
  });

  describe('Step 2 — Curation', () => {
    async function goToStep2(overrides = {}) {
      const result = renderWizard(overrides);

      await act(async () => {
        fireEvent.click(screen.getByText('Continue'));
      });

      return result;
    }

    it('renders transcript textarea with content', async () => {
      await goToStep2();

      const textarea = screen.getByTestId('curated-transcript-input');
      expect(textarea).toHaveValue(LONG_TRANSCRIPT);
    });

    it('shows "Include my notes" checkbox', async () => {
      await goToStep2();

      expect(screen.getByText(/Include my notes/)).toBeInTheDocument();
    });

    it('calls onConfirm with curated transcript on Run analysis', async () => {
      const onConfirm = vi.fn();
      await goToStep2({ onConfirm });

      await act(async () => {
        fireEvent.click(screen.getByText('Run analysis'));
      });

      expect(onConfirm).toHaveBeenCalledWith(
        LONG_TRANSCRIPT,
        expect.objectContaining({
          qualification: true,
          nextSteps: true,
        }),
      );
    });

    it('disables Run analysis when transcript is empty', async () => {
      await goToStep2({ transcript: '' });

      const btn = screen.getByText('Run analysis').closest('button');
      expect(btn).toBeDisabled();
    });

    it('disables Run analysis when transcript is too short', async () => {
      await goToStep2({ transcript: 'Short' });

      const btn = screen.getByText('Run analysis').closest('button');
      expect(btn).toBeDisabled();
    });
  });

  describe('Closed state', () => {
    it('does not render when open is false', () => {
      renderWizard({ open: false });

      expect(screen.queryByText(/Select objectives/)).not.toBeInTheDocument();
    });
  });
});
