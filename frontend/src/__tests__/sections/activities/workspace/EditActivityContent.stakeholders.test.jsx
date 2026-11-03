// frontend/src/__tests__/sections/activities/workspace/EditActivityContent.stakeholders.test.jsx
//
// Sprint « Cycle de vie des contacts », étape 7 (3) — the Edit activity drawer
// (create AND edit), section People: ONE « Stakeholders » list = the account
// contacts + the NON-converted stakeholders of the activity's DC (as they
// are), each marked « Contact » / « Not yet a contact »; the internal team
// stays in the section.
//   - PEOPLE_ACTIVITY_TYPES (MEETING / CALL / EMAIL / DEMO, mirror of the
//     backend): at least one participant (a contact, a stakeholder, the inline
//     contact); the other types: no minimum.
//   - The payload carries contact_ids AND stakeholder_ids.
//   - A next step (DEMO included) pre-fills its cited names as participants:
//     the matched contacts AND the matched non-converted stakeholders; the
//     other names stay « Mentioned ».
// The REAL EditActivityContent; the API hooks / calls and the pickers mocked.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, within, waitFor } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

const DC = "44444444-4444-4444-8444-444444444444";
const STEP = "55555555-5555-4555-8555-555555555555";
const JANE = { id: "c-jane", first_name: "Jane", last_name: "Doe", full_name: "Jane Doe",
               department_name: "Sales", is_reachable: true };
const MARC = { id: "st-marc", display_name: "Marc", full_name: "Marc", department: null,
               is_linked: false, decision_cycle: DC };
const FINANCE = { id: "st-fin", display_name: "Finance", full_name: "", is_linked: false,
                  department: { id: 7, name: "Finance" }, decision_cycle: DC };

let mockStakeholders = [MARC, FINANCE];
let mockCited = [];

vi.mock("@mui/x-date-pickers/DatePicker", async () => {
  const { default: dayjs } = await import("dayjs");
  return {
    DatePicker: (props) => (
      <button type="button" data-testid={`pick-${props.label}`}
              onClick={() => props.onChange(dayjs("2026-12-15"))}>
        pick
      </button>
    ),
  };
});
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => null }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer: vi.fn(), openDrawer: vi.fn() }),
}));
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u-1", first_name: "Ann", last_name: "Owner" }, tenantId: "t-1" }),
  default: () => ({ user: { id: "u-1", first_name: "Ann", last_name: "Owner" }, tenantId: "t-1" }),
}));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn() }));
vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  createActivity: vi.fn(async () => ({ success: true, data: { id: "act-new" } })),
  createActivityWithEntities: vi.fn(async () => ({ success: true, data: { id: "act-new" } })),
  updateActivity: vi.fn(async () => ({ success: true, data: {} })),
}));
vi.mock("api/accounts/decisionCycles", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetDecisionCyclesByAccount: () => ({ cycles: [{ id: DC, name: "Deal Acme" }], cyclesLoading: false }),
  useGetDecisionStepsByCycle: () => ({ steps: [{ id: STEP, name: "Qualification", order: 1, is_current: true }],
                                       stepsLoading: false }),
  useGetDCStakeholders: (cycleId) => ({
    stakeholders: cycleId ? mockStakeholders : [], stakeholdersLoading: false,
  }),
}));
vi.mock("api/signals/signals", async (importOriginal) => ({
  ...(await importOriginal()),
  useNextStepCitedContacts: () => ({ citedContacts: mockCited, citedLoading: false }),
}));
vi.mock("components/AsyncSelection/AsyncUserSelect", () => ({ default: () => null }));
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: ({ onChange }) => (
    <button type="button" data-testid="pick-contact" onClick={(e) => onChange(e, JANE)}>
      pick Jane
    </button>
  ),
}));

import EditActivityContent from "sections/activities/workspace/EditActivityContent";
import { createActivity, updateActivity } from "api/accounts/activities";

const renderCreate = (props = {}) =>
  render(
    <AphoriqTheme>
      <EditActivityContent mode="create" accountId="acc-1" decisionCycleId={DC}
                           activityType="MEETING" {...props} />
    </AphoriqTheme>,
  );

const people = () => screen.getByTestId("people-section");
const pickDate = () => {
  // The required title, then the date (it reads as a value; a click opens the
  // editor, ✓ keeps the draft).
  fireEvent.click(screen.getByTestId("inline-read-title"));
  fireEvent.change(screen.getByTestId("inline-input-title"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByTestId("inline-read-date"));
  fireEvent.click(screen.getByTestId("pick-Scheduled date"));
  fireEvent.click(screen.getByTestId("date-confirm"));
};
const save = async () => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
  });
};
const addStakeholder = (label) => {
  fireEvent.click(screen.getByTestId("add-stakeholder"));
  const input = within(screen.getByTestId("stakeholder-select")).getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.click(screen.getByRole("option", { name: label }));
};

beforeEach(() => {
  mockStakeholders = [MARC, FINANCE];
  mockCited = [];
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("Edit activity — ONE « Stakeholders » list (étape 7)", () => {
  it("the participants list is captioned « Stakeholders »", () => {
    renderCreate();
    expect(within(people()).getByText("Stakeholders")).toBeInTheDocument();
    expect(within(people()).queryByText("External contacts")).toBeNull();
  });

  it("a MEETING without participant cannot be saved (the type has people)", async () => {
    renderCreate();
    pickDate();
    await save();
    expect(createActivity).not.toHaveBeenCalled();
    expect(await within(people()).findByText("At least one participant is required")).toBeInTheDocument();
  });

  it("a TASK without participant is saved (no minimum)", async () => {
    renderCreate({ activityType: "TASK" });
    pickDate();
    await save();
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0]).toMatchObject({ contact_ids: [], stakeholder_ids: [] });
  });

  it("a not-yet-contact stakeholder of the DC is a participant, marked so, sent as stakeholder_ids", async () => {
    renderCreate();
    pickDate();
    addStakeholder("Marc");
    const row = within(people()).getByTestId("participant-st-marc");
    expect(row).toHaveTextContent("Marc");
    expect(row).toHaveTextContent("Not yet a contact");
    await save();
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0]).toMatchObject({ contact_ids: [], stakeholder_ids: ["st-marc"] });
  });

  it("a department-only stakeholder shows its department", () => {
    renderCreate();
    addStakeholder("Finance");
    expect(within(people()).getByTestId("participant-st-fin")).toHaveTextContent("Finance");
  });

  it("a contact is marked « Contact »", () => {
    renderCreate();
    fireEvent.click(screen.getByTestId("add-contact"));
    fireEvent.click(screen.getByTestId("pick-contact"));
    expect(within(people()).getByTestId("participant-c-jane")).toHaveTextContent("Contact");
  });

  it("without a DC, no stakeholder can be added", () => {
    renderCreate({ decisionCycleId: undefined });
    expect(screen.queryByTestId("add-stakeholder")).toBeNull();
  });
});

describe("Next step → DEMO: the cited names pre-fill the participants (étape 7)", () => {
  it("matched contacts AND matched stakeholders join; the others stay Mentioned", async () => {
    mockCited = [
      { name: "Jane Doe", contact: JANE, stakeholder: null },
      { name: "Marc", contact: null, stakeholder: MARC },
      { name: "Zed", contact: null, stakeholder: null },
    ];
    renderCreate({
      activityType: "DEMO",
      nextStep: { id: "ns-1", suggested_title: "Demo", suggested_activity_type: "DEMO",
                  suggested_people: [], suggested_people_names: ["Jane Doe", "Marc", "Zed"],
                  suggested_due_date: "2026-12-10" },
    });
    expect(within(people()).getByTestId("participant-c-jane")).toBeInTheDocument();
    expect(within(people()).getByTestId("participant-st-marc")).toBeInTheDocument();
    expect(within(people()).getByTestId("mentioned-names")).toHaveTextContent("Mentioned: Zed");
    await save();
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0]).toMatchObject({
      contact_ids: ["c-jane"], stakeholder_ids: ["st-marc"],
    });
    expect(createActivity.mock.calls[0][0].description || "").not.toMatch(/Mentioned:/);
  });
});

describe("Edit mode — the same list (étape 7)", () => {
  const ACTIVITY = {
    id: "act-1", title: "Workshop", activity_type: "MEETING", status: "PLANNED",
    scheduled_date: "2026-12-01", account: "acc-1", decision_cycle: DC,
    owner_detail: { id: "u-1", first_name: "Ann", last_name: "Owner" }, invited_users_detail: [],
    contacts_detail: [JANE], stakeholders_detail: [MARC], campaign_detail: null,
  };
  const renderEdit = (over = {}) =>
    render(<AphoriqTheme><EditActivityContent activity={{ ...ACTIVITY, ...over }} /></AphoriqTheme>);

  it("shows the contacts and the stakeholders, and sends both lists", async () => {
    renderEdit();
    expect(within(people()).getByTestId("participant-c-jane")).toHaveTextContent("Contact");
    expect(within(people()).getByTestId("participant-st-marc")).toHaveTextContent("Not yet a contact");
    fireEvent.click(within(people()).getByTestId("remove-contact-c-jane"));
    await save();
    await waitFor(() => expect(updateActivity).toHaveBeenCalled());
    expect(updateActivity.mock.calls[0][1]).toMatchObject({ contact_ids: [], stakeholder_ids: ["st-marc"] });
  });

  it("removing every participant of a MEETING is refused", async () => {
    renderEdit();
    fireEvent.click(within(people()).getByTestId("remove-contact-c-jane"));
    fireEvent.click(within(people()).getByTestId("remove-stakeholder-st-marc"));
    await save();
    expect(updateActivity).not.toHaveBeenCalled();
    expect(await within(people()).findByText("At least one participant is required")).toBeInTheDocument();
  });
});
