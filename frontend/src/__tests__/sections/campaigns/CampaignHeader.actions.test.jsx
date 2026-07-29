// frontend/src/__tests__/sections/campaigns/CampaignHeader.actions.test.jsx
//
// Item B — the workspace header's primary action button per (campaign_type × status):
//   TARGETED (any)        → primary "Log Response" (solid)
//   OUTBOUND DRAFT        → primary "Start"
//   OUTBOUND ACTIVE       → primary "Log Response"; dropdown {Pause, Complete}
//   OUTBOUND PAUSED       → primary "Resume";       dropdown {Log Response, Complete}
//   OUTBOUND COMPLETED    → no button (null)
// Also: the ACTIVE primary fires onLogResponse (not pauseCampaign); dropdown Pause fires
// pauseCampaign.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

const h = vi.hoisted(() => ({
  startCampaign: vi.fn(() => Promise.resolve({ success: true })),
  pauseCampaign: vi.fn(() => Promise.resolve({ success: true })),
  resumeCampaign: vi.fn(() => Promise.resolve({ success: true })),
  completeCampaign: vi.fn(() => Promise.resolve({ success: true })),
}));

// Keep the pure helpers (labels / schedule / progress) the hook needs; override only
// the lifecycle action calls.
vi.mock("api/campaigns/campaigns", async (importActual) => {
  const actual = await importActual();
  return {
    ...actual,
    startCampaign: (...a) => h.startCampaign(...a),
    pauseCampaign: (...a) => h.pauseCampaign(...a),
    resumeCampaign: (...a) => h.resumeCampaign(...a),
    completeCampaign: (...a) => h.completeCampaign(...a),
  };
});

vi.mock("sections/campaigns/workspace/CampaignCompletionModal", () => ({ default: () => null }));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

import useCampaignHeaderProps from "sections/campaigns/workspace/CampaignHeader";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function Harness({ campaign, onLogResponse }) {
  const { headerActions } = useCampaignHeaderProps({ campaign, onLogResponse });
  return <div>{headerActions}</div>;
}

const base = {
  id: "c1", name: "C", planned_start_date: "2026-08-01", planned_end_date: "2999-09-01",
  members: [],
};

function renderHeader(over, onLogResponse = vi.fn()) {
  render(
    <ThemeProvider theme={createTheme()}>
      <Harness campaign={{ ...base, ...over }} onLogResponse={onLogResponse} />
    </ThemeProvider>,
  );
  return onLogResponse;
}

// Open the split-button dropdown by clicking the arrow (DownOutlined) button.
function openDropdown() {
  const arrow = screen.getByRole("img", { name: "down" }).closest("button");
  fireEvent.click(arrow);
}

describe("CampaignHeader — primary action per type×status", () => {
  it("TARGETED (ACTIVE) → primary Log Response", () => {
    renderHeader({ campaign_type: "TARGETED", status: "ACTIVE" });
    expect(screen.getByRole("button", { name: /Log Response/ })).toBeInTheDocument();
  });

  it("OUTBOUND DRAFT → primary Start", () => {
    renderHeader({ campaign_type: "OUTBOUND", status: "DRAFT" });
    expect(screen.getByRole("button", { name: /Start/ })).toBeInTheDocument();
  });

  it("OUTBOUND ACTIVE → primary Log Response; dropdown {Pause, Complete}, no Resume", () => {
    renderHeader({ campaign_type: "OUTBOUND", status: "ACTIVE" });
    expect(screen.getByRole("button", { name: /Log Response/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Pause/ })).toBeNull(); // Pause is not primary

    openDropdown();
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: /Pause/ })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: /Complete/ })).toBeInTheDocument();
    expect(within(menu).queryByRole("menuitem", { name: /Log Response/ })).toBeNull();
  });

  it("OUTBOUND PAUSED → primary Resume; dropdown {Log Response, Complete}", () => {
    renderHeader({ campaign_type: "OUTBOUND", status: "PAUSED" });
    expect(screen.getByRole("button", { name: /Resume/ })).toBeInTheDocument();

    openDropdown();
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: /Log Response/ })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: /Complete/ })).toBeInTheDocument();
  });

  it("OUTBOUND COMPLETED → no action button", () => {
    renderHeader({ campaign_type: "OUTBOUND", status: "COMPLETED" });
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("ACTIVE primary fires onLogResponse; dropdown Pause fires pauseCampaign", async () => {
    const onLog = renderHeader({ campaign_type: "OUTBOUND", status: "ACTIVE" });
    fireEvent.click(screen.getByRole("button", { name: /Log Response/ }));
    expect(onLog).toHaveBeenCalledTimes(1);
    expect(h.pauseCampaign).not.toHaveBeenCalled();

    openDropdown();
    fireEvent.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: /Pause/ }));
    await waitFor(() => expect(h.pauseCampaign).toHaveBeenCalledTimes(1));
  });
});
