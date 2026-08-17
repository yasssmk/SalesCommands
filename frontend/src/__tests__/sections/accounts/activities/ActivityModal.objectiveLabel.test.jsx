// frontend/src/__tests__/sections/accounts/activities/ActivityModal.objectiveLabel.test.jsx
//
// S13 sub-step 6a — the call_to_action field's displayed label is now
// "Activity Objective" (was "Call to Action"). Real render of ActivityModal,
// with the api SWR hooks + MUI date pickers mocked (project convention — see
// __tests__/nextSteps/ActivityNextStepsTab.test.jsx for the mock style).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

// next/font/google is evaluated at import time by config/theme-config.js
// (pulled in transitively) and is not available under vitest.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" }, variable: "" }),
}));

// MUI date/time pickers → light stand-ins (no adapter wiring in tests).
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

// api hooks + constants used by the modal.
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

afterEach(cleanup);

describe("ActivityModal — Activity Objective label", () => {
  it("renders the objective field labelled 'Activity Objective'", () => {
    render(<ActivityModal open onClose={() => {}} accountId="acc1" />);

    expect(screen.getByText("Activity Objective")).toBeInTheDocument();
    // The old label must be gone.
    expect(screen.queryByText("Call to Action")).toBeNull();
  });

  it("shows the activity-variant objective + description placeholders (6e)", () => {
    render(<ActivityModal open onClose={() => {}} accountId="acc1" />);

    expect(
      screen.getByPlaceholderText(
        "Describe the goal of this activity — the AI recommendations will be more accurate.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(
        "Describe the context of this activity — the AI recommendations will be more accurate.",
      ),
    ).toBeInTheDocument();
  });
});
