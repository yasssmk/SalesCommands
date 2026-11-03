// frontend/src/__tests__/sections/activities/workspace/EditActivityContent.stakeholders.test.jsx
//
// Sprint « Cycle de vie des contacts », étapes 7 / 7c — the Edit activity drawer
// (create AND edit), section People. PO (7c): at the ACTIVITY level the
// stakeholder / contact distinction does not show — no marker, no creation
// of a person from this drawer:
//   - ONE « Add stakeholder » button (no « Add contact », no « New contact »);
//   - its list (choice A): every stakeholder of the activity's DC (converted
//     or not) + the account contacts not yet stakeholders of it; without a
//     DC, the account contacts;
//   - the payload keeps the distinction INTERNAL: a contact or a converted
//     stakeholder -> contact_ids; a non-converted stakeholder -> stakeholder_ids;
//   - PEOPLE_ACTIVITY_TYPES: at least one participant; the other types none;
//   - a next step (DEMO included) pre-fills its cited names as participants.
// 7d-1: the picker IS the standard AsyncContactSelect (server search, 20 per
// page) — the account contacts + the NON-converted stakeholders of the DC,
// both searched on the server; a converted stakeholder only under its contact.
// The REAL EditActivityContent and AsyncContactSelect; the API hooks mocked.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, within, waitFor } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

const DC = "44444444-4444-4444-8444-444444444444";
const STEP = "55555555-5555-4555-8555-555555555555";
const JANE = { id: "c-jane", first_name: "Jane", last_name: "Doe", full_name: "Jane Doe",
               department_name: "Sales", is_reachable: true };
const ZOE = { id: "c-zoe", first_name: "Zoe", last_name: "Martin", full_name: "Zoe Martin",
              department_name: null, is_reachable: true };
const PAUL_C = { id: "c-paul", first_name: "Paul", last_name: "X", full_name: "Paul X",
                 department_name: null, is_reachable: true };
const MARC = { id: "st-marc", display_name: "Marc", full_name: "Marc", department: null,
               is_linked: false, contact: null, decision_cycle: DC };
const FINANCE = { id: "st-fin", display_name: "Finance", full_name: "", is_linked: false,
                  contact: null, department: { id: 7, name: "Finance" }, decision_cycle: DC };
const PAUL = { id: "st-paul", display_name: "Paul X", full_name: "", department: null,
               is_linked: true, contact: PAUL_C, decision_cycle: DC };

let mockStakeholders = [MARC, FINANCE, PAUL];
let mockContacts = [JANE, ZOE, PAUL_C];
// The hooks' calls are recorded: the picker must search the SERVER.
const mockContactsHook = vi.fn(() => ({ contacts: mockContacts, contactsLoading: false }));
const mockStakeholdersHook = vi.fn((cycleId) => ({
  stakeholders: cycleId ? mockStakeholders : [], stakeholdersLoading: false,
}));
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
  useGetDecisionStepsByCycle: () => ({
    steps: [{ id: STEP, name: "Qualification", order: 1, is_current: true }], stepsLoading: false,
  }),
  useGetDCStakeholders: (...args) => mockStakeholdersHook(...args),
}));
vi.mock("api/businessData/contacts", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetContacts: (...args) => mockContactsHook(...args),
}));
vi.mock("api/signals/signals", async (importOriginal) => ({
  ...(await importOriginal()),
  useNextStepCitedContacts: () => ({ citedContacts: mockCited, citedLoading: false }),
}));
vi.mock("components/AsyncSelection/AsyncUserSelect", () => ({ default: () => null }));

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
const fillRequired = () => {
  fireEvent.click(screen.getByTestId("inline-read-title"));
  fireEvent.change(screen.getByTestId("inline-input-title"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByTestId("inline-read-date"));
  fireEvent.click(screen.getAllByTestId(/^pick-(Scheduled|Due) date$/)[0]);
  fireEvent.click(screen.getByTestId("date-confirm"));
};
const save = async () => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
  });
};
const openPicker = () => {
  fireEvent.click(screen.getByTestId("add-stakeholder"));
  const input = within(screen.getByTestId("stakeholder-select")).getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.keyDown(input, { key: "ArrowDown" });
};
const optionNames = () => screen.getAllByRole("option").map((o) => o.textContent);
const pick = (label) => {
  openPicker();
  fireEvent.click(screen.getByRole("option", { name: label }));
};

beforeEach(() => {
  mockStakeholders = [MARC, FINANCE, PAUL];
  mockContacts = [JANE, ZOE, PAUL_C];
  mockCited = [];
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("Edit activity — ONE « Add stakeholder », no distinction shown (7c)", () => {
  it("only « Add stakeholder »: no « Add contact », no « New contact »", () => {
    renderCreate();
    expect(within(people()).getByTestId("add-stakeholder")).toBeInTheDocument();
    expect(within(people()).queryByTestId("add-contact")).toBeNull();
    expect(within(people()).queryByTestId("add-inline-contact")).toBeNull();
    expect(within(people()).getByText("Stakeholders")).toBeInTheDocument();
  });

  it("the list (A): the DC's stakeholders (converted or not) + the account contacts not yet stakeholders", () => {
    renderCreate();
    openPicker();
    expect(optionNames().sort()).toEqual(["Finance", "Jane Doe", "Marc", "Paul X", "Zoe Martin"]);
  });

  it("a converted stakeholder is offered only under its contact (never as a stakeholder)", () => {
    mockContacts = [JANE];
    renderCreate();
    openPicker();
    expect(optionNames().sort()).toEqual(["Finance", "Jane Doe", "Marc"]);
  });

  it("the standard AsyncContactSelect: a server search on the contacts AND the DC's non-converted stakeholders", async () => {
    renderCreate();
    openPicker();
    const input = within(screen.getByTestId("stakeholder-select")).getByRole("combobox");
    fireEvent.change(input, { target: { value: "ma" } });
    await waitFor(() =>
      expect(mockContactsHook).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "ma", pageSize: 20, filters: { account_id: "acc-1" } }),
      ), { timeout: 2000 });
    expect(mockStakeholdersHook).toHaveBeenLastCalledWith(DC, { search: "ma", converted: false });
    // never the 100 contacts read of 7c
    expect(mockContactsHook.mock.calls.some(([o]) => o?.pageSize === 100)).toBe(false);
  });

  it("without a DC: the account contacts", () => {
    renderCreate({ decisionCycleId: undefined });
    openPicker();
    expect(optionNames().sort()).toEqual(["Jane Doe", "Paul X", "Zoe Martin"]);
  });

  it("no « Contact » / « Not yet a contact » marker", () => {
    renderCreate();
    pick("Marc");
    pick("Jane Doe");
    expect(people().textContent).not.toMatch(/Not yet a contact/);
    expect(within(people()).getByTestId("participant-c-jane").textContent).not.toMatch(/Contact/);
  });

  it("the payload keeps the distinction internal (contact / converted -> contact_ids; others -> stakeholder_ids)", async () => {
    renderCreate();
    fillRequired();
    pick("Marc");          // non-converted stakeholder
    pick("Paul X");        // converted stakeholder -> its contact
    pick("Jane Doe");      // account contact
    await save();
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.stakeholder_ids).toEqual(["st-marc"]);
    expect(body.contact_ids.sort()).toEqual(["c-jane", "c-paul"]);
  });

  it("a picked participant leaves the list", () => {
    renderCreate();
    pick("Paul X");
    openPicker();
    expect(optionNames()).not.toContain("Paul X");
  });

  it("a MEETING without participant cannot be saved", async () => {
    renderCreate();
    fillRequired();
    await save();
    expect(createActivity).not.toHaveBeenCalled();
    expect(await within(people()).findByText("At least one participant is required")).toBeInTheDocument();
  });

  it("a TASK without participant is saved", async () => {
    renderCreate({ activityType: "TASK", decisionCycleId: undefined });
    fillRequired();
    await save();
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0]).toMatchObject({ contact_ids: [], stakeholder_ids: [] });
  });
});

describe("Next step → DEMO: the cited names pre-fill the participants", () => {
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
  });
});

describe("Edit mode — the same list", () => {
  const ACTIVITY = {
    id: "act-1", title: "Workshop", activity_type: "MEETING", status: "PLANNED",
    scheduled_date: "2026-12-01", account: "acc-1", decision_cycle: DC,
    owner_detail: { id: "u-1", first_name: "Ann", last_name: "Owner" }, invited_users_detail: [],
    contacts_detail: [JANE], stakeholders_detail: [MARC], campaign_detail: null,
  };
  const renderEdit = (over = {}) =>
    render(<AphoriqTheme><EditActivityContent activity={{ ...ACTIVITY, ...over }} /></AphoriqTheme>);

  it("shows both, unmarked, no « Add contact », and sends both lists", async () => {
    renderEdit();
    expect(within(people()).queryByTestId("add-contact")).toBeNull();
    expect(people().textContent).not.toMatch(/Not yet a contact/);
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
