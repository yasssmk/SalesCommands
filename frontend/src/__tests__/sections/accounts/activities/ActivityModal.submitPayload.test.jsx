// frontend/src/__tests__/sections/accounts/activities/ActivityModal.submitPayload.test.jsx
//
// Bug (e) — the create payload must not carry `previous_activity_id`: the
// Activity.previous_activity / next_activity fields were dropped (backend
// migration activities 0016) and the create serializers no longer know them.
// Real render + real submit of ActivityModal on BOTH create paths (standard
// POST /module-activities/ and create-with-entities); the rest of the payload
// is pinned unchanged. Mock style: ActivityModal.objectivePrefill.test.jsx.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

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
  createActivity: vi.fn(async () => ({ success: true, data: {} })),
  createActivityWithEntities: vi.fn(async () => ({ success: true, data: {} })),
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

// The inline contact sub-form is replaced by a one-click save — the modal's
// own submit logic stays real.
vi.mock("sections/accounts/activities/components", async (importOriginal) => ({
  ...(await importOriginal()),
  InlineContactForm: ({ onSave }) => (
    <button type="button" onClick={() => onSave({ first_name: "Isabelle", last_name: "Roux" })}>
      save inline contact
    </button>
  ),
}));

import ActivityModal from "sections/accounts/activities/ActivityModal";
import { createActivity, createActivityWithEntities } from "api/accounts/activities";

const NEXT_STEP = {
  id: "ns1",
  suggested_title: "Meet the CFO",
  suggested_activity_type: "MEETING",
  suggested_objective: "Validate the budget",
  suggested_due_date: "2026-11-20",
  suggested_contacts: [{ id: "c1" }],
};

// The payload the modal sends for NEXT_STEP, without previous_activity_id.
const EXPECTED_ACTIVITY_PAYLOAD = {
  title: "Meet the CFO",
  activity_type: "MEETING",
  status: "PLANNED",
  description: null,
  call_to_action: "Validate the budget",
  scheduled_date: "2026-11-20",
  scheduled_time: null,
  due_date: null,
  contact_ids: ["c1"],
  account_id: "acc1",
  decision_cycle_id: null,
  decision_step_id: null,
  next_step_signal_id: "ns1",
};

function renderModal() {
  render(
    <ActivityModal
      open
      onClose={() => {}}
      accountId="acc1"
      activity={null}
      previousActivityId="prev1"
      nextStepSignal={NEXT_STEP}
    />,
  );
}

// The MUI Modal marks its content aria-hidden in jsdom: query with hidden.
function clickButton(name) {
  fireEvent.click(screen.getByRole("button", { name, hidden: true }));
}

function submit() {
  clickButton("Create");
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ActivityModal — create payload (bug (e): no previous_activity_id)", () => {
  it("standard creation sends no previous_activity_id, the rest unchanged", async () => {
    renderModal();
    submit();

    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    const payload = createActivity.mock.calls[0][0];
    expect(payload).not.toHaveProperty("previous_activity_id");
    expect(payload).toEqual(EXPECTED_ACTIVITY_PAYLOAD);
  });

  it("create-with-entities sends no previous_activity_id, the rest unchanged", async () => {
    renderModal();
    // The icon's aria-label ("plus") is part of the accessible name.
    clickButton(/add new contact/i);
    clickButton("save inline contact");
    submit();

    await waitFor(() => expect(createActivityWithEntities).toHaveBeenCalledTimes(1));
    const body = createActivityWithEntities.mock.calls[0][0];
    expect(body.activity).not.toHaveProperty("previous_activity_id");
    expect(body).toEqual({
      activity: EXPECTED_ACTIVITY_PAYLOAD,
      inline_contact: { first_name: "Isabelle", last_name: "Roux" },
      inline_cycle: null,
      inline_step_stage: null,
    });
  });
});

// Sprint Next steps 2.2a (R3): a next step's long objective is converted
// whole — no 500-character cap on the Objective any more.
describe("ActivityModal — objective longer than 500 characters", () => {
  it("converts a next step whose objective exceeds 500 characters, whole", async () => {
    const longObjective = "Valider le budget 2027 avec la DAF et le contrôleur de gestion. ".repeat(12).trim();
    expect(longObjective.length).toBeGreaterThan(500);
    render(
      <ActivityModal
        open
        onClose={() => {}}
        accountId="acc1"
        activity={null}
        nextStepSignal={{ ...NEXT_STEP, suggested_objective: longObjective }}
      />,
    );
    submit();

    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0].call_to_action).toBe(longObjective);
  });
});
