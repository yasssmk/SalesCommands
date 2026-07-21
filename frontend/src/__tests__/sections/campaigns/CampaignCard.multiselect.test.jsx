// frontend/src/__tests__/sections/campaigns/CampaignCard.multiselect.test.jsx
//
// Corner state machine + protected-card + selection behaviour for CampaignCard.
// Real renders only (no shared-component mocks). Hover is CSS-driven (opacity),
// so we assert DOM presence/absence and the gtm-card-status / gtm-card-delete
// classes — not computed opacity.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import CampaignCard from "sections/campaigns/CampaignCard";

afterEach(cleanup);

// Minimal theme providing the custom error.* tokens the app theme defines, so
// the error-palette selection highlight resolves to concrete colors. The card
// itself renders for real — only the palette source is a lightweight stand-in.
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
    id: "c1",
    name: "Q3 Outbound",
    campaign_type: "OUTBOUND",
    status: "DRAFT",
    description: "",
    accounts_count: 3,
    activities_total: 10,
    activities_completed: 4,
    objective_type: null,
    objective_target: 0,
    objective_current: 0,
    start_date: null,
    end_date: null,
    members: [],
    ...overrides,
  };
}

const root = () => document.querySelector(".MuiCard-root");
const qCheckbox = () => screen.queryByRole("checkbox");
const qDelete = () => document.querySelector(".gtm-card-delete");
const qStatusClass = () => document.querySelector(".gtm-card-status");

describe("CampaignCard — corner state machine (non-protected)", () => {
  it("at rest: status present (gtm-card-status), delete present, no checkbox", () => {
    render(<CampaignCard campaign={mk()} />);
    // Status is the rest occupant.
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(qStatusClass()).toBeTruthy();
    // Delete is present in the DOM (revealed on hover via CSS).
    expect(qDelete()).toBeTruthy();
    // No checkbox at rest.
    expect(qCheckbox()).toBeNull();
  });

  it("selection mode: checkbox only — status dropped, no delete (never two at once)", () => {
    render(<CampaignCard campaign={mk()} selectionMode selected={false} />);
    expect(qCheckbox()).toBeInTheDocument();
    expect(qDelete()).toBeNull();
    // Status is removed (not merely hidden) so the corner has a single occupant.
    expect(screen.queryByText("Draft")).toBeNull();
    expect(qStatusClass()).toBeNull();
  });
});

describe("CampaignCard — TARGETED is protected (inert in every state)", () => {
  it("at rest: status present WITHOUT gtm-card-status class, never a delete", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "TARGETED" })} />);
    expect(screen.getByText("Draft")).toBeInTheDocument();
    // Protected status is rendered outside the hover mechanism.
    expect(qStatusClass()).toBeNull();
    expect(qDelete()).toBeNull();
    expect(qCheckbox()).toBeNull();
  });

  it("selection mode: still no checkbox and no delete; status stays", () => {
    render(
      <CampaignCard
        campaign={mk({ campaign_type: "TARGETED" })}
        selectionMode
        selected={false}
      />,
    );
    expect(qCheckbox()).toBeNull();
    expect(qDelete()).toBeNull();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(qStatusClass()).toBeNull();
  });
});

describe("CampaignCard — corner clicks never navigate (stopPropagation)", () => {
  it("selection mode: clicking the checkbox selects but does not open", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const onSelect = vi.fn();
    render(
      <CampaignCard
        campaign={mk()}
        selectionMode
        onOpen={onOpen}
        onSelect={onSelect}
      />,
    );

    await user.click(screen.getByRole("checkbox"));
    expect(onSelect).toHaveBeenCalledWith("c1");
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("rest: clicking the delete does not open the card", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const onDelete = vi.fn();
    render(<CampaignCard campaign={mk()} onOpen={onOpen} onDelete={onDelete} />);

    await user.click(qDelete().querySelector("button"));
    expect(onDelete).toHaveBeenCalled();
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("clicking the card body opens it", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<CampaignCard campaign={mk()} onOpen={onOpen} />);

    await user.click(screen.getByText("Q3 Outbound"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});

describe("CampaignCard — selection highlight uses the error palette", () => {
  it("selected card border + background resolve to the error tokens", () => {
    render(
      <ThemeProvider theme={themeWithError}>
        <CampaignCard campaign={mk()} selected />
      </ThemeProvider>,
    );
    const card = root();
    // error.main #e02424 -> rgb(224, 36, 36); error.lighter #fde8e8 -> rgb(253, 232, 232).
    expect(card).toHaveStyle({ borderColor: "rgb(224, 36, 36)" });
    expect(card).toHaveStyle({ backgroundColor: "rgb(253, 232, 232)" });
  });

  it("unselected card does NOT use the error tokens", () => {
    render(
      <ThemeProvider theme={themeWithError}>
        <CampaignCard campaign={mk()} selected={false} />
      </ThemeProvider>,
    );
    const card = root();
    expect(card).not.toHaveStyle({ borderColor: "rgb(224, 36, 36)" });
    expect(card).not.toHaveStyle({ backgroundColor: "rgb(253, 232, 232)" });
  });
});
