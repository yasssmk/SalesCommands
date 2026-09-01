// frontend/src/__tests__/sections/accounts/activities/ActivityModal.objectivePrefill.test.jsx
//
// S13 sub-step 5 — converting a NextStepSignal must pre-fill the "Activity
// Objective" (call_to_action) field from nextStepSignal.suggested_objective,
// mirroring how title/type/date are already pre-filled. Real render of
// ActivityModal, api SWR hooks + MUI pickers mocked (project convention —
// see ActivityModal.objectiveLabel.test.jsx for the mock style).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" }, variable: "" }),
}));

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

vi.mock("api/accounts/activities", () => ({
  createActivity: vi.fn(),
  createActivityWithEntities: vi.fn(),
  updateActivity: vi.fn(),
  useGetActivityChoices: () => ({ choicesLoading: false }),
  ACTIVITY_TYPES: { CALL: "CALL", EMAIL: "EMAIL", MEETING: "MEETING", TASK: "TASK" },
  ACTIVITY_TYPE_LABELS: { CALL: "Call", EMAIL: "Email", MEETING: "Meeting", TASK: "Task" },
  ACTIVITY_STATUSES: { PLANNED: "PLANNED", COMPLETED: "COMPLETED" },
  ACTIVITY_STATUS_LABELS: { PLANNED: "Planned", COMPLETED: "Completed" },
}));

vi.mock("api/businessData/contacts", () => ({
  useGetContacts: () => ({ contacts: [], contactsLoading: false }),
}));

vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionCyclesByAccount: () => ({ cycles: [], cyclesLoading: false }),
  useGetDecisionStepsByCycle: () => ({ steps: [], stepsLoading: false }),
}));

vi.mock("utils/displayError", () => ({
  displayErrorSnackbar: vi.fn(),
  displaySuccessSnackbar: vi.fn(),
}));

import ActivityModal from "sections/accounts/activities/ActivityModal";

const OBJECTIVE_PLACEHOLDER =
  "Describe the goal of this activity — the AI recommendations will be more accurate.";

afterEach(cleanup);

describe("ActivityModal — objective pre-fill on conversion", () => {
  it("pre-fills the objective from nextStepSignal.suggested_objective when converting", () => {
    render(
      <ActivityModal
        open
        onClose={() => {}}
        accountId="acc1"
        activity={null}
        nextStepSignal={{
          id: "ns1",
          suggested_title: "Follow up on pricing",
          suggested_activity_type: "CALL",
          suggested_objective: "Lock the pricing narrative",
        }}
      />,
    );

    const objective = screen.getByPlaceholderText(OBJECTIVE_PLACEHOLDER);
    expect(objective.value).toBe("Lock the pricing narrative");
  });

  it("keeps the existing activity's call_to_action when editing (fallback order)", () => {
    render(
      <ActivityModal
        open
        onClose={() => {}}
        accountId="acc1"
        activity={{
          id: "act1",
          title: "Existing activity",
          activity_type: "CALL",
          status: "PLANNED",
          call_to_action: "Existing objective",
        }}
        nextStepSignal={{
          id: "ns1",
          suggested_objective: "Signal objective (must not win)",
        }}
      />,
    );

    const objective = screen.getByPlaceholderText(OBJECTIVE_PLACEHOLDER);
    expect(objective.value).toBe("Existing objective");
  });
});
