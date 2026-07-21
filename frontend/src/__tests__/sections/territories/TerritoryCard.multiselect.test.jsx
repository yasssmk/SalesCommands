// frontend/src/__tests__/sections/territories/TerritoryCard.multiselect.test.jsx
//
// Corner state machine + protected-card + selection behaviour for TerritoryCard.
// Real renders only. Hover is CSS-driven, so we assert DOM presence/absence and
// the gtm-card-delete class — not computed opacity. Territory has no rest status
// for normal cards; its protected status is the header "System" chip.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { useRouter } from "next/navigation";

import TerritoryCard from "sections/territories/TerritoryCard";

afterEach(cleanup);

const push = vi.fn();
beforeEach(() => {
  push.mockReset();
  vi.mocked(useRouter).mockReturnValue({ push, replace: vi.fn(), back: vi.fn() });
});

const themeWithError = createTheme({
  palette: {
    divider: "#e0e0e0",
    error: {
      lighter: "#fde8e8",
      light: "#f8b4b4",
      main: "#e02424",
      dark: "#9b1c1c",
      contrastText: "#fff",
    },
  },
});

function mk(overrides = {}) {
  return {
    id: "t1",
    name: "Enterprise",
    type: "ACCOUNT",
    description: "",
    is_system: false,
    filter_definition: {},
    ...overrides,
  };
}

const root = () => document.querySelector(".MuiCard-root");
const qCheckbox = () => screen.queryByRole("checkbox");
const qDelete = () => document.querySelector(".gtm-card-delete");

describe("TerritoryCard — corner state machine (non-system)", () => {
  it("at rest: empty status, delete present, no checkbox", () => {
    render(<TerritoryCard territory={mk()} />);
    expect(screen.queryByText("System")).toBeNull(); // no status for normal cards
    expect(qDelete()).toBeTruthy();
    expect(qCheckbox()).toBeNull();
  });

  it("selection mode: checkbox only — no delete (never two at once)", () => {
    render(<TerritoryCard territory={mk()} selectionMode selected={false} />);
    expect(qCheckbox()).toBeInTheDocument();
    expect(qDelete()).toBeNull();
  });
});

describe("TerritoryCard — is_system is protected (inert in every state)", () => {
  it("at rest: System chip present, never a delete or checkbox", () => {
    render(<TerritoryCard territory={mk({ is_system: true })} />);
    expect(screen.getByText("System")).toBeInTheDocument();
    expect(qDelete()).toBeNull();
    expect(qCheckbox()).toBeNull();
  });

  it("selection mode: still no checkbox and no delete; System chip stays", () => {
    render(
      <TerritoryCard territory={mk({ is_system: true })} selectionMode selected={false} />,
    );
    expect(qCheckbox()).toBeNull();
    expect(qDelete()).toBeNull();
    expect(screen.getByText("System")).toBeInTheDocument();
  });
});

describe("TerritoryCard — corner clicks never navigate (stopPropagation)", () => {
  it("selection mode: clicking the checkbox selects but does not navigate", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<TerritoryCard territory={mk()} selectionMode onSelect={onSelect} />);

    await user.click(screen.getByRole("checkbox"));
    expect(onSelect).toHaveBeenCalledWith("t1");
    expect(push).not.toHaveBeenCalled();
  });

  it("rest: clicking the delete does not navigate", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<TerritoryCard territory={mk()} onDelete={onDelete} />);

    await user.click(qDelete().querySelector("button"));
    expect(onDelete).toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("clicking the card body navigates to the workspace", async () => {
    const user = userEvent.setup();
    render(<TerritoryCard territory={mk()} />);

    await user.click(screen.getByText("Enterprise"));
    expect(push).toHaveBeenCalledWith("/territories/t1");
  });
});

describe("TerritoryCard — selection highlight uses the error palette", () => {
  it("selected card border + background resolve to the error tokens", () => {
    render(
      <ThemeProvider theme={themeWithError}>
        <TerritoryCard territory={mk()} selected />
      </ThemeProvider>,
    );
    const card = root();
    expect(card).toHaveStyle({ borderColor: "rgb(224, 36, 36)" });
    expect(card).toHaveStyle({ backgroundColor: "rgb(253, 232, 232)" });
  });

  it("unselected card does NOT use the error tokens", () => {
    render(
      <ThemeProvider theme={themeWithError}>
        <TerritoryCard territory={mk()} selected={false} />
      </ThemeProvider>,
    );
    const card = root();
    expect(card).not.toHaveStyle({ borderColor: "rgb(224, 36, 36)" });
    expect(card).not.toHaveStyle({ backgroundColor: "rgb(253, 232, 232)" });
  });
});
