// frontend/src/__tests__/sections/campaigns/CampaignCard.multiselect.test.jsx
//
// Corner state machine + protected-card + selection behaviour for CampaignCard.
// Real renders only (no shared-component mocks). Hover is CSS-driven (opacity),
// so we assert DOM presence/absence and the gtm-card-delete class — not computed
// opacity.
//
// Since commit 5b the status badge is NO LONGER a corner occupant (status now
// reads from the date line in the body), so the corner at rest is empty for
// normal cards — same as the territory card. The exclusive checkbox⊕delete
// machine and TARGETED inertness are unchanged and are what these tests pin.

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
    planned_start_date: "2026-08-01",
    planned_end_date: "2026-09-01",
    actual_start_date: null,
    actual_end_date: null,
    owner: { id: "u1", full_name: "Paul DUPONT" },
    owner_team: { name: "SALES EMEA" },
    executor: null,
    executor_team: null,
    ...overrides,
  };
}

const root = () => document.querySelector(".MuiCard-root");
const qCheckbox = () => screen.queryByRole("checkbox");
const qDelete = () => document.querySelector(".gtm-card-delete");

describe("CampaignCard — corner state machine (non-protected)", () => {
  it("at rest: no corner status badge, delete present, no checkbox", () => {
    render(<CampaignCard campaign={mk()} />);
    // Status is no longer a corner badge — it reads from the schedule line.
    expect(document.querySelector(".gtm-card-status")).toBeNull();
    expect(screen.queryByText("Draft")).toBeNull();
    // Delete is present in the DOM (revealed on hover via CSS).
    expect(qDelete()).toBeTruthy();
    // No checkbox at rest.
    expect(qCheckbox()).toBeNull();
  });

  it("selection mode: checkbox only — no delete (never two at once)", () => {
    render(<CampaignCard campaign={mk()} selectionMode selected={false} />);
    expect(qCheckbox()).toBeInTheDocument();
    expect(qDelete()).toBeNull();
  });
});

describe("CampaignCard — TARGETED is protected (inert in every state)", () => {
  it("at rest: never a delete or checkbox", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "TARGETED" })} />);
    expect(qDelete()).toBeNull();
    expect(qCheckbox()).toBeNull();
  });

  it("selection mode: still no checkbox and no delete", () => {
    render(
      <CampaignCard
        campaign={mk({ campaign_type: "TARGETED" })}
        selectionMode
        selected={false}
      />,
    );
    expect(qCheckbox()).toBeNull();
    expect(qDelete()).toBeNull();
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
