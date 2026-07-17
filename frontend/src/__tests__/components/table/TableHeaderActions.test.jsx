// frontend/src/__tests__/components/table/TableHeaderActions.test.jsx
//
// Mounts the REAL shared toolbar. This is the backward-compat guard for the
// 20+ tables in the repo: the "⋮" menu is ALWAYS present with Export CSV, and
// enableImport gates ONLY the Import item. (A prior enableExport prop + a
// whole-menu-hidden path were reverted — the original component already offered
// everything the navigation-only Home needed via enableImport={false}.)

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));

import Palette from 'themes/palette';
import Typography from 'themes/typography';
import CustomShadows from 'themes/shadows';

// react-csv (the CSV export leaf) isn't installed; aliased to a stub in
// vitest.config so the real component mounts.
import TableHeaderActions from 'components/third-party/react-table/TableHeaderActions';

const paletteTheme = Palette('light', 'default');
const theme = createTheme({
  palette: paletteTheme.palette,
  customShadows: CustomShadows(paletteTheme),
  typography: Typography(`'Public Sans', sans-serif`),
});

const renderWith = (props) =>
  render(
    <ThemeProvider theme={theme}>
      <TableHeaderActions {...props} />
    </ThemeProvider>,
  );

const menuButton = () => document.querySelector('[aria-haspopup="true"]');

afterEach(() => cleanup());

describe('TableHeaderActions', () => {
  it('DEFAULT (all other tables): the ⋮ menu shows Export + Import', () => {
    renderWith({});
    expect(menuButton()).toBeTruthy();
    fireEvent.click(menuButton());
    expect(screen.getByText('Export CSV')).toBeInTheDocument();
    expect(screen.getByText('Import CSV')).toBeInTheDocument();
  });

  it('enableImport=false (the Home): the ⋮ menu stays, Export kept, Import gone', () => {
    renderWith({ enableImport: false });
    // the button is ALWAYS present — the whole point of the A4 revert
    expect(menuButton()).toBeTruthy();
    fireEvent.click(menuButton());
    expect(screen.getByText('Export CSV')).toBeInTheDocument();
    expect(screen.queryByText('Import CSV')).toBeNull();
  });
});
