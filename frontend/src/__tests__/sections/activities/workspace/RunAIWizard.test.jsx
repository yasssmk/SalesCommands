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
// The review-step notice (InfoNotice, T5b) reads theme.iconSizes.
import AphoriqTheme from '../../../_utils/aphoriqTheme';

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
  return render(<RunAIWizard {...defaultProps} {...overrides} />, { wrapper: AphoriqTheme });
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

    // Lot 3 / 11b (TD-258): the qualification option lists the types the
    // pipeline REALLY extracts (8, transcript_signals.py _STAGES), labels read
    // from utils/signalTypes.js — no hard-coded (and stale) list.
    it('lists the 8 qualification types really extracted, with their shared labels', () => {
      renderWizard();
      expect(
        screen.getByText(
          'Qualification signals (Pain, Objective, Impact, Tech Stack, Objection, Constraint, Competitor, People)',
        ),
      ).toBeInTheDocument();
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

    // « Source / Notes » 3.1 — no note on the activity: the transcript alone.
    it('calls onConfirm with curated transcript on Run analysis', async () => {
      const onConfirm = vi.fn();
      await goToStep2({ onConfirm, outcomeNotes: '' });

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

    // « Source / Notes » 3.1 — no note on the activity: the transcript alone.
    it('passes unchecked next-steps flag to onConfirm', async () => {
      const onConfirm = vi.fn();
      renderWizard({ onConfirm, outcomeNotes: '' });

      // Uncheck "Next-step suggestions" in Step 1
      const nextStepsCheckbox = screen.getByText(/Next-step suggestions/)
        .closest('label')
        .querySelector('input[type="checkbox"]');
      await act(async () => {
        fireEvent.click(nextStepsCheckbox);
      });

      // Continue to Step 2
      await act(async () => {
        fireEvent.click(screen.getByText('Continue'));
      });

      // Confirm
      await act(async () => {
        fireEvent.click(screen.getByText('Run analysis'));
      });

      expect(onConfirm).toHaveBeenCalledWith(
        LONG_TRANSCRIPT,
        expect.objectContaining({
          qualification: true,
          nextSteps: false,
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

// ==============================|| « SOURCE / NOTES » 3.1 ||============================== //
// The wizard follows the SERVER state of step 1 (runsByPipeline): a pipeline
// already analysed is NOT sent (the server never re-runs it — 1.6); the
// hash-based « Analysis already performed » alert is gone; « Include my
// notes » is CHECKED by default when the activity has notes.

import { createHash } from 'node:crypto';

const RUN = { last_run_at: '2026-11-01T10:00:00Z', created_signals_count: 1 };
const NOTES_SEPARATOR = '\n\n---\nSDR Notes:\n';

async function runFromStep1(overrides = {}) {
  const onConfirm = vi.fn();
  renderWizard({ onConfirm, outcomeNotes: '', ...overrides });
  await act(async () => { fireEvent.click(screen.getByText('Continue')); });
  await act(async () => { fireEvent.click(screen.getByText('Run analysis')); });
  return onConfirm;
}

describe('RunAIWizard — 3.1', () => {
  it('qualification already analysed: it is NOT sent, the next steps are', async () => {
    const onConfirm = await runFromStep1({
      runsByPipeline: { TRANSCRIPT_SIGNALS: RUN, NEXT_STEPS: null },
    });
    expect(onConfirm).toHaveBeenCalledWith(
      LONG_TRANSCRIPT,
      { qualification: false, nextSteps: true },
    );
  });

  it('next steps already analysed: they are NOT sent, the qualification is', async () => {
    const onConfirm = await runFromStep1({
      runsByPipeline: { TRANSCRIPT_SIGNALS: null, NEXT_STEPS: RUN },
    });
    expect(onConfirm).toHaveBeenCalledWith(
      LONG_TRANSCRIPT,
      { qualification: true, nextSteps: false },
    );
  });

  it('« Include my notes » is CHECKED by default when the activity has notes, and sends them', async () => {
    const onConfirm = vi.fn();
    renderWizard({ onConfirm, outcomeNotes: 'Call takeaways' });
    await act(async () => { fireEvent.click(screen.getByText('Continue')); });
    const notes = screen.getByText(/Include my notes/).closest('label').querySelector('input[type="checkbox"]');
    expect(notes).toBeChecked();
    await act(async () => { fireEvent.click(screen.getByText('Run analysis')); });
    expect(onConfirm.mock.calls[0][0]).toBe(LONG_TRANSCRIPT + NOTES_SEPARATOR + 'Call takeaways');
  });

  it('no notes on the activity: the box is unchecked and disabled', async () => {
    renderWizard({ outcomeNotes: '' });
    await act(async () => { fireEvent.click(screen.getByText('Continue')); });
    const notes = screen.getByText(/Include my notes/).closest('label').querySelector('input[type="checkbox"]');
    expect(notes).not.toBeChecked();
    expect(notes).toBeDisabled();
  });

  it('the hash-based « Analysis already performed » alert is gone', async () => {
    const inputHash = createHash('sha256').update(`act-111::${LONG_TRANSCRIPT}`).digest('hex');
    renderWizard({
      outcomeNotes: '',
      lastRun: { ...RUN, input_hash: inputHash },
      runsByPipeline: { TRANSCRIPT_SIGNALS: null, NEXT_STEPS: null },
    });
    await act(async () => { fireEvent.click(screen.getByText('Continue')); });
    await act(async () => { await new Promise((r) => setTimeout(r, 450)); });
    expect(screen.queryByText(/Analysis already performed/)).toBeNull();
  });
});
