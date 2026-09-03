// frontend/src/__tests__/sections/activities/workspace/ActivityHeader.demoType.test.jsx
//
// UX Activity · Context S1 — the DEMO activity type must be a first-class
// citizen on the FRONT (the backend enum ActivityType.DEMO exists since
// migration 0019). Two guarantees:
//   1. api/accounts/activities.js exposes DEMO in the type/label/icon maps.
//   2. The activity header renders a DEMO activity with its dedicated label
//      ("Demo"), icon (desktop) and chip colour — NOT the OTHER fallback
//      (question-circle / raw "DEMO" / default colour).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, renderHook, cleanup, screen } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import Typography from "themes/typography";
import CustomShadows from "themes/shadows";
import IconSizes from "themes/iconSizes";
import AphoriQ from "themes/aphoriq";

import {
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_TYPE_ICONS,
} from "api/accounts/activities";

// next/font is not available in the test env — stub it like the sibling tests.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

// CampaignOutcomeModal pulls @mui/x-date-pickers (not ESM-resolvable here) and
// is only referenced inside the header's unrendered modals bundle.
vi.mock("sections/campaigns/CampaignOutcomeModal", () => ({ default: () => null }));

// EditActivityContent pulls @mui/x-date-pickers (unresolvable ESM in this env);
// the header only references it on the ⋮ Edit click, so stub it here.
vi.mock("sections/activities/workspace/EditActivityContent", () => ({ default: () => null }));

// Router spy — the header pushes navigation through next/navigation.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import useActivityHeaderProps from "sections/activities/workspace/ActivityHeader";

const paletteTheme = Palette("light", "default");
const theme = createTheme({
  breakpoints: { values: { xs: 0, sm: 768, md: 1024, lg: 1266, xl: 1440 } },
  palette: paletteTheme.palette,
  customShadows: CustomShadows(paletteTheme),
  typography: Typography(`'Public Sans', sans-serif`),
  iconSizes: IconSizes(),
  aphoriQ: AphoriQ({ palette: paletteTheme.palette }),
});

const wrapper = ({ children }) => (
  <ThemeProvider theme={theme}>{children}</ThemeProvider>
);

const demoActivity = {
  id: "act-demo",
  activity_type: "DEMO",
  status: "PLANNED",
  title: "Product demo",
  account_detail: { id: "acc-1", company_name: "ACME" },
};

afterEach(() => {
  cleanup();
});

describe("Activity type maps — DEMO (api/accounts/activities.js)", () => {
  it("exposes DEMO in the type, label and icon maps", () => {
    expect(ACTIVITY_TYPES.DEMO).toBe("DEMO");
    expect(ACTIVITY_TYPE_LABELS.DEMO).toBe("Demo");
    expect(ACTIVITY_TYPE_ICONS.DEMO).toBe("DesktopOutlined");
  });
});

describe("ActivityHeader — DEMO activity type", () => {
  it("renders the DEMO icon in the avatar tile, not the OTHER fallback", () => {
    // HEADER-1: the activity type is shown by the avatar TILE (icon), not a
    // type chip — so a DEMO activity carries the desktop icon in a rounded tile.
    const { result } = renderHook(
      () => useActivityHeaderProps({ activity: demoActivity }),
      { wrapper },
    );

    const { container } = render(<div>{result.current.avatar}</div>, { wrapper });

    // Avatar carries the dedicated DEMO icon, not the question-circle fallback.
    expect(container.querySelector(".anticon-desktop")).toBeTruthy();
    expect(container.querySelector(".anticon-question-circle")).toBeFalsy();
    // …in a rounded tile (not a circular avatar).
    expect(container.querySelector(".MuiAvatar-rounded")).toBeTruthy();
    expect(container.querySelector(".MuiAvatar-circular")).toBeFalsy();
  });
});
