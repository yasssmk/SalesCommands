// frontend/src/__tests__/sections/campaigns/TargetsTab.rowActions.test.jsx
//
// After removing the bulk-contacts UI from the Targets tab, the INDIVIDUAL per-row
// actions must still work and hit the per-contact endpoints, and there must be no
// selection checkboxes nor a bulk action bar anymore.
//   - IN_PROGRESS row → Pause calls pauseTarget(contactId, campaignId)
//   - ON_HOLD row     → Resume calls resumeTarget(contactId, campaignId)
//   - no checkbox / no "N selected" bulk bar is rendered

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

const h = vi.hoisted(() => ({
  contacts: [
    {
      id: "cc-active",
      contact_name: "Active One",
      account_name: "Acme Corp",
      department_name: "Sales",
      status: "IN_PROGRESS",
      has_on_hold: false,
      contact: { id: "ct-1", department_name: "Sales" },
    },
    {
      id: "cc-hold",
      contact_name: "Held One",
      account_name: "Acme Corp",
      department_name: "Sales",
      status: "ON_HOLD",
      has_on_hold: true,
      contact: { id: "ct-2", department_name: "Sales" },
    },
  ],
}));

vi.mock("api/campaigns/campaigns", () => ({
  useGetCampaignContacts: () => ({
    campaignContacts: h.contacts,
    campaignContactsLoading: false,
    campaignContactsError: null,
    mutateCampaignContacts: vi.fn(),
  }),
  pauseTarget: vi.fn(() => Promise.resolve({ success: true })),
  resumeTarget: vi.fn(() => Promise.resolve({ success: true })),
  stopTarget: vi.fn(() => Promise.resolve({ success: true })),
  enrollTarget: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("sections/campaigns/workspace/AddTargetToCampaignModal", () => ({
  default: () => null,
}));

import TargetsTab from "sections/campaigns/workspace/TargetsTab";
import { pauseTarget, resumeTarget } from "api/campaigns/campaigns";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const base = Palette("light", "default");
const theme = createTheme({ palette: base.palette, customShadows: CustomShadows(base) });
theme.components = componentsOverride(theme);

function renderTab() {
  return render(
    <ThemeProvider theme={theme}>
      <TargetsTab campaignId="camp-1" campaign={{ status: "ACTIVE", campaign_type: "TARGETED" }} />
    </ThemeProvider>,
  );
}

describe("TargetsTab — individual row actions (post bulk removal)", () => {
  it("Pause on an IN_PROGRESS row calls pauseTarget(contactId, campaignId)", async () => {
    renderTab();
    fireEvent.click(screen.getByRole("img", { name: "pause-circle" }).closest("button"));
    await waitFor(() => expect(pauseTarget).toHaveBeenCalledTimes(1));
    expect(pauseTarget).toHaveBeenCalledWith("cc-active", "camp-1");
  });

  it("Resume on an ON_HOLD row calls resumeTarget(contactId, campaignId)", async () => {
    renderTab();
    fireEvent.click(screen.getByRole("img", { name: "play-circle" }).closest("button"));
    await waitFor(() => expect(resumeTarget).toHaveBeenCalledTimes(1));
    expect(resumeTarget).toHaveBeenCalledWith("cc-hold", "camp-1");
  });

  it("renders no selection checkbox and no bulk action bar", () => {
    renderTab();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByText(/\bselected\b/i)).toBeNull();
  });
});
