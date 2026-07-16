// frontend/src/__tests__/views/home/TodoActivityTable.integration.test.jsx
//
// Integration test: render the REAL ReusableTable (NOT mocked) through
// TodoActivityTable, so the actual TanStack manual-mode prop contract is
// exercised. This is the test that would have caught the crash
// `getState().sorting.length` — ReusableTable spreads the caller's `sorting`
// into TanStack's state, and an undefined value overrides the [] default and
// throws in getSortedRowModel. The column/link unit tests mock ReusableTable and
// never touch this contract; this one does.
//
// Only the next/font chain (via MainCard) and the framework hooks the table
// pulls (next/navigation, swr) are stubbed — the table + TanStack are real.

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';

// The real ReusableTable + its toolbar/pagination children read the app's custom
// theme (palette.primary.lighter, customShadows.secondaryButton, …). The app
// always renders under ThemeCustomization; build the SAME theme from the real
// palette/typography/shadows modules (next/font is mocked below) so this test
// mounts the real components exactly as production does.
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
// Stub MainCard (pulls a next/font chain jsdom can't evaluate) but RENDER its
// children, so the real table body — and TanStack's getRowModel() — still runs.
vi.mock('components/MainCard', () => ({
  default: ({ children }) => <div data-testid="main-card">{children}</div>,
}));

// ReusableTable + the todo columns use these framework hooks.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ entries: () => [], toString: () => '', keys: () => [] }),
}));
vi.mock('swr', () => ({ useSWRConfig: () => ({ mutate: vi.fn() }) }));
// NB: the table's toolbar/pagination children (SelectColumnSorting, HeaderSort,
// TablePagination) are the very components that read getState().sorting — they
// are NOT mocked, so this test faithfully reproduces the crash. Only the
// react-csv leaf is aliased away (vitest.config.js).

import TodoActivityTable from 'sections/home/TodoActivityTable';

const ROWS = [
  {
    id: 'a1',
    title: 'Call Acme',
    activity_type_display: 'Call',
    effective_date: '2026-07-10',
    owner: { id: 'u1', full_name: 'Fabien Roux' },
    account: { id: 'acc1', company_name: 'Acme' },
    decision_cycle: null,
    campaign: null,
  },
  {
    id: 'a2',
    title: 'Email Globex',
    activity_type_display: 'Email',
    effective_date: '2026-07-11',
    owner: { id: 'u2', full_name: 'Uma Stone' },
    account: { id: 'acc2', company_name: 'Globex' },
    decision_cycle: null,
    campaign: null,
  },
];

afterEach(() => cleanup());

function renderTable(extraProps = {}) {
  return render(
    <ThemeProvider theme={theme}>
      <TodoActivityTable
        activities={ROWS}
        activitiesCount={2}
        activitiesLoading={false}
        activitiesError={null}
        swrKey={null}
        page={1}
        onPaginationChange={vi.fn()}
        pageSize={10}
        {...extraProps}
      />
    </ThemeProvider>,
  );
}

describe('TodoActivityTable (real ReusableTable)', () => {
  it('mounts without crashing on the TanStack manual-mode contract and renders the rows', () => {
    // Pre-fix this threw: "undefined is not an object (evaluating 'getState().sorting.length')".
    renderTable();
    expect(screen.getByText('Call Acme')).toBeInTheDocument();
    expect(screen.getByText('Email Globex')).toBeInTheDocument();
  });

  it('renders the leading (manager) columns too — the Person cell for the team table', () => {
    // Exercise the team-table shape: a leading Person column over the same real table.
    const personColumn = {
      header: 'Person',
      id: 'owner',
      enableSorting: false,
      cell: ({ row }) => <span>{row.original.owner?.full_name || '—'}</span>,
    };
    renderTable({ leadingColumns: [personColumn] });
    expect(screen.getByText('Fabien Roux')).toBeInTheDocument();
    expect(screen.getByText('Uma Stone')).toBeInTheDocument();
    expect(screen.getByText('Call Acme')).toBeInTheDocument();
  });
});
