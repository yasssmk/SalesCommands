// frontend/src/__tests__/nextSteps/ActivityCreateConversion.test.jsx
//
// Sprint Next steps 5.13 — "Start Decision Cycle" moves from the ActivityModal
// to the creation drawer (EditActivityContent, create mode).
//   13.1 — the drawer accepts `sourceActivityId` and sends it as
//          source_activity_id on BOTH creation paths (createActivity, and
//          createActivityWithEntities when something is created inline) —
//          what the ActivityModal sent (ActivityModal.jsx: source_activity_id),
//          the link the backend reads to call the new cycle "born" from the
//          campaign activity (and to stamp its source_campaign).
//   13.2 — the drawer's CONVERSION mode (PO): the cycle is ALWAYS a NEW one
//          (inline_cycle — the only way the backend stamps source_campaign,
//          the DECISION_CYCLES objective), never an existing one; the
//          InlineCycleForm in pills (name + the starting step, the 5 steps the
//          backend creates — PIPELINE_STEPS_CONFIG — read from the ONE front
//          constant, api/accounts/decisionCycles); the campaign activity's
//          contact pre-filled; Save disabled while the cycle is not set.
// The drawer, InlineCycleForm and the coque are REAL; the API calls and data
// hooks are mocked.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/activities/act-1",
}));
// A DatePicker that hands its typed value to the form (a dayjs date).
vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: ({ label, onChange }) => {
    const dayjs = require("dayjs");
    return <input aria-label={label} onChange={(e) => onChange(dayjs(e.target.value))} />;
  },
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));
vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  createActivity: vi.fn(async () => ({ success: true, data: { id: "act-new" } })),
  createActivityWithEntities: vi.fn(async () => ({ success: true, data: { id: "act-new" } })),
}));
vi.mock("api/accounts/decisionCycles", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetDecisionCyclesByAccount: vi.fn(() => ({ cycles: [], cyclesLoading: false })),
  useGetDecisionStepsByCycle: vi.fn(() => ({ steps: [], stepsLoading: false })),
}));
vi.mock("api/signals/signals", async (importOriginal) => ({
  ...(await importOriginal()),
  useNextStepCitedContacts: vi.fn(() => ({ citedContacts: mockCited, citedLoading: false })),
}));
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" }, tenantId: "t-1" }),
  default: () => ({ user: { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" }, tenantId: "t-1" }),
}));
// The inline contact sub-form → a one-click save (as in the band tests).
vi.mock("sections/accounts/activities/components", async (importOriginal) => ({
  ...(await importOriginal()),
  InlineContactForm: ({ onSave }) => (
    <button type="button" onClick={() => onSave({ first_name: "Isabelle", last_name: "Roux" })}>
      save inline contact
    </button>
  ),
}));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn() }));

import { createActivity, createActivityWithEntities } from "api/accounts/activities";
import EditActivityContent from "sections/activities/workspace/EditActivityContent";

let mockCited = [];
const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", job_title: "CTO" };

// A next step pre-fills a valid form (title, date, the cited contact).
const NEXT_STEP = {
  id: "ns-1", status: "PENDING", suggested_title: "Discovery meeting",
  suggested_activity_type: "MEETING", suggested_due_date: "2026-11-12",
};

const renderDrawer = (props = {}) =>
  render(
    <WorkspaceCoque>
      <EditActivityContent mode="create" accountId="acc-1" nextStep={NEXT_STEP} {...props} />
    </WorkspaceCoque>,
  );
const saveButton = () => screen.getByRole("button", { name: "Save" });

beforeEach(() => { mockCited = [{ name: "Thomas Lefèvre", contact: THOMAS }]; });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("13.1 — the creation drawer sends source_activity_id", () => {
  it("createActivity: the payload carries source_activity_id", async () => {
    renderDrawer({ sourceActivityId: "act-camp" });
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0].source_activity_id).toBe("act-camp");
  });

  it("createActivityWithEntities (a contact created inline): the activity carries source_activity_id", async () => {
    renderDrawer({ sourceActivityId: "act-camp" });
    fireEvent.click(within(screen.getByTestId("activity-create")).getByTestId("add-inline-contact"));
    fireEvent.click(screen.getByRole("button", { name: "save inline contact" }));
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivityWithEntities).toHaveBeenCalledTimes(1));
    expect(createActivityWithEntities.mock.calls[0][0].activity.source_activity_id).toBe("act-camp");
  });

  it("without sourceActivityId: no source_activity_id key (the payload as before)", async () => {
    renderDrawer();
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0]).not.toHaveProperty("source_activity_id");
  });
});

// ==============================|| 13.2 — THE CONVERSION MODE ||============================== //

describe("13.2 — conversion mode: a NEW cycle only, the contact pre-filled", () => {
  // No next step here: nothing cited — the contact can only come from
  // initialContacts (the campaign activity's).
  beforeEach(() => { mockCited = []; });
  const STEP_LABELS = ["Qualification", "Technical Fit", "Solution Validation", "Business Case", "Closing"];

  const renderConversion = (props = {}) =>
    render(
      <WorkspaceCoque>
        <EditActivityContent
          mode="create"
          conversion
          accountId="acc-1"
          activityType="MEETING"
          sourceActivityId="act-camp"
          initialContacts={[THOMAS]}
          {...props}
        />
      </WorkspaceCoque>,
    );
  const drawer = () => screen.getByTestId("activity-create");
  const cycleZone = () => within(drawer()).getByTestId("conversion-cycle");
  const fillTitleAndDate = () => {
    fireEvent.click(within(drawer()).getByTestId("inline-read-title"));
    fireEvent.change(within(drawer()).getByTestId("inline-input-title"), { target: { value: "Discovery meeting" } });
    fireEvent.click(within(drawer()).getByTestId("inline-read-date"));
    fireEvent.change(screen.getByLabelText("Scheduled date"), { target: { value: "2026-11-12" } });
    fireEvent.click(screen.getByTestId("date-confirm"));
  };
  const createCycle = (name = "Deal Acme", stage = "Technical Fit") => {
    fireEvent.change(within(cycleZone()).getByPlaceholderText("Cycle name *"), { target: { value: name } });
    fireEvent.click(within(cycleZone()).getByRole("button", { name: stage }));
    fireEvent.click(within(cycleZone()).getByRole("button", { name: /Create Cycle/ }));
  };

  it("no existing cycle to pick: the new-cycle form is shown instead", () => {
    renderConversion();
    expect(within(drawer()).queryByTestId("inline-read-decision_cycle")).toBeNull();
    expect(within(cycleZone()).getByPlaceholderText("Cycle name *")).toBeInTheDocument();
  });

  it("the starting step in PILLS: the 5 steps the backend creates, in order, Qualification chosen", () => {
    renderConversion();
    const pills = within(cycleZone()).getAllByTestId(/^stage-pill-/);
    expect(pills.map((p) => p.textContent)).toEqual(STEP_LABELS);
    pills.forEach((p) => expect(p).toHaveAttribute("data-testid", expect.stringMatching(/^stage-pill-/)));
    expect(within(cycleZone()).getByRole("button", { name: "Qualification" })).toHaveAttribute("aria-pressed", "true");
    expect(within(cycleZone()).queryByRole("combobox")).toBeNull();
    fireEvent.click(within(cycleZone()).getByRole("button", { name: "Business Case" }));
    expect(within(cycleZone()).getByRole("button", { name: "Business Case" })).toHaveAttribute("aria-pressed", "true");
    expect(within(cycleZone()).getByRole("button", { name: "Qualification" })).toHaveAttribute("aria-pressed", "false");
  });

  it("the campaign activity's contact is pre-filled", () => {
    renderConversion();
    expect(within(drawer()).getByText("Thomas Lefèvre")).toBeInTheDocument();
  });

  it("Save disabled while the cycle is not set; enabled once created", async () => {
    renderConversion();
    fillTitleAndDate();
    await waitFor(() => expect(saveButton()).toBeDisabled());
    createCycle();
    await waitFor(() => expect(saveButton()).toBeEnabled());
  });

  it("the new cycle reads « name · new cycle · step », removable (back to the form, Save disabled)", async () => {
    renderConversion();
    fillTitleAndDate();
    createCycle();
    const row = (await within(cycleZone()).findByText("Deal Acme")).closest("p");
    expect(row.textContent).toBe("Deal Acme · new cycle · Technical Fit");
    fireEvent.click(within(cycleZone()).getByTestId("remove-inline-cycle"));
    expect(within(cycleZone()).getByPlaceholderText("Cycle name *")).toBeInTheDocument();
    await waitFor(() => expect(saveButton()).toBeDisabled());
  });

  it("the EXACT payload: create-with-entities, inline_cycle + inline_step_stage + source_activity_id", async () => {
    renderConversion();
    fillTitleAndDate();
    createCycle();
    await waitFor(() => expect(saveButton()).toBeEnabled());
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivityWithEntities).toHaveBeenCalledTimes(1));
    expect(createActivityWithEntities.mock.calls[0][0]).toEqual({
      activity: {
        title: "Discovery meeting",
        activity_type: "MEETING",
        status: "PLANNED",
        description: null,
        call_to_action: null,
        scheduled_date: "2026-11-12",
        scheduled_time: null,
        due_date: null,
        contact_ids: ["c-1"],
        invited_user_ids: [],
        account_id: "acc-1",
        decision_cycle_id: null,
        decision_step_id: null,
        source_activity_id: "act-camp",
      },
      inline_contact: null,
      inline_cycle: { name: "Deal Acme" },
      inline_step_stage: "TECHNICAL_FIT",
    });
    expect(createActivity).not.toHaveBeenCalled();
  });

  it("outside the conversion: the existing-cycle picker as before", () => {
    renderDrawer();
    expect(within(drawer()).getByTestId("inline-read-decision_cycle")).toBeInTheDocument();
    expect(within(drawer()).queryByTestId("conversion-cycle")).toBeNull();
  });
});
