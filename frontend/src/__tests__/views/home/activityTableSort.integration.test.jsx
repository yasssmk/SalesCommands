// frontend/src/__tests__/views/home/activityTableSort.integration.test.jsx
//
// The test that would have caught A3. It mounts the REAL RepActivityTable /
// TeamActivityTable (hence the REAL ReusableTable + TanStack), clicks a column
// header, and asserts the `ordering` sent to the data hook actually changes.
//
// Why the mocked unit tests missed the bug: they mock ReusableTable and call
// onSortingChange DIRECTLY, so they only exercise toOrdering() — never
// TanStack's getCanSort(), which gates every real sort entry point on
// !!column.accessorFn. A display column (id + cell, no accessorFn) is silently
// non-sortable: getToggleSortingHandler() is a no-op, clicking the header does
// nothing, and no HeaderSort renders. This test drives the header click through
// the real table, so a column that regresses to display-only fails here.

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';

import Palette from 'themes/palette';
import Typography from 'themes/typography';
import CustomShadows from 'themes/shadows';

const paletteTheme = Palette('light', 'default');
const theme = createTheme({
  breakpoints: { values: { xs: 0, sm: 768, md: 1024, lg: 1266, xl: 1440 } },
  palette: paletteTheme.palette,
  customShadows: CustomShadows(paletteTheme),
  typography: Typography(`'Public Sans', sans-serif`),
});

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));
vi.mock('components/MainCard', () => ({
  default: ({ children }) => <div data-testid="main-card">{children}</div>,
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ entries: () => [], toString: () => '', keys: () => [] }),
}));
vi.mock('swr', () => ({ useSWRConfig: () => ({ mutate: vi.fn() }) }));
vi.mock('hooks/useLocalStorage', () => ({ default: (_k, init) => [init, vi.fn()] }));

// Capture the args passed to the data hooks so we can read `ordering` after a
// header click. Both wrappers pull from api/bi/todo.
let lastRepArgs = null;
let lastTeamArgs = null;
const ROWS = [
  {
    id: 'a1', title: 'Call Acme', activity_type_display: 'Call', effective_date: '2026-07-10',
    owner: { id: 'u1', full_name: 'Fabien Roux', last_name: 'Roux' },
    team: { id: 't1', name: 'EMEA' },
    account: { id: 'acc1', company_name: 'Acme' }, decision_cycle: null, campaign: null,
  },
  {
    id: 'a2', title: 'Email Globex', activity_type_display: 'Email', effective_date: '2026-07-11',
    owner: { id: 'u2', full_name: 'Uma Stone', last_name: 'Stone' },
    team: { id: 't2', name: 'AMER' },
    account: { id: 'acc2', company_name: 'Globex' }, decision_cycle: null, campaign: null,
  },
];
const hookReturn = () => ({
  activities: ROWS, activitiesCount: 2, activitiesLoading: false, activitiesError: null, swrKey: null,
});
vi.mock('api/bi/todo', () => ({
  useGetTodoActivities: (args) => { lastRepArgs = args; return hookReturn(); },
  useGetTeamTodoActivities: (args) => { lastTeamArgs = args; return hookReturn(); },
}));

import RepActivityTable from 'sections/home/RepActivityTable';
import TeamActivityTable from 'sections/home/TeamActivityTable';

function renderRep() {
  return render(
    <ThemeProvider theme={theme}>
      <RepActivityTable window="today" scope="mine" />
    </ThemeProvider>,
  );
}
function renderTeam() {
  return render(
    <ThemeProvider theme={theme}>
      <TeamActivityTable team="" owner="" />
    </ThemeProvider>,
  );
}

// Click a column header by its text (bubbles to the TableCell's sort onClick).
function clickHeader(label) {
  fireEvent.click(screen.getByText(label));
}

beforeEach(() => { lastRepArgs = null; lastTeamArgs = null; });
afterEach(() => cleanup());

describe('Activity table sorting (real ReusableTable) — the columns are actually sortable', () => {
  it('rep: the previously-broken display columns now drive server ordering', () => {
    renderRep();
    expect(lastRepArgs.ordering).toBe(''); // default: no sort

    clickHeader('Account');
    expect(lastRepArgs.ordering).toBe('account__company_name');

    clickHeader('Context');
    expect(lastRepArgs.ordering).toBe('context_kind');

    clickHeader('Name');
    expect(lastRepArgs.ordering).toBe('context_name');
  });

  it('rep: the already-working accessorKey columns still sort (no regression)', () => {
    renderRep();
    clickHeader('Type');
    expect(lastRepArgs.ordering).toBe('activity_type');
    clickHeader('Due');
    expect(lastRepArgs.ordering).toBe('effective_date');
  });

  it('manager: the leading Person and Team columns are sortable too', () => {
    renderTeam();
    expect(lastTeamArgs.ordering).toBe('');

    clickHeader('Person');
    expect(lastTeamArgs.ordering).toBe('owner__last_name');

    clickHeader('Team');
    expect(lastTeamArgs.ordering).toBe('owner__team__name');
  });
});
