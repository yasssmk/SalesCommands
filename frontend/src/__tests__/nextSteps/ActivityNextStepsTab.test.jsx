// frontend/src/__tests__/nextSteps/ActivityNextStepsTab.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
} from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: (props) => <input data-testid="date-picker" aria-label={props.label} />,
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({
  AdapterDayjs: class {},
}));

const mockMutateAll = vi.fn();
const mockMutateCounts = vi.fn();
const mockRouterPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockRouterPush }),
}));

const mockNextStepSignals = [
  {
    id: "ns1",
    status: "PENDING",
    suggested_title: "Follow up on pricing",
    suggested_activity_type: "CALL",
    suggested_due_date: "2026-06-15",
    suggested_objective: "Lock the pricing narrative with the CFO before Q4 close",
    source_quote: "We should discuss pricing next week",
    suggested_contacts: [
      { id: "c1", first_name: "Jane", last_name: "Doe" },
    ],
    linked_activity: null,
    _signalType: "next-steps",
  },
  {
    id: "ns2",
    status: "VALIDATED",
    suggested_title: "Send proposal",
    suggested_activity_type: "EMAIL",
    suggested_due_date: "2026-06-12",
    source_quote: "She asked for a proposal",
    suggested_contacts: [],
    linked_activity: {
      id: "act1",
      title: "Send proposal email",
      activity_type: "EMAIL",
      activity_type_display: "Email",
      status: "PLANNED",
      status_display: "Planned",
      scheduled_date: "2026-06-12",
    },
    _signalType: "next-steps",
  },
  {
    id: "ns3",
    status: "REJECTED",
    suggested_title: "Schedule demo",
    suggested_activity_type: "MEETING",
    suggested_due_date: null,
    source_quote: null,
    suggested_contacts: [],
    linked_activity: null,
    _signalType: "next-steps",
  },
];

vi.mock("hooks/useActivityAllSignals", () => ({
  default: vi.fn(() => ({
    qualificationSignals: [],
    techStackSignals: [],
    blockerSignals: [],
    nextStepSignals: mockNextStepSignals,
    allSignals: mockNextStepSignals,
    loading: false,
    error: null,
    mutateAll: mockMutateAll,
  })),
}));

vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: vi.fn(() => ({
    choices: {},
    choicesLoading: false,
  })),
  validateSignal: vi.fn(() => Promise.resolve({ success: true })),
  rejectSignal: vi.fn(() => Promise.resolve({ success: true })),
  reopenSignal: vi.fn(() => Promise.resolve({ success: true })),
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("api/accounts/activities", () => ({
  createActivity: vi.fn(() => Promise.resolve({ success: true, data: {} })),
  ACTIVITY_TYPES: {
    CALL: "CALL",
    EMAIL: "EMAIL",
    MEETING: "MEETING",
    TASK: "TASK",
    LINKEDIN: "LINKEDIN",
    OTHER: "OTHER",
  },
  ACTIVITY_TYPE_LABELS: {
    CALL: "Phone Call",
    EMAIL: "Email",
    MEETING: "Meeting",
    TASK: "Task",
    LINKEDIN: "LinkedIn Message",
    OTHER: "Other",
  },
  ACTIVITY_STATUS_LABELS: { PLANNED: "Planned" },
  ACTIVITY_STATUS_COLORS: { PLANNED: "default" },
  useGetActivityChoices: vi.fn(() => ({ choicesLoading: false })),
}));

vi.mock("api/businessData/contacts", () => ({
  useGetContacts: vi.fn(() => ({
    contacts: [
      {
        id: "c1",
        first_name: "Jane",
        last_name: "Doe",
        email: "jane@acme.com",
        job_title: "VP Eng",
      },
    ],
    contactsLoading: false,
  })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: ({ open, onClose, nextStepSignal }) =>
    open ? (
      <div data-testid="activity-modal">
        <h2>Convert to Activity</h2>
        {nextStepSignal && <span>{nextStepSignal.suggested_title}</span>}
        <button onClick={onClose}>Close</button>
      </div>
    ) : null,
}));

vi.mock("components/signals/SignalEditDrawer", () => ({
  default: ({ open }) =>
    open ? <div data-testid="signal-edit-dialog" /> : null,
}));

vi.mock("sections/activities/nextSteps/UpcomingActivitiesSection", () => ({
  default: ({ activity, onCreateActivity, isLocked }) => (
    <div data-testid="upcoming-activities-section">
      {!isLocked && (
        <button onClick={() => onCreateActivity("MEETING")}>Quick Meeting</button>
      )}
    </div>
  ),
}));

vi.mock("sections/activities/nextSteps/NextStepSuggestionDrawer", () => ({
  default: ({ open, signal, onClose }) =>
    open && signal ? (
      <div data-testid="suggestion-drawer">
        <span>{signal.suggested_title}</span>
        <button onClick={onClose} aria-label="Close drawer">Close</button>
      </div>
    ) : null,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivityNextStepsTab from "sections/activities/workspace/ActivityNextStepsTab";
import { rejectSignal } from "api/signals/signals";

// ==============================|| TEST ACTIVITY ||============================== //

const mockActivity = {
  id: "activity-123",
  account: "account-456",
  status: "COMPLETED",
  decision_step: "step-1",
  decision_cycle: "dc-1",
  sequence_context: {
    next_activities: [],
  },
};

// ==============================|| TESTS ||============================== //

describe("ActivityNextStepsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders AI Suggestions section with sorted signals (PENDING first)", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("AI Suggestions")).toBeInTheDocument();
    expect(screen.getByText("Follow up on pricing")).toBeInTheDocument();
    expect(screen.getByText("Send proposal")).toBeInTheDocument();
  });

  it("renders the suggested objective on the suggestion card", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(
      screen.getByText(
        "Lock the pricing narrative with the CFO before Q4 close",
      ),
    ).toBeInTheDocument();
  });

  it("renders Upcoming Activities section", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByTestId("upcoming-activities-section")).toBeInTheDocument();
  });

  it("hides REJECTED signals by default", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.queryByText("Schedule demo")).not.toBeInTheDocument();
  });

  it("shows REJECTED signals when Include rejected is checked", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);

    expect(screen.getByText("Schedule demo")).toBeInTheDocument();
  });

  it("shows Convert to Activity button for PENDING signals", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("Convert to Activity")).toBeInTheDocument();
  });

  it("opens convert modal when clicking Convert to Activity", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    fireEvent.click(screen.getByText("Convert to Activity"));

    expect(screen.getByTestId("activity-modal")).toBeInTheDocument();
  });

  it("opens drawer when clicking on a suggestion card", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    fireEvent.click(screen.getByText("Follow up on pricing"));

    expect(screen.getByTestId("suggestion-drawer")).toBeInTheDocument();
  });

  it("shows Converted to link for VALIDATED signals with linked activity", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText(/Converted to:/)).toBeInTheDocument();
    expect(screen.getByText("Send proposal email")).toBeInTheDocument();
  });

  it("calls rejectSignal and mutates when rejecting a suggestion", async () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    fireEvent.click(screen.getByText("Reject"));

    expect(rejectSignal).toHaveBeenCalledWith("next-steps", "ns1");
  });

  it("shows summary line with correct counts", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(
      screen.getByText(/1 AI suggestion to handle/),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 activity created/)).toBeInTheDocument();
  });

  it("shows Add manually button", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("Add manually")).toBeInTheDocument();
  });

  it("hides action buttons when isLocked", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={true}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.queryByText("Convert to Activity")).not.toBeInTheDocument();
    expect(screen.queryByText("Reject")).not.toBeInTheDocument();
    expect(screen.queryByText("Add manually")).not.toBeInTheDocument();
  });

  it("shows Upcoming Activities heading", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("Upcoming Activities")).toBeInTheDocument();
  });
});

// ==============================|| DC-ONLY AI SUGGESTIONS GUARD ||============================== //
//
// PO decision (1-bis): the AI SUGGESTIONS block (AISuggestionCard list of
// NextStepSignal) is a DC-only feature. In a campaign context (no
// decision_cycle) it must NOT be proposed. Everything else — "Add
// manually", Upcoming Activities — stays. The tab itself stays visible
// (that is asserted in ActivityTabs.test.jsx).

const mockActivityNoDc = {
  ...mockActivity,
  decision_cycle: null,
};

describe("ActivityNextStepsTab — DC-only AI suggestions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("does NOT render the AI Suggestions block without a decision cycle", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivityNoDc}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.queryByText("AI Suggestions")).not.toBeInTheDocument();
    expect(screen.queryByText("Follow up on pricing")).not.toBeInTheDocument();
  });

  it("still renders 'Add manually' without a decision cycle (manual path stays)", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivityNoDc}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("Add manually")).toBeInTheDocument();
  });

  it("renders the AI Suggestions block AND 'Add manually' with a decision cycle", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("AI Suggestions")).toBeInTheDocument();
    expect(screen.getByText("Follow up on pricing")).toBeInTheDocument();
    expect(screen.getByText("Add manually")).toBeInTheDocument();
  });
});
