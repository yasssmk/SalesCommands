// frontend/src/__tests__/sections/activities/workspace/EditPeopleContent.test.jsx
//
// People S3 — the People EDIT drawer, a clone of EditObjectionContent on the
// standard chassis. Fields: contact (AsyncContactSelect, account-scoped,
// clearable) + full_name + department (FK mono select, empty "—") + role
// (select, required, options from the choices endpoint) + influence (select,
// clearable "—") + notes + source_quote. Identity invariant: contact OR name OR
// department, else Save disabled with a warning help message.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, waitFor } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: vi.fn(() => ({
    choices: {
      people_roles: [
        { value: "ECONOMIC_BUYER", label: "Economic Buyer" },
        { value: "CHAMPION", label: "Champion" },
      ],
      people_influences: [
        { value: "HIGH", label: "High" },
        { value: "LOW", label: "Low" },
      ],
    },
    choicesLoading: false,
  })),
}));
// Department choices arrive with INT values (backend contacts choices);
// the signal payload carries the id as a STRING — the form must line them up.
vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: vi.fn(() => ({
    standardDepartments: [
      { value: 1, label: "Finance" },
      { value: 2, label: "Marketing" },
    ],
  })),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
const closeDrawer = vi.fn();
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer, openDrawer: vi.fn() }),
}));
// The picker emits onChange(event, contact) — the AsyncContactSelect signature.
const PICKED = {
  id: "c-picked",
  first_name: "Paul",
  last_name: "Picked",
  job_title: "CTO",
  email: "paul@example.com",
};
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: (props) => (
    <div data-testid="people-contact-select" data-filters={JSON.stringify(props.filters ?? null)}>
      <span data-testid="people-contact-value">
        {props.value ? `${props.value.first_name} ${props.value.last_name}` : "none"}
      </span>
      <button type="button" onClick={(e) => props.onChange(e, PICKED)}>
        pick
      </button>
      <button type="button" onClick={(e) => props.onChange(e, null)}>
        clear
      </button>
    </div>
  ),
}));

import EditPeopleContent from "sections/activities/workspace/EditPeopleContent";
import { updateSignal } from "api/signals/signals";

const PEOPLE = {
  id: "people-1",
  status: "PENDING",
  role: "ECONOMIC_BUYER",
  role_display: "Economic Buyer",
  influence: "HIGH",
  influence_display: "High",
  full_name: "Sophie Martin",
  target_contact: { id: "c-orig", first_name: "Sophie", last_name: "Martin", job_title: "CFO" },
  target_department: { id: "1", name: "Finance" },
  notes: "Signs off every budget line.",
  source_quote: "Sophie will have the final word.",
};

const renderEdit = (people = PEOPLE, props = {}) =>
  render(
    <AphoriqTheme>
      <EditPeopleContent people={people} accountId="acc-1" {...props} />
    </AphoriqTheme>,
  );

const save = async () => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
  });
};

// An InlineEditableValue select opens WITH its menu already open: one click.
const openInlineSelect = (name) => {
  fireEvent.click(screen.getByTestId(`inline-read-${name}`));
};

const pickSelect = (name, optionName) => {
  openInlineSelect(name);
  fireEvent.click(screen.getByRole("option", { name: optionName }));
};

const pickDepartment = (optionName) => {
  fireEvent.mouseDown(screen.getByRole("combobox", { name: /department/i }));
  fireEvent.click(screen.getByRole("option", { name: optionName }));
};

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditPeopleContent (People S3)", () => {
  it("renders the 3 guiding sections pre-filled (contact, name, department, role, influence, notes, quote)", () => {
    renderEdit();
    expect(screen.getByText("Who is this person?")).toBeInTheDocument();
    expect(screen.getByText("What is their role?")).toBeInTheDocument();
    expect(screen.getByText("Source quote")).toBeInTheDocument();
    expect(screen.getByTestId("people-contact-value")).toHaveTextContent("Sophie Martin");
    expect(screen.getByTestId("inline-read-full_name")).toHaveTextContent("Sophie Martin");
    // int choices vs string payload id lined up → the department shows.
    expect(screen.getByRole("combobox", { name: /department/i })).toHaveTextContent("Finance");
    expect(screen.getByTestId("inline-read-role")).toHaveTextContent("Economic Buyer");
    expect(screen.getByTestId("inline-read-influence")).toHaveTextContent("High");
    expect(screen.getByText(PEOPLE.notes)).toBeInTheDocument();
    expect(screen.getByText(PEOPLE.source_quote)).toBeInTheDocument();
    expect(screen.queryByText("Edit people")).not.toBeInTheDocument();
  });

  it("E2: picking a contact → PATCH updateSignal('people', id, {target_contact: <uuid>})", async () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: "pick" }));
    await save();
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("people");
    expect(id).toBe("people-1");
    expect(patch.target_contact).toBe("c-picked");
  });

  it("E3: the picker is scoped to the activity's account — filters={{ account_id }}", () => {
    renderEdit();
    expect(JSON.parse(screen.getByTestId("people-contact-select").dataset.filters)).toEqual({
      account_id: "acc-1",
    });
  });

  it("E4: clearing contact, department and influence → null in the payload (name kept)", async () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: "clear" }));
    pickDepartment("—");
    pickSelect("influence", "—");
    await save();
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const patch = updateSignal.mock.calls[0][2];
    expect(patch.target_contact).toBeNull();
    expect(patch.target_department).toBeNull();
    expect(patch.influence).toBeNull();
    expect(patch.full_name).toBe("Sophie Martin");
  });

  it("E5: role changed → payload role = code; role options come from the choices only", async () => {
    renderEdit();
    openInlineSelect("role");
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["Economic Buyer", "Champion"]);
    fireEvent.click(screen.getByRole("option", { name: "Champion" }));
    await save();
    expect(updateSignal.mock.calls[0][2].role).toBe("CHAMPION");
  });

  it("select, one click: clicking the role opens the field WITH its menu already open", () => {
    renderEdit();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("inline-read-role"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("select: picking an option returns to READ showing the new value; Save sends it", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-role"));
    fireEvent.click(screen.getByRole("option", { name: "Champion" }));
    await waitFor(() => expect(screen.queryByTestId("inline-input-role")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-role")).toHaveTextContent("Champion");
    await save();
    expect(updateSignal.mock.calls[0][2].role).toBe("CHAMPION");
  });

  it("select: Escape with the menu open returns to READ with the original value", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-role"));
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByTestId("inline-input-role")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-role")).toHaveTextContent("Economic Buyer");
  });

  it("E5b: exact payload keys {role, influence, target_contact, target_department, full_name, notes, source_quote}", async () => {
    renderEdit();
    pickDepartment("Marketing");
    await save();
    expect(updateSignal.mock.calls[0][2]).toEqual({
      role: "ECONOMIC_BUYER",
      influence: "HIGH",
      target_contact: "c-orig",
      target_department: "2",
      full_name: "Sophie Martin",
      notes: PEOPLE.notes,
      source_quote: PEOPLE.source_quote,
    });
  });

  it("E6: contact, name AND department empty → Save disabled + warning help, no PATCH", async () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: "clear" }));
    pickDepartment("—");
    fireEvent.click(screen.getByTestId("inline-read-full_name"));
    fireEvent.change(screen.getByTestId("inline-input-full_name"), { target: { value: "  " } });
    await act(async () => {});
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    expect(screen.getByTestId("people-identity-warning")).toBeInTheDocument();
    await save();
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("single click on the name opens its input (real form, one click everywhere)", () => {
    renderEdit();
    expect(screen.queryByTestId("inline-input-full_name")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("inline-read-full_name"));
    expect(screen.getByTestId("inline-input-full_name")).toBeInTheDocument();
  });

  it("E6b: any one identity (name only) → Save enabled, no warning", async () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: "clear" }));
    pickDepartment("—");
    await act(async () => {});
    expect(screen.queryByTestId("people-identity-warning")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).not.toBeDisabled();
  });

  it("Save returns to the detail — onSaved gets the rebuilt signal (displays + compact FKs)", async () => {
    const onSaved = vi.fn();
    renderEdit(PEOPLE, { onSaved });
    fireEvent.click(screen.getByRole("button", { name: "pick" }));
    pickDepartment("Marketing");
    pickSelect("role", "Champion");
    await save();
    expect(onSaved).toHaveBeenCalledTimes(1);
    const updated = onSaved.mock.calls[0][0];
    expect(updated).toMatchObject({
      id: "people-1",
      role: "CHAMPION",
      role_display: "Champion",
      influence: "HIGH",
      influence_display: "High",
      target_department: { id: "2", name: "Marketing" },
    });
    expect(updated.target_contact).toEqual({
      id: "c-picked",
      first_name: "Paul",
      last_name: "Picked",
      job_title: "CTO",
    });
    expect(closeDrawer).not.toHaveBeenCalled();
  });
});
