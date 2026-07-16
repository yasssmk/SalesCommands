// frontend/src/__tests__/components/table/TableHeaderActions.test.jsx
//
// Proves the additive enableExport prop is backward-compatible: with the
// defaults (enableExport=true, enableImport=true) the "⋮" menu still shows
// Export + Import exactly as before; and the new gating hides Export / the whole
// menu when the actions are disabled (the navigation-only Home tables).

import { describe, it, expect, vi, afterEach } from 'vitest';
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
  it('DEFAULT (backward-compat): the ⋮ menu shows Export + Import', () => {
    renderWith({});
    expect(menuButton()).toBeTruthy();
    fireEvent.click(menuButton());
    expect(screen.getByText('Export CSV')).toBeInTheDocument();
    expect(screen.getByText('Import CSV')).toBeInTheDocument();
  });

  it('enableExport=false hides Export but keeps Import', () => {
    renderWith({ enableExport: false, enableImport: true });
    fireEvent.click(menuButton());
    expect(screen.queryByText('Export CSV')).toBeNull();
    expect(screen.getByText('Import CSV')).toBeInTheDocument();
  });

  it('both disabled: no ⋮ menu at all (navigation-only)', () => {
    renderWith({ enableExport: false, enableImport: false });
    expect(menuButton()).toBeNull();
  });
});
