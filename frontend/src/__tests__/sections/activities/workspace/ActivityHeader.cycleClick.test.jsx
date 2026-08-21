// frontend/src/__tests__/sections/activities/workspace/ActivityHeader.cycleClick.test.jsx
//
// S2.1 — clicking the CYCLE NAME in the activity workspace header (the crumb
// next to the account name) must route to the DC workspace TIMELINE tab of the
// activity's parent cycle, not to the account's decision-cycle tab.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, renderHook, cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import Typography from "themes/typography";
import CustomShadows from "themes/shadows";
import IconSizes from "themes/iconSizes";

// next/font is not available in the test env — stub it like the other
// theme-consuming tests do.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

// CampaignOutcomeModal pulls @mui/x-date-pickers, which does not resolve as
// ESM under the test env. The header only references it inside its (unrendered)
// modals bundle, so stub it out to keep the import graph clean.
vi.mock("sections/campaigns/CampaignOutcomeModal", () => ({ default: () => null }));

// Router spy — the header pushes navigation through next/navigation.
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import useActivityHeaderProps from "sections/activities/workspace/ActivityHeader";

const paletteTheme = Palette("light", "default");
const theme = createTheme({
  breakpoints: { values: { xs: 0, sm: 768, md: 1024, lg: 1266, xl: 1440 } },
  palette: paletteTheme.palette,
  customShadows: CustomShadows(paletteTheme),
  typography: Typography(`'Public Sans', sans-serif`),
  iconSizes: IconSizes(),
});

const activity = {
  id: "act-1",
  activity_type: "CALL",
  status: "PLANNED",
  title: "Discovery call",
  account_detail: { id: "acc-1", company_name: "ACME" },
  decision_cycle: "cyc-9",
  decision_cycle_detail: { name: "New HQ rollout" },
};

const wrapper = ({ children }) => (
  <ThemeProvider theme={theme}>{children}</ThemeProvider>
);

afterEach(() => {
  cleanup();
  pushMock.mockReset();
});

describe("ActivityHeader — cycle-name click routing", () => {
  it("routes the cycle name to the DC workspace timeline of the parent cycle", async () => {
    const { result } = renderHook(
      () => useActivityHeaderProps({ activity }),
      { wrapper },
    );

    // Render only the info items (which hold the clickable cycle name).
    render(<div>{result.current.infoItems}</div>, { wrapper });

    await userEvent.click(screen.getByText("New HQ rollout"));

    expect(pushMock).toHaveBeenCalledWith(
      "/accounts/acc-1/dc/cyc-9?tab=timeline",
    );
    // Not the old account decision-cycle tab.
    expect(pushMock).not.toHaveBeenCalledWith(
      expect.stringContaining("tab=decision-cycle"),
    );
  });
});
