// frontend/src/__tests__/sections/activities/workspace/ActivityOverviewTab.objectiveLabel.test.jsx
//
// S13 sub-step 6a — the call_to_action "CTA box" label is now "Activity
// Objective" (was "Call to Action"). Real render of ActivityOverviewTab, api
// SWR hooks mocked (project convention — see
// __tests__/nextSteps/ActivityNextStepsTab.test.jsx).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

// The component reads a custom theme.iconSizes extension (themes/iconSizes.js);
// provide it so SectionHeader's <Icon> renders.
const theme = createTheme({
  iconSizes: { xs: 12, sm: 14, md: 16, lg: 18, xl: 20, xxl: 24, inline: "inherit" },
});
const renderWithTheme = (ui) => render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);

// next/font/google is evaluated at import time by config/theme-config.js
// (pulled in transitively) and is not available under vitest.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" }, variable: "" }),
}));

// MUI date/time pickers → light stand-ins (ESM resolution + no adapter wiring).
vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: (props) => <input aria-label={props.label} />,
}));
vi.mock("@mui/x-date-pickers/TimePicker", () => ({
  TimePicker: (props) => <input aria-label={props.label} />,
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

vi.mock("api/accounts/activities", () => ({ updateActivity: vi.fn() }));
vi.mock("api/businessData/contacts", () => ({
  useGetContacts: () => ({ contacts: [], contactsLoading: false }),
}));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionCyclesByAccount: () => ({ cycles: [], cyclesLoading: false }),
  useGetDecisionStepsByCycle: () => ({ steps: [], stepsLoading: false }),
}));

import ActivityOverviewTab from "sections/activities/workspace/ActivityOverviewTab";

afterEach(cleanup);

const activity = {
  id: "a1",
  title: "Follow up",
  activity_type: "CALL",
  status: "PLANNED",
  call_to_action: "Ask about budget",
  description: "",
  account: { id: "acc1", company_name: "Acme" },
  contacts: [],
  scheduled_date: "2026-07-24",
  due_date: null,
  decision_cycle: null,
  decision_step: null,
};

describe("ActivityOverviewTab — Activity Objective label", () => {
  it("renders the CTA box labelled 'Activity Objective'", () => {
    renderWithTheme(<ActivityOverviewTab activity={activity} onUpdate={() => {}} mutate={() => {}} />);

    expect(screen.getByText("Activity Objective")).toBeInTheDocument();
    expect(screen.queryByText("Call to Action")).toBeNull();
  });

  it("shows the activity-variant objective + description placeholders in edit mode (6e)", () => {
    // Empty values so each editor shows its click-to-edit CTA; entering edit mode
    // surfaces the placeholder in the input.
    const empty = { ...activity, call_to_action: "", description: "" };
    renderWithTheme(<ActivityOverviewTab activity={empty} onUpdate={() => {}} mutate={() => {}} />);

    fireEvent.click(screen.getByText("Click to define objective..."));
    expect(
      screen.getByPlaceholderText(
        "Describe the goal of this activity — the AI recommendations will be more accurate.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText("Click to add description..."));
    expect(
      screen.getByPlaceholderText(
        "Describe the context of this activity — the AI recommendations will be more accurate.",
      ),
    ).toBeInTheDocument();
  });
});
