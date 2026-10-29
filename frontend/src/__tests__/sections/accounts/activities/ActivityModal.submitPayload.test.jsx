// frontend/src/__tests__/sections/accounts/activities/ActivityModal.submitPayload.test.jsx
//
// Bug (e) — the create payload must not carry `previous_activity_id`: the
// Activity.previous_activity / next_activity fields were dropped (backend
// migration activities 0016) and the create serializers no longer know them.
// Real render + real submit of ActivityModal on BOTH create paths (standard
// POST /module-activities/ and create-with-entities); the rest of the payload
// is pinned unchanged. Mock style: ActivityModal.objectivePrefill.test.jsx.
// 5.13.4: the dead `previousActivityId` prop is removed too (grep: no
// consumer); the payload still carries no previous_activity_id.

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

// The steps of the selected cycle — set per test (Sprint Next steps 2.2b).
const cycleSteps = vi.hoisted(() => ({ list: [] }));

// The real module's constants (PIPELINE_STEPS_ORDER / PIPELINE_STEP_LABELS —
// the inline cycle form's steps, 5.13).
vi.mock("api/accounts/decisionCycles", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetDecisionCyclesByAccount: () => ({ cycles: [], cyclesLoading: false }),
  useGetDecisionStepsByCycle: (cycleId) => ({
    steps: cycleId ? cycleSteps.list : [],
    stepsLoading: false,
  }),
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
import AphoriqTheme from "../../../_utils/aphoriqTheme";
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

function renderModal({ themed = false } = {}) {
  const modal = (
    <ActivityModal
      open
      onClose={() => {}}
      accountId="acc1"
      activity={null}
      nextStepSignal={NEXT_STEP}
    />
  );
  // The shared pills (StatusPill) read the aphoriQ theme, as in the app.
  render(themed ? <AphoriqTheme>{modal}</AphoriqTheme> : modal);
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
  cycleSteps.list = [];
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

// Sprint Next steps 2.2b — the conversion pre-fills the form from the next
// step (mirror of the backend defaults, activities/constants.py ↔
// utils/activityTypes.js); everything stays editable.
describe("ActivityModal — the shared pre-fill, names cited (5.8d)", () => {
  function renderConversion(nextStep) {
    render(
      <ActivityModal open onClose={() => {}} accountId="acc1" activity={null}
        nextStepSignal={{ ...NEXT_STEP, ...nextStep }} />,
    );
  }

  it("a TASK next step: the names cited and the internal names go to the description", async () => {
    renderConversion({
      suggested_activity_type: "TASK", suggested_topics: "DPA",
      suggested_people_names: ["Laurent", "Marc"], suggested_internal_names: ["Sophie"],
    });
    submit();
    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0].description).toBe(
      "DPA\n\nMentioned: Laurent, Marc\n\nInternal: Sophie");
  });

  it("a MEETING next step: the internal names go to the description, not the names cited", async () => {
    renderConversion({
      suggested_topics: "DPA", suggested_people_names: ["Laurent"],
      suggested_internal_names: ["Sophie"],
    });
    submit();
    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0].description).toBe("DPA\n\nInternal: Sophie");
  });
});

describe("ActivityModal — conversion pre-fill from the next step", () => {
  function renderConversion(nextStep, props = {}) {
    render(
      <ActivityModal
        open
        onClose={() => {}}
        accountId="acc1"
        activity={null}
        nextStepSignal={{ ...NEXT_STEP, ...nextStep }}
        {...props}
      />,
    );
  }

  it("D6: an EMAIL / TASK next step date is a due date, not a scheduled date (bug c)", async () => {
    renderConversion({ suggested_activity_type: "EMAIL", suggested_due_date: "2026-10-23" });
    submit();

    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    const payload = createActivity.mock.calls[0][0];
    expect(payload.due_date).toBe("2026-10-23");
    expect(payload.scheduled_date).toBeNull();
  });

  it("objective + success criterion → Objective, topics → Description", async () => {
    renderConversion({
      suggested_objective: "Lever le blocage sécurité",
      suggested_success_criterion: "Le DSI valide l'hébergement",
      suggested_topics: "Hébergement UE, DPA, SOC 2",
    });
    submit();

    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    const payload = createActivity.mock.calls[0][0];
    expect(payload.call_to_action).toBe(
      "Lever le blocage sécurité\n\nSuccess criterion: Le DSI valide l'hébergement",
    );
    expect(payload.description).toBe("Hébergement UE, DPA, SOC 2");
  });

  it("contacts: the contacts of the next step's People are pre-selected", async () => {
    renderConversion({
      suggested_contacts: [{ id: "c1" }],
      suggested_people: [
        { id: "p1", full_name: "Laurent Petit", target_contact: { id: "c2" } },
        { id: "p2", full_name: "la DAF", target_contact: null },
        { id: "p3", full_name: "Thomas", target_contact: { id: "c1" } },
      ],
    });
    submit();

    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0].contact_ids).toEqual(["c1", "c2"]);
  });

  it("DC step: the proposed step is pre-selected when it is a step of the cycle", async () => {
    cycleSteps.list = [
      { id: "s1", name: "Step 1", is_current: false },
      { id: "s2", name: "Step 2", is_current: true },
      { id: "s3", name: "Step 3", is_current: false },
    ];
    renderConversion({ suggested_decision_step: "s3" }, { decisionCycleId: "dc1" });

    await waitFor(() => {
      submit();
      expect(createActivity).toHaveBeenCalledTimes(1);
    });
    expect(createActivity.mock.calls[0][0].decision_step_id).toBe("s3");
  });

  it("DC step: without a usable proposal the cycle's current step is pre-selected", async () => {
    cycleSteps.list = [
      { id: "s1", name: "Step 1", is_current: false },
      { id: "s2", name: "Step 2", is_current: true },
    ];
    renderConversion({ suggested_decision_step: "other-cycle-step" }, { decisionCycleId: "dc1" });

    await waitFor(() => {
      submit();
      expect(createActivity).toHaveBeenCalledTimes(1);
    });
    expect(createActivity.mock.calls[0][0].decision_step_id).toBe("s2");
  });

  it("Description longer than 2000 characters is converted whole (no cap)", async () => {
    const longTopics = "Hébergement UE, DPA, SOC 2, réversibilité, localisation des sauvegardes. ".repeat(40).trim();
    expect(longTopics.length).toBeGreaterThan(2000);
    renderConversion({ suggested_topics: longTopics });
    submit();

    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0].description).toBe(longTopics);
  });
});

// 5.13 — ONE inline cycle form for the ActivityModal and the creation drawer:
// the starting step in pills (the 5 steps the backend creates, the shared
// constant), and the modal's « Starting at » reads the shared labels.
describe("ActivityModal — the inline cycle form is the shared one (5.13)", () => {
  it("the starting step in pills, then « Starting at: <label> » once created", async () => {
    renderModal({ themed: true });
    clickButton(/Create new cycle/);
    const pills = screen.getAllByTestId(/^stage-pill-/);
    expect(pills.map((p) => p.textContent)).toEqual([
      "Qualification", "Technical Fit", "Solution Validation", "Business Case", "Closing",
    ]);
    fireEvent.change(screen.getByPlaceholderText("Cycle name *"), { target: { value: "Deal Acme" } });
    fireEvent.click(screen.getByTestId("stage-pill-BUSINESS_CASE"));
    clickButton(/Create Cycle/);
    expect(await screen.findByText(/Starting at:/)).toHaveTextContent("Starting at: Business Case");
  });
});
