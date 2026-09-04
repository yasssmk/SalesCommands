// frontend/src/__tests__/sections/activities/workspace/EditContactContent.test.jsx
//
// CT-3 — the Contact EDIT drawer, cloned from EditActivityContent: Formik +
// DrawerContentLayout (global Save/Cancel) + InlineEditableValue (double-click
// to edit). Identity + coordinates + department (a bounded select). Save PATCHes
// via updateContact; first/last are required; the payload never carries
// account_id and trims phone/linkedin.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

const { closeDrawer, updateContact, createSignal, displaySuccessSnackbar, displayErrorSnackbar } =
  vi.hoisted(() => ({
    closeDrawer: vi.fn(),
    updateContact: vi.fn(() => Promise.resolve({ success: true, data: {} })),
    createSignal: vi.fn(() => Promise.resolve({ success: true, data: {} })),
    displaySuccessSnackbar: vi.fn(),
    displayErrorSnackbar: vi.fn(),
  }));

vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ isOpen: true, content: null, openDrawer: vi.fn(), closeDrawer }),
}));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar, displayErrorSnackbar }));

const useGetContact = vi.fn();
const useGetContactChoices = vi.fn();
const useGetDCPeople = vi.fn();
const mutatePeople = vi.fn();
vi.mock("api/businessData/contacts", () => ({
  useGetContact: (...a) => useGetContact(...a),
  useGetContactChoices: (...a) => useGetContactChoices(...a),
  updateContact: (...a) => updateContact(...a),
}));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDCPeople: (...a) => useGetDCPeople(...a),
}));
vi.mock("api/signals/signals", () => ({
  createSignal: (...a) => createSignal(...a),
}));

import ThemeCustomization from "themes/index";
import EditContactContent from "sections/activities/workspace/EditContactContent";

const CONTACT = {
  id: "c1",
  first_name: "Chevalier",
  last_name: "Iki",
  job_title: "Head of HR",
  standard_department: { id: "d1", name: "Sales" },
  email: "iki@rr.com",
  phone_number: "+33124354657",
  linkedin: "https://linkedin.com/in/iki",
};

const DEPARTMENTS = [
  { value: "d1", label: "Sales" },
  { value: "d2", label: "Marketing" },
];

function mockContact(contact = CONTACT) {
  useGetContact.mockReturnValue({
    contact,
    contactLoading: false,
    contactError: null,
    contactValidating: false,
  });
}
function mockChoices(depts = DEPARTMENTS) {
  useGetContactChoices.mockReturnValue({
    influenceLevels: [],
    standardDepartments: depts,
    choicesLoading: false,
    choicesError: null,
  });
}
function mockDCPeople(peopleObj = { qualified: [], unqualified: [] }) {
  useGetDCPeople.mockReturnValue({
    people: peopleObj,
    peopleLoading: false,
    peopleError: null,
    mutatePeople,
  });
}

const DC_ACTIVITY = { id: "a1", decision_cycle: "dc-1", account: "acc-1" };

function renderEdit(props = {}) {
  return render(
    <ThemeCustomization>
      <EditContactContent contactId="c1" {...props} />
    </ThemeCustomization>,
  );
}

function editField(name, value) {
  fireEvent.doubleClick(screen.getByTestId(`inline-read-${name}`));
  const input = screen.getByTestId(`inline-input-${name}`);
  fireEvent.change(input, { target: { value } });
  return input;
}

beforeEach(() => {
  vi.clearAllMocks();
  updateContact.mockResolvedValue({ success: true, data: {} });
  createSignal.mockResolvedValue({ success: true, data: {} });
  mockContact();
  mockChoices();
  mockDCPeople();
});

describe("EditContactContent — fields", () => {
  it("pre-fills identity + coordinates + department (label), the right set of fields", () => {
    renderEdit();
    expect(screen.getByTestId("inline-read-first_name")).toHaveTextContent("Chevalier");
    expect(screen.getByTestId("inline-read-last_name")).toHaveTextContent("Iki");
    expect(screen.getByTestId("inline-read-job_title")).toHaveTextContent("Head of HR");
    // department is a select showing the LABEL of the pre-filled id
    expect(screen.getByTestId("inline-read-standard_department_id")).toHaveTextContent("Sales");
    expect(screen.getByTestId("inline-read-email")).toHaveTextContent("iki@rr.com");
    expect(screen.getByTestId("inline-read-phone_number")).toHaveTextContent("+33124354657");
    expect(screen.getByTestId("inline-read-linkedin")).toHaveTextContent(/linkedin/i);
    // V0 excludes influence_level and the free-text department
    expect(screen.queryByTestId("inline-read-influence_level")).not.toBeInTheDocument();
    expect(screen.queryByTestId("inline-read-department")).not.toBeInTheDocument();
  });

  it("edits a field on double-click (input appears)", () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-job_title"));
    expect(screen.getByTestId("inline-input-job_title")).toBeInTheDocument();
  });

  it("edits the department as a select (combobox) carrying the department options", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-standard_department_id"));
    // A MUI select renders a combobox (a text field would be a plain textbox).
    const combobox = screen.getByRole("combobox");
    expect(combobox).toBeInTheDocument();
    fireEvent.mouseDown(combobox);
    expect(await screen.findByRole("option", { name: "Sales" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Marketing" })).toBeInTheDocument();
  });
});

describe("EditContactContent — validation", () => {
  it("blocks Save when a required name is cleared, re-enables when valid", async () => {
    renderEdit();
    // enter edit mode once; keep changing the SAME input (it stays in edit mode).
    const input = editField("first_name", "");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /save/i })).toBeDisabled(),
    );
    fireEvent.change(input, { target: { value: "Chevalière" } });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /save/i })).not.toBeDisabled(),
    );
  });
});

describe("EditContactContent — save", () => {
  it("PATCHes via updateContact with the field set, no account_id, phone/linkedin trimmed", async () => {
    renderEdit();
    editField("job_title", "Head of Sales");
    editField("phone_number", "  +33 99  ");
    editField("linkedin", "  https://li/x  ");
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(updateContact).toHaveBeenCalledTimes(1));
    const [id, payload] = updateContact.mock.calls[0];
    expect(id).toBe("c1");
    expect(payload).toMatchObject({
      first_name: "Chevalier",
      last_name: "Iki",
      job_title: "Head of Sales",
      standard_department_id: "d1",
      email: "iki@rr.com",
      phone_number: "+33 99",
      linkedin: "https://li/x",
    });
    expect(payload).not.toHaveProperty("account_id");
  });

  it("sends empty string coordinates (never null) so a contact saves without them", async () => {
    // The write serializer accepts "" (allow_blank) but rejects null
    // ("may not be null") for email/phone/linkedin. Empty coords must go as "".
    renderEdit();
    editField("email", "");
    editField("phone_number", "");
    editField("linkedin", "");
    editField("job_title", "");
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(updateContact).toHaveBeenCalledTimes(1));
    const payload = updateContact.mock.calls[0][1];
    expect(payload.email).toBe("");
    expect(payload.phone_number).toBe("");
    expect(payload.linkedin).toBe("");
    expect(payload.job_title).toBe("");
    // none of the string coords is null
    expect(payload.email).not.toBeNull();
    expect(payload.phone_number).not.toBeNull();
    expect(payload.linkedin).not.toBeNull();
    // the department FK still clears with null (allow_null on the FK)
    expect(payload.standard_department_id).toBe("d1");
  });

  it("on success: success snackbar + closeDrawer + onSaved", async () => {
    const onSaved = vi.fn();
    renderEdit({ onSaved });
    editField("job_title", "Head of Sales");
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(displaySuccessSnackbar).toHaveBeenCalled());
    expect(onSaved).toHaveBeenCalled();
    expect(closeDrawer).toHaveBeenCalled();
  });

  it("on a duplicate-email error: shows the error, keeps the drawer open", async () => {
    updateContact.mockResolvedValueOnce({ success: false, error: "A contact with this email already exists" });
    renderEdit();
    editField("email", "dup@rr.com");
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(displayErrorSnackbar).toHaveBeenCalled());
    expect(closeDrawer).not.toHaveBeenCalled();
  });

  it("Cancel closes the drawer", () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(closeDrawer).toHaveBeenCalled();
  });
});

describe("EditContactContent — sections", () => {
  it("shows a 'Contact' section caption for the coordinates", () => {
    renderEdit();
    expect(screen.getByText("Contact")).toBeInTheDocument();
  });
});

describe("EditContactContent — role in the decision (DC only)", () => {
  const QUALIFIED = {
    target_contact: { id: "c1" },
    role: "CHAMPION",
    role_display: "Champion",
    influence: "HIGH",
    influence_display: "High",
    activity_count: 0,
  };

  it("is ABSENT outside a DC (no activity / decision_cycle)", () => {
    renderEdit(); // no activity
    expect(screen.queryByTestId("edit-contact-role-section")).not.toBeInTheDocument();
    expect(screen.queryByText("Role in the decision")).not.toBeInTheDocument();
  });

  it("is PRESENT inside a DC, pre-filled from the contact's qualified entry", () => {
    mockDCPeople({ qualified: [QUALIFIED], unqualified: [] });
    renderEdit({ activity: DC_ACTIVITY });
    expect(screen.getByTestId("edit-contact-role-section")).toBeInTheDocument();
    expect(screen.getByTestId("inline-read-role")).toHaveTextContent("Champion");
    expect(screen.getByTestId("inline-read-influence")).toHaveTextContent("High");
  });

  it("changing the role and saving writes a MANUAL people signal, then revalidates", async () => {
    mockDCPeople({ qualified: [QUALIFIED], unqualified: [] });
    renderEdit({ activity: DC_ACTIVITY });

    fireEvent.doubleClick(screen.getByTestId("inline-read-role"));
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(await screen.findByRole("option", { name: "Decision Maker" }));

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(updateContact).toHaveBeenCalledTimes(1));
    expect(createSignal).toHaveBeenCalledWith(
      "people",
      expect.objectContaining({
        role: "DECISION_MAKER",
        target_contact: "c1",
        account: "acc-1",
        source: "MANUAL",
        decision_cycle: "dc-1",
      }),
    );
    expect(mutatePeople).toHaveBeenCalled();
    expect(closeDrawer).toHaveBeenCalled();
  });

  it("does NOT write a people signal when the role is unchanged", async () => {
    mockDCPeople({ qualified: [QUALIFIED], unqualified: [] });
    renderEdit({ activity: DC_ACTIVITY });

    editField("job_title", "Head of Sales"); // change only a contact field
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(updateContact).toHaveBeenCalledTimes(1));
    expect(createSignal).not.toHaveBeenCalled();
    expect(closeDrawer).toHaveBeenCalled();
  });
});
