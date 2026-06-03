// frontend/src/__tests__/sections/activities/workspace/ActivityNotesExtractionPreviewModal.test.jsx

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

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivityNotesExtractionPreviewModal from 'sections/activities/workspace/ActivityNotesExtractionPreviewModal';

// ==============================|| TEST DATA ||============================== //

const LONG_TRANSCRIPT = 'A'.repeat(200);
const SHORT_TRANSCRIPT = 'A'.repeat(30);

const defaultProps = {
  open: true,
  activityId: 'act-123',
  transcript: LONG_TRANSCRIPT,
  outcomeNotes: 'My meeting notes here',
  lastRun: null,
  onCancel: vi.fn(),
  onConfirm: vi.fn(),
  loading: false,
};

// ==============================|| HELPERS ||============================== //

function renderModal(overrides = {}) {
  return render(
    <ActivityNotesExtractionPreviewModal {...defaultProps} {...overrides} />,
  );
}

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

describe('ActivityNotesExtractionPreviewModal', () => {
  // ------------------------------------------------------------------
  // 1. Render OK
  // ------------------------------------------------------------------
  it('renders title, info banner, textarea, checkbox, and buttons when open', () => {
    renderModal();

    expect(screen.getByText('Review before sending to AI')).toBeInTheDocument();
    expect(screen.getByText(/Edit below to remove anything/)).toBeInTheDocument();
    expect(screen.getByTestId('curated-transcript-input')).toBeInTheDocument();
    expect(screen.getByText(/Include my notes/)).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
    expect(screen.getByText('Send for analysis')).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 2. Pre-fills textarea with transcript
  // ------------------------------------------------------------------
  it('pre-fills textarea with the transcript prop', () => {
    renderModal();

    const input = screen.getByTestId('curated-transcript-input');
    expect(input.value).toBe(LONG_TRANSCRIPT);
  });

  // ------------------------------------------------------------------
  // 3. Allows free editing
  // ------------------------------------------------------------------
  it('allows editing the curated transcript', () => {
    renderModal();

    const input = screen.getByTestId('curated-transcript-input');
    fireEvent.change(input, { target: { value: 'Edited content that is long enough to be valid for the minimum check yes' } });

    expect(input.value).toBe('Edited content that is long enough to be valid for the minimum check yes');
  });

  // ------------------------------------------------------------------
  // 4. Cancel calls onCancel, does not call onConfirm
  // ------------------------------------------------------------------
  it('calls onCancel and NOT onConfirm when Cancel is clicked', () => {
    renderModal();

    fireEvent.click(screen.getByText('Cancel'));

    expect(defaultProps.onCancel).toHaveBeenCalledTimes(1);
    expect(defaultProps.onConfirm).not.toHaveBeenCalled();
  });

  // ------------------------------------------------------------------
  // 5. Confirm dispatches the EDITED version, not the original
  // ------------------------------------------------------------------
  it('calls onConfirm with the edited (trimmed) text, not the original', () => {
    renderModal();

    const input = screen.getByTestId('curated-transcript-input');
    const editedText = 'This is the redacted version of the transcript that should be long enough';
    fireEvent.change(input, { target: { value: `  ${editedText}  ` } });

    fireEvent.click(screen.getByText('Send for analysis'));

    expect(defaultProps.onConfirm).toHaveBeenCalledWith(editedText);
  });

  // ------------------------------------------------------------------
  // 6. Disables Send when content is too short
  // ------------------------------------------------------------------
  it('disables Send button when transcript is below 50 chars', () => {
    renderModal();

    const input = screen.getByTestId('curated-transcript-input');
    fireEvent.change(input, { target: { value: SHORT_TRANSCRIPT } });

    const sendBtn = screen.getByText('Send for analysis').closest('button');
    expect(sendBtn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 7. Shows error helper text when too short
  // ------------------------------------------------------------------
  it('shows validation error when transcript is below 50 chars', () => {
    renderModal();

    const input = screen.getByTestId('curated-transcript-input');
    fireEvent.change(input, { target: { value: SHORT_TRANSCRIPT } });

    expect(screen.getByText(/Transcript too short/)).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 8. Disables Send when content is empty
  // ------------------------------------------------------------------
  it('disables Send button when transcript is empty', () => {
    renderModal();

    const input = screen.getByTestId('curated-transcript-input');
    fireEvent.change(input, { target: { value: '' } });

    const sendBtn = screen.getByText('Send for analysis').closest('button');
    expect(sendBtn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 9. Shows character count
  // ------------------------------------------------------------------
  it('displays character count based on trimmed content', () => {
    renderModal();

    expect(screen.getByText(`${LONG_TRANSCRIPT.length} characters`)).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 10. Loading state disables buttons and shows spinner
  // ------------------------------------------------------------------
  it('disables buttons and shows Sending when loading', () => {
    renderModal({ loading: true });

    const sendBtn = screen.getByText('Sending...').closest('button');
    expect(sendBtn).toBeDisabled();

    const cancelBtn = screen.getByText('Cancel').closest('button');
    expect(cancelBtn).toBeDisabled();
  });

  // ------------------------------------------------------------------
  // 11. Resets to original transcript on each open
  // ------------------------------------------------------------------
  it('resets curated text to transcript prop when reopened', () => {
    const { rerender } = renderModal();

    const input = screen.getByTestId('curated-transcript-input');
    fireEvent.change(input, { target: { value: 'edited' } });

    rerender(
      <ActivityNotesExtractionPreviewModal {...defaultProps} open={false} />,
    );
    rerender(
      <ActivityNotesExtractionPreviewModal
        {...defaultProps}
        open={true}
        transcript="New transcript content that is definitely long enough for the minimum"
      />,
    );

    const newInput = screen.getByTestId('curated-transcript-input');
    expect(newInput.value).toBe('New transcript content that is definitely long enough for the minimum');
  });

  // ------------------------------------------------------------------
  // 12. Does not render content when closed
  // ------------------------------------------------------------------
  it('does not render modal content when open is false', () => {
    renderModal({ open: false });

    expect(screen.queryByText('Review before sending to AI')).not.toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 13. Include notes checkbox — enabled when notes exist
  // ------------------------------------------------------------------
  it('enables "Include my notes" checkbox when outcomeNotes is provided', () => {
    renderModal();

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).not.toBeDisabled();
    expect(checkbox).not.toBeChecked();
    expect(screen.getByText(/available on this activity/)).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 14. Include notes checkbox — disabled when no notes
  // ------------------------------------------------------------------
  it('disables "Include my notes" checkbox when outcomeNotes is empty', () => {
    renderModal({ outcomeNotes: '' });

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeDisabled();
    expect(screen.getByText(/none on this activity/)).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 15. Confirm with notes included — concatenates content
  // ------------------------------------------------------------------
  it('concatenates notes when checkbox is checked and confirmed', () => {
    renderModal();

    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    fireEvent.click(screen.getByText('Send for analysis'));

    const expected = LONG_TRANSCRIPT + '\n\n---\nSDR Notes:\n' + 'My meeting notes here';
    expect(defaultProps.onConfirm).toHaveBeenCalledWith(expected);
  });

  // ------------------------------------------------------------------
  // 16. Confirm without notes — sends transcript only
  // ------------------------------------------------------------------
  it('sends only transcript when checkbox is unchecked', () => {
    renderModal();

    fireEvent.click(screen.getByText('Send for analysis'));

    expect(defaultProps.onConfirm).toHaveBeenCalledWith(LONG_TRANSCRIPT);
  });

  // ------------------------------------------------------------------
  // 17. Resets include-notes checkbox on reopen
  // ------------------------------------------------------------------
  it('resets include-notes checkbox to unchecked on reopen', () => {
    const { rerender } = renderModal();

    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();

    rerender(
      <ActivityNotesExtractionPreviewModal {...defaultProps} open={false} />,
    );
    rerender(
      <ActivityNotesExtractionPreviewModal {...defaultProps} open={true} />,
    );

    expect(screen.getByRole('checkbox')).not.toBeChecked();
  });
});
