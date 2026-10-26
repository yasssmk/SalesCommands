// frontend/src/__tests__/sections/activities/workspace/ActivityOverviewTab.legacyMiniCardStatus.test.jsx
//
// Sprint Next steps 5.2 (R13, front) — the legacy components/cards/ActivityMiniCard
// (Previous / Next Activity of ActivityOverviewTab) uses the activity statuses
// of the app (api/accounts/activities): ON_HOLD reads "On hold"; the phantom
// IN_PROGRESS status is gone. Real render of ActivityOverviewTab, api SWR hooks
// mocked (same setup as ActivityOverviewTab.objectiveLabel.test.jsx).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import legacyCardSource from "components/cards/ActivityMiniCard.jsx?raw";

const theme = createTheme({
  iconSizes: { xs: 12, sm: 14, md: 16, lg: 18, xl: 20, xxl: 24, inline: "inherit" },
});
const renderWithTheme = (ui) => render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" }, variable: "" }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
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

vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  updateActivity: vi.fn(),
}));
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
  status: "COMPLETED",
  call_to_action: "",
  description: "",
  account: { id: "acc1", company_name: "Acme" },
  contacts: [],
  scheduled_date: "2026-07-24",
  due_date: null,
  decision_cycle: "dc-1",
  decision_step: null,
  sequence_context: {
    previous_activities: [],
    next_activities: [
      { id: "a2", title: "Paused demo", activity_type: "MEETING", status: "ON_HOLD",
        is_overdue: false, scheduled_date: "2026-08-01" },
    ],
  },
};

describe("ActivityOverviewTab — legacy ActivityMiniCard statuses (5.2)", () => {
  it("an ON_HOLD next activity reads 'On hold'", () => {
    renderWithTheme(<ActivityOverviewTab activity={activity} onUpdate={() => {}} mutate={() => {}} />);
    expect(screen.getByText("Paused demo")).toBeInTheDocument();
    expect(screen.getByText("On hold")).toBeInTheDocument();
    expect(screen.queryByText("ON_HOLD")).not.toBeInTheDocument();
  });

  it("the phantom IN_PROGRESS activity status is gone from the legacy card", () => {
    expect(legacyCardSource).not.toContain("IN_PROGRESS");
  });
});
