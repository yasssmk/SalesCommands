// frontend/src/__tests__/nextSteps/ActivityNextStepsTab.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
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
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));

const mockMutateAll = vi.fn();
const mockMutateCounts = vi.fn();
const mockRouterPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockRouterPush }),
  usePathname: () => "/activities/activity-123",
}));
// The workspace coque in push mode (large screen).
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));

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

// 5.8d — the creation in the coque reads the user (owner) and the cycles.
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u-1", first_name: "Yasmine", last_name: "Kawi" }, tenantId: "t-1" }),
}));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionCyclesByAccount: () => ({ cycles: [], cyclesLoading: false }),
  useGetDecisionStepsByCycle: () => ({ steps: [], stepsLoading: false }),
}));
vi.mock("api/signals/aggregatedSignals", () => ({
  default: vi.fn(() => ({
    signals: mockNextStepSignals,
    loading: false,
    error: null,
    mutate: mockMutateAll,
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
  useNextStepLinkCandidates: vi.fn(() => ({ candidates: [], candidatesLoading: false })),
  getSignal: vi.fn(() => Promise.resolve({ success: true, data: {} })),
  useNextStepCitedContacts: vi.fn(() => ({ citedContacts: [], citedLoading: false })),
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  createActivity: vi.fn(() => Promise.resolve({ success: true, data: {} })),
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

// ==============================|| IMPORTS (after mocks) ||============================== //

// The extraction (the shared Run AI action, 5.12 B) is out of scope here —
// covered by NextStepsBandLayoutPage.
vi.mock("sections/activities/workspace/RunAIAnalysisButton", () => ({
  default: () => null,
  RUN_AI_TRIGGER_VARIANTS: { BUTTON: "button", PILL: "pill" },
}));

import ActivityNextStepsTab from "sections/activities/workspace/ActivityNextStepsTab";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { rejectSignal, validateSignal } from "api/signals/signals";
import WorkspaceCoque from "../_utils/workspaceCoque";

// ==============================|| TEST ACTIVITY ||============================== //

const mockActivity = {
  id: "activity-123",
  account: "account-456",
  status: "PLANNED",
  decision_step: "step-1",
  decision_cycle: "dc-1",
  sequence_context: {
    next_activities: [],
  },
};

// ==============================|| TESTS ||============================== //
//
// Sprint Next steps 5.3 — the band in 4 parts: (1) the next planned step,
// (2-3) the generic SignalsValidationList filtered on next-steps (the row ✓
// opens the drawer, never validates; ✗ rejects; a resolved next step carries
// its activity on the row's 3rd line), (4) "Set a next step manually" —
// replaced in 5.8e by "+ Add next step" (header of part 1). The former AI suggestion cards, filter bar and summary line are gone.

const renderTab = (props = {}) =>
  render(
    <WorkspaceCoque>
      <ActivityNextStepsTab
        activity={mockActivity}
        mutateCounts={mockMutateCounts}
        {...props}
      />
    </WorkspaceCoque>,
  );

describe("ActivityNextStepsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("reads the next steps from the aggregated endpoint, all 3 statuses", () => {
    renderTab();
    expect(useAggregatedSignals).toHaveBeenCalledWith(
      expect.objectContaining({
        activityId: "activity-123",
        signalTypes: ["next-steps"],
        statuses: ["PENDING", "VALIDATED", "REJECTED"],
      }),
    );
  });

  it("lists the pending next steps in the generic validation list", () => {
    renderTab();
    expect(screen.getByText("To validate")).toBeInTheDocument();
    expect(screen.getByText("Follow up on pricing")).toBeInTheDocument();
    expect(screen.getByText("Validated")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("no AI suggestion card, filter bar or summary line any more", () => {
    renderTab();
    expect(screen.queryByText("AI Suggestions")).not.toBeInTheDocument();
    expect(screen.queryByText("Convert to Activity")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByText(/AI suggestion to handle/)).not.toBeInTheDocument();
  });

  // 5.12 B — the next planned step left the band (it is in Context).
  it("renders no 'Next planned step' sub-block any more", () => {
    renderTab();
    expect(screen.queryByText("Next planned step")).not.toBeInTheDocument();
    expect(screen.queryByTestId("next-planned-step-block")).not.toBeInTheDocument();
  });

  it("opens the detail in the workspace coque when clicking a next step", () => {
    renderTab();
    fireEvent.click(screen.getByText("Follow up on pricing"));
    expect(screen.getByTestId("next-step-detail-body")).toBeInTheDocument();
  });

  it("the row ✓ opens the validation flow and validates nothing", () => {
    renderTab();
    fireEvent.click(screen.getByLabelText("Validate signal"));
    expect(screen.getByTestId("next-step-validate-flow")).toBeInTheDocument();
    expect(validateSignal).not.toHaveBeenCalled();
  });

  it("the row ✗ calls rejectSignal and mutates", async () => {
    renderTab();
    fireEvent.click(screen.getByLabelText("Reject signal"));
    expect(rejectSignal).toHaveBeenCalledWith("next-steps", "ns1");
    await waitFor(() => expect(mockMutateAll).toHaveBeenCalled());
    expect(mockMutateCounts).toHaveBeenCalled();
  });

  it("a resolved next step shows its activity on the 3rd line", () => {
    renderTab();
    fireEvent.click(screen.getByText("Validated"));
    expect(screen.getByText("Send proposal email")).toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line-extra")).toHaveLength(1);
  });

  // 5.8e — "+ Add next step" replaces "Set a next step manually" and the chips.
  const ADD = { name: "+ Add next step" };

  it("shows the '+ Add next step' pill, and no 'Set a next step manually'", () => {
    renderTab();
    expect(screen.getByRole("button", ADD)).toBeInTheDocument();
    expect(screen.queryByText("Set a next step manually")).not.toBeInTheDocument();
  });

  it("a CANCELLED activity locks the band: no '+ Add next step', no row action", () => {
    renderTab({ activity: { ...mockActivity, status: "CANCELLED" } });
    expect(screen.queryByRole("button", ADD)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Validate signal")).not.toBeInTheDocument();
  });

  it("a COMPLETED activity does NOT lock the band (PO decision)", () => {
    renderTab({ activity: { ...mockActivity, status: "COMPLETED" } });
    expect(screen.getByRole("button", ADD)).toBeInTheDocument();
    expect(screen.getByLabelText("Validate signal")).toBeInTheDocument();
  });

  it("opens the activity creation in the coque from a type pill of '+ Add next step'", () => {
    renderTab();
    fireEvent.click(screen.getByRole("button", ADD));
    fireEvent.click(within(screen.getByTestId("add-next-step-types")).getByRole("button", { name: "Meeting" }));
    expect(screen.getByTestId("activity-create")).toBeInTheDocument();
    expect(screen.queryByTestId("activity-modal")).not.toBeInTheDocument();
  });
});

// ==============================|| DC-ONLY GUARD ||============================== //
//
// PO decision (1-bis): the next steps extracted by the AI (parts 2-3) are a
// DC-only feature. In a campaign context (no decision_cycle) they are NOT
// proposed. 5.12 B (PO): "+ Add next step" is DC-only too (hasSuggestedNextSteps);
// the page hides the band when it has nothing to show (NextStepsBandLayoutPage).

const mockActivityNoDc = {
  ...mockActivity,
  decision_cycle: null,
};

describe("ActivityNextStepsTab — DC-only parts 2-3", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("does NOT render the next steps to validate without a decision cycle", () => {
    renderTab({ activity: mockActivityNoDc });
    expect(screen.queryByText("To validate")).not.toBeInTheDocument();
    expect(screen.queryByText("Follow up on pricing")).not.toBeInTheDocument();
  });

  it("5.12 B: no '+ Add next step' without a decision cycle", () => {
    renderTab({ activity: mockActivityNoDc });
    expect(screen.queryByRole("button", { name: "+ Add next step" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("add-next-step")).not.toBeInTheDocument();
  });

  it("renders parts 2-3 AND '+ Add next step' with a decision cycle", () => {
    renderTab();
    expect(screen.getByText("Follow up on pricing")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Add next step" })).toBeInTheDocument();
  });
});
