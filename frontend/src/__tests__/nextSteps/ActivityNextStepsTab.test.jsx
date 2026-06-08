// frontend/src/__tests__/nextSteps/ActivityNextStepsTab.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
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

vi.mock("sections/activities/signals/SignalEditDialog", () => ({
  default: ({ open }) =>
    open ? <div data-testid="signal-edit-dialog" /> : null,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivityNextStepsTab from "sections/activities/workspace/ActivityNextStepsTab";
import { rejectSignal } from "api/signals/signals";

// ==============================|| TEST ACTIVITY ||============================== //

const mockActivity = {
  id: "activity-123",
  account: "account-456",
  status: "COMPLETED",
};

// ==============================|| TESTS ||============================== //

describe("ActivityNextStepsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders AI Suggestions section with PENDING signals", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("AI Suggestions")).toBeInTheDocument();
    expect(screen.getByText("Follow up on pricing")).toBeInTheDocument();
    expect(screen.getByText(/suggested 2026-06-15/)).toBeInTheDocument();
  });

  it("renders Linked Activities section with VALIDATED signals", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("Linked Activities")).toBeInTheDocument();
    expect(screen.getByText("Send proposal email")).toBeInTheDocument();
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

  it("shows View Activity for VALIDATED signals with linked_activity", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    expect(screen.getByText("Open Activity")).toBeInTheDocument();
  });

  it("navigates to activity workspace when clicking Open Activity", () => {
    render(
      <ActivityNextStepsTab
        activity={mockActivity}
        isLocked={false}
        mutateCounts={mockMutateCounts}
      />,
    );

    fireEvent.click(screen.getByText("Open Activity"));

    expect(mockRouterPush).toHaveBeenCalledWith(
      "/activities/act1/workspace?tab=overview",
    );
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
});
