// frontend/src/__tests__/sections/dcOverviewNotes.test.jsx
//
// Item 6: the "Coaching Notes" title lives in ManagerNotesThread (which owns
// the 403 decision), so it never orphans above an empty body, and OverviewTab
// no longer duplicates the 403 guard.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

// Configurable notes state per test.
let notesState;
vi.mock('api/accounts/decisionCycles', () => ({
  useGetManagerNotes: () => notesState,
  createManagerNote: vi.fn(),
  deleteManagerNote: vi.fn(),
}));

vi.mock('hooks/useUserPermissions', () => ({
  default: () => ({ isAdmin: true, isManager: true, currentUserId: 'u1' }),
}));

vi.mock('utils/displayError', () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

import ManagerNotesThread from 'sections/accounts/dc-workspace/ManagerNotesThread';
import OverviewTab from 'sections/accounts/dc-workspace/OverviewTab';

const okState = (overrides = {}) => ({
  notes: [],
  notesLoading: false,
  notesError: null,
  notesErrorStatus: null,
  mutateNotes: vi.fn(),
  ...overrides,
});

beforeEach(() => {
  notesState = okState();
});
afterEach(() => cleanup());

describe('ManagerNotesThread', () => {
  it('renders the Coaching Notes title with the body', () => {
    notesState = okState();
    render(<ManagerNotesThread cycleId="c1" />);
    expect(screen.getByText('Coaching Notes')).toBeInTheDocument();
    expect(screen.getByText('No coaching notes yet.')).toBeInTheDocument();
  });

  it('renders nothing on 403 — no title, no orphan header', () => {
    notesState = okState({ notesErrorStatus: 403 });
    const { container } = render(<ManagerNotesThread cycleId="c1" />);
    expect(screen.queryByText('Coaching Notes')).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });
});

describe('OverviewTab', () => {
  it('surfaces the notes (title owned by the thread, not the tab)', () => {
    notesState = okState();
    render(<OverviewTab cycleId="c1" />);
    expect(screen.getByText('Coaching Notes')).toBeInTheDocument();
  });

  it('has an empty body on 403 — no duplicate guard, no orphan title', () => {
    notesState = okState({ notesErrorStatus: 403 });
    render(<OverviewTab cycleId="c1" />);
    expect(screen.queryByText('Coaching Notes')).not.toBeInTheDocument();
  });
});
