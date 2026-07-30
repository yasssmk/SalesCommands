// frontend/src/__tests__/sections/territories/AlertTerritoryDelete.warning.test.jsx
//
// Lot 1 / commit 2 — the delete modal warns about the destructive cascade
// (draft/finished campaigns relying only on this territory are deleted; an
// active-campaign territory is blocked). System territories show their own
// message and no cascade warning.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

vi.mock("api/territories/territories", () => ({ deleteTerritory: vi.fn() }));
vi.mock("utils/displayError", () => ({
  displayErrorSnackbar: vi.fn(),
  displaySuccessSnackbar: vi.fn(),
}));

import AlertTerritoryDelete from "sections/territories/AlertTerritoryDelete";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderModal(territory) {
  render(
    <ThemeProvider theme={createTheme()}>
      <AlertTerritoryDelete territory={territory} open handleClose={vi.fn()} />
    </ThemeProvider>,
  );
}

describe("AlertTerritoryDelete — cascade warning", () => {
  it("non-system territory shows the cascade warning", () => {
    renderModal({ id: "t1", name: "West", is_system: false });
    expect(screen.getByText(/rely only on this territory/i)).toBeInTheDocument();
    expect(screen.getByText(/active campaign cannot be deleted/i)).toBeInTheDocument();
  });

  it("system territory shows the system message, not the cascade warning", () => {
    renderModal({ id: "t2", name: "All", is_system: true });
    expect(
      screen.getByText(/System territories cannot be deleted/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/rely only on this territory/i)).toBeNull();
  });
});
