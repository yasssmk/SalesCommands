// frontend/src/__tests__/sections/activities/workspace/EditTechStackContent.test.jsx
//
// Sprint TechStack T2b — the TechStack EDIT drawer on the standard chassis
// (Activity surface), same 5 sections / order as the T1 detail:
// Technology → Usage → Lifecycle → Notes → Source.
//   - §2 Usage = the shared exclusive-scope gesture (3 pills Department ·
//     Company · Unknown, labels from the choices); Department → department pills
//     + "+ add department" with options stringified (TD-241: the contacts
//     choices emit INTEGER ids, the signal payload STRING ids); Company /
//     Unknown mask the departments and send []; Department with no department
//     blocks the save (backend T0 rule).
//   - §3 Lifecycle: start year / discontinued via renderEditor, dates via the
//     shared InlineDateField; discontinued ⇒ date required.
//   - Payload: every edited field, NEVER is_to_replace.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, within, waitFor } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: vi.fn(() => ({
    choices: {
      // Real /signals/choices/ usage_scopes (backend UsageScope, T0).
      usage_scopes: [
        { value: "DEPARTMENT", label: "Department" },
        { value: "COMPANY", label: "Company" },
        { value: "UNKNOWN", label: "Unknown" },
      ],
    },
    choicesLoading: false,
  })),
}));
// REAL backend contact-choices shape: the department `value` is the INTEGER pk
// ({'value': dept.id}), the signal payload carries STRING ids (str(d.id)).
vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: vi.fn(() => ({
    standardDepartments: [
      { value: 3, label: "Marketing" },
      { value: 5, label: "Sales" },
    ],
  })),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
// x-date-pickers — stubbed in tests (jsdom can't resolve its ESM), same as
// OutcomeDrawerContent.test: a "pick" button fires onChange with a dayjs date.
vi.mock("@mui/x-date-pickers/DatePicker", async () => {
  const { default: dayjs } = await import("dayjs");
  return {
    DatePicker: (props) => (
      <button
        type="button"
        data-testid={`pick-${props.label}`}
        onClick={() => props.onChange(dayjs("2026-12-31"))}
      >
        pick {props.label}
      </button>
    ),
  };
});
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
const closeDrawer = vi.fn();
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer, openDrawer: vi.fn() }),
}));

import EditTechStackContent from "sections/activities/workspace/EditTechStackContent";
import { updateSignal } from "api/signals/signals";

const TECH = {
  id: "ts-1",
  status: "PENDING",
  tech_name: "HubSpot",
  is_to_replace: true,
  usage_scope: "DEPARTMENT",
  usage_scope_display: "Department",
  // List / detail serializer shape: [{id (STRING), name}].
  usage_departments: [{ id: "5", name: "Sales" }],
  usage_start_year: 2021,
  renewal_date: "2026-06-15",
  cost_description: "~50k/year",
  is_discontinued: false,
  discontinued_date: null,
  notes: "They find the reporting clunky.",
  source_quote: "Sales lives in HubSpot.",
};

const renderEdit = (techstack = TECH, props = {}) =>
  render(
    <AphoriqTheme>
      <EditTechStackContent techstack={techstack} accountId="acc-1" {...props} />
    </AphoriqTheme>,
  );

const save = async () => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
  });
};

const addDepartment = (label) => {
  fireEvent.click(screen.getByTestId("add-department"));
  fireEvent.click(screen.getByRole("button", { name: "Open" }));
  fireEvent.click(screen.getByRole("option", { name: label }));
  fireEvent.click(screen.getByTestId("confirm-add-departments"));
};

const editNotes = (text) => {
  fireEvent.click(screen.getByTestId("inline-read-notes"));
  fireEvent.change(screen.getByTestId("inline-input-notes"), { target: { value: text } });
};

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditTechStackContent (T2b)", () => {
  it("renders the 5 sections in the detail order (Source last)", () => {
    renderEdit();
    const body = screen.getByTestId("techstack-edit");
    // First occurrence = the section title ("Notes" is also the field label below it).
    const titles = ["Technology", "Usage", "Lifecycle", "Notes", "Source"].map(
      (t) => within(body).getAllByText(t)[0],
    );
    for (let i = 1; i < titles.length; i += 1) {
      expect(
        titles[i - 1].compareDocumentPosition(titles[i]) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    }
  });

  it("(T2c-1) §2 shows ONLY Department · Company (choices labels), NO Unknown pill", () => {
    renderEdit();
    const pills = screen.getByTestId("techstack-scope-pills");
    expect(within(pills).getAllByRole("button")).toHaveLength(2);
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveTextContent("Department");
    expect(screen.getByTestId("scope-pill-COMPANY")).toHaveTextContent("Company");
    expect(screen.queryByTestId("scope-pill-UNKNOWN")).not.toBeInTheDocument();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "true");
  });

  it("(T2c-1) an UNKNOWN signal → no pill pressed", () => {
    renderEdit({ ...TECH, id: "ts-unknown", usage_scope: "UNKNOWN", usage_departments: [] });
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("scope-pill-COMPANY")).toHaveAttribute("aria-pressed", "false");
  });

  // (b) — real types: int choices vs string payload ids.
  it("(b) the existing department reads 'Sales' (int option vs string id)", () => {
    renderEdit();
    const field = screen.getByTestId("techstack-departments-field");
    expect(within(field).getByTestId("dept-pill-5")).toHaveTextContent("Sales");
  });

  it("(b) the '+ add department' menu never re-proposes an already-chosen department", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.queryByRole("option", { name: "Sales" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Marketing" })).toBeInTheDocument();
  });

  it("(b) add then remove a department without duplicate; the payload carries the ids", async () => {
    renderEdit();
    addDepartment("Marketing");
    const field = screen.getByTestId("techstack-departments-field");
    expect(within(field).getAllByText("Sales")).toHaveLength(1);
    expect(within(field).getAllByText("Marketing")).toHaveLength(1);

    fireEvent.click(within(field).getByTestId("remove-dept-5"));
    expect(within(field).queryByText("Sales")).not.toBeInTheDocument();

    await save();
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("tech-stack");
    expect(id).toBe("ts-1");
    expect(patch.usage_scope).toBe("DEPARTMENT");
    expect(patch.usage_departments).toEqual(["3"]);
  });

  // (c) — Company / Unknown mask the departments and send [].
  it("(c) Company → payload usage_departments [] (departments masked, not cleared)", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("scope-pill-COMPANY"));
    expect(screen.queryByTestId("techstack-departments-field")).not.toBeInTheDocument();

    await save();
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.usage_scope).toBe("COMPANY");
    expect(patch.usage_departments).toEqual([]);
  });

  it("(T2c-1) a click on the ACTIVE pill deselects it → UNKNOWN + usage_departments []", async () => {
    renderEdit(); // Department pressed, Sales chosen
    fireEvent.click(screen.getByTestId("scope-pill-DEPARTMENT"));
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("scope-pill-COMPANY")).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByTestId("techstack-departments-field")).not.toBeInTheDocument();
    await save();
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.usage_scope).toBe("UNKNOWN");
    expect(patch.usage_departments).toEqual([]);
  });

  it("(T2c-1) deselecting Company → UNKNOWN", async () => {
    renderEdit({ ...TECH, id: "ts-co", usage_scope: "COMPANY", usage_departments: [] });
    fireEvent.click(screen.getByTestId("scope-pill-COMPANY"));
    await save();
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.usage_scope).toBe("UNKNOWN");
    expect(patch.usage_departments).toEqual([]);
  });

  it("(c) Company then back to Department keeps the chosen departments", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("scope-pill-COMPANY"));
    fireEvent.click(screen.getByTestId("scope-pill-DEPARTMENT"));
    expect(
      within(screen.getByTestId("techstack-departments-field")).getByText("Sales"),
    ).toBeInTheDocument();
  });

  // (d) — Department with no department blocks the save.
  it("(d) Department with no department → save blocked with a message", async () => {
    renderEdit({ ...TECH, id: "ts-company", usage_scope: "COMPANY", usage_departments: [] });
    fireEvent.click(screen.getByTestId("scope-pill-DEPARTMENT"));
    expect(await screen.findByText("Pick at least one department")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    await save();
    expect(updateSignal).not.toHaveBeenCalled();
  });

  // (e) — discontinued without a date blocks the save.
  it("(T2c-3) Discontinued is a Switch shown directly (no click to reveal), one single label", () => {
    renderEdit();
    const toggle = screen.getByRole("checkbox", { name: "Discontinued" });
    expect(toggle.closest(".MuiSwitch-root")).not.toBeNull();
    expect(toggle).not.toBeChecked();
    expect(screen.queryByTestId("inline-read-is_discontinued")).not.toBeInTheDocument();
    expect(within(screen.getByTestId("techstack-edit")).getAllByText("Discontinued")).toHaveLength(1);
    // Off → no discontinued-date field.
    expect(screen.queryByTestId("inline-read-discontinued_date")).not.toBeInTheDocument();
  });

  it("(e) discontinued ticked without a date → save blocked with a message", async () => {
    renderEdit();
    fireEvent.click(screen.getByRole("checkbox", { name: "Discontinued" }));
    // On → the (required) discontinued-date field appears, empty → "Unknown".
    expect(screen.getByTestId("inline-read-discontinued_date")).toHaveTextContent("Unknown");
    expect(await screen.findByText("Discontinued date is required")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    await save();
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("(e) a discontinued tool shows its date; unticking clears the date in the payload", async () => {
    renderEdit({
      ...TECH, id: "ts-disc", is_discontinued: true, discontinued_date: "2026-06-30",
    });
    expect(screen.getByTestId("inline-read-discontinued_date")).toHaveTextContent("30 Jun 2026");
    expect(screen.getByRole("checkbox", { name: "Discontinued" })).toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: "Discontinued" }));
    expect(screen.queryByTestId("inline-read-discontinued_date")).not.toBeInTheDocument();

    // Switched back on → the date was ERASED (not restored): reads "Unknown".
    fireEvent.click(screen.getByRole("checkbox", { name: "Discontinued" }));
    expect(screen.getByTestId("inline-read-discontinued_date")).toHaveTextContent("Unknown");
    fireEvent.click(screen.getByRole("checkbox", { name: "Discontinued" }));

    await save();
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.is_discontinued).toBe(false);
    expect(patch.discontinued_date).toBeNull();
  });

  it("§3 start year via the click-to-edit editor; out of bounds blocks the save", async () => {
    renderEdit();
    expect(screen.getByTestId("inline-read-usage_start_year")).toHaveTextContent("2021");
    fireEvent.click(screen.getByTestId("inline-read-usage_start_year"));
    fireEvent.change(screen.getByTestId("inline-input-usage_start_year"), {
      target: { value: "1900" },
    });
    expect(await screen.findByText(/Year must be/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();

    fireEvent.change(screen.getByTestId("inline-input-usage_start_year"), {
      target: { value: "2019" },
    });
    // Formik validates asynchronously — wait for the save to be enabled again.
    await waitFor(() => expect(screen.getByRole("button", { name: /save/i })).toBeEnabled());
    await save();
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.usage_start_year).toBe(2019);
  });

  it("(T2d-1) the start year editor has the ✓ / ✗ buttons of the date field (same ids pattern, same aria)", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-usage_start_year"));
    expect(screen.getByTestId("usage-start-year-confirm")).toHaveAttribute("aria-label", "Confirm used since");
    expect(screen.getByTestId("usage-start-year-cancel")).toHaveAttribute("aria-label", "Discard used since");
  });

  it("(T2d-1) erase the year like a date: empty the field + ✓ → null, reads 'Unknown'", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-usage_start_year"));
    fireEvent.change(screen.getByTestId("inline-input-usage_start_year"), { target: { value: "" } });
    fireEvent.click(screen.getByTestId("usage-start-year-confirm"));
    expect(screen.getByTestId("inline-read-usage_start_year")).toHaveTextContent("Unknown");
    await waitFor(() => expect(screen.getByRole("button", { name: /save/i })).toBeEnabled());
    await save();
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.usage_start_year).toBeNull();
  });

  it("(T2d-1) ✗ discards the year being typed (back to the stored value)", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-usage_start_year"));
    fireEvent.change(screen.getByTestId("inline-input-usage_start_year"), { target: { value: "1999" } });
    fireEvent.click(screen.getByTestId("usage-start-year-cancel"));
    expect(screen.getByTestId("inline-read-usage_start_year")).toHaveTextContent("2021");
  });

  it("(T2d-2) Discontinued: label LEFT (field-label typography), switch RIGHT, one row", () => {
    renderEdit();
    const row = screen.getByTestId("techstack-discontinued-row");
    const label = within(row).getByText("Discontinued");
    const toggle = within(row).getByRole("checkbox", { name: "Discontinued" });
    // Same typography as the other field labels (InlineEditableValue caption).
    expect(label).toHaveClass("MuiTypography-caption");
    // Label first, switch after (left → right), no FormControlLabel wrapper.
    expect(label.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(row.querySelector(".MuiFormControlLabel-root")).toBeNull();
    expect(toggle.closest(".MuiSwitch-root")).not.toBeNull();
  });

  it("(T2d-3) 'Discontinued date is required' is a WARNING (business rule), not a red error", async () => {
    renderEdit();
    fireEvent.click(screen.getByRole("checkbox", { name: "Discontinued" }));
    const message = await screen.findByText("Discontinued date is required");
    expect(message.closest(".MuiAlert-standardWarning")).not.toBeNull();
    expect(message.closest(".Mui-error")).toBeNull();
  });

  it("(T2c-2) the start year can be ERASED: cleared + validated → null, reads 'Unknown'", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-usage_start_year"));
    const input = screen.getByTestId("inline-input-usage_start_year");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByTestId("inline-read-usage_start_year")).toHaveTextContent("Unknown");
    await waitFor(() => expect(screen.getByRole("button", { name: /save/i })).toBeEnabled());
    await save();
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.usage_start_year).toBeNull();
  });

  it("(T2c-2) Escape cancels the year being typed (back to the stored value)", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-usage_start_year"));
    const input = screen.getByTestId("inline-input-usage_start_year");
    fireEvent.change(input, { target: { value: "1999" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.getByTestId("inline-read-usage_start_year")).toHaveTextContent("2021");
  });

  it("(T2c-4) empty renewal date reads 'Unknown' (not 'No date set')", () => {
    renderEdit({ ...TECH, id: "ts-no-renewal", renewal_date: null });
    const renewal = screen.getByTestId("inline-read-renewal_date");
    expect(renewal).toHaveTextContent("Unknown");
    expect(renewal).not.toHaveTextContent("No date set");
  });

  it("§1 a blanked tool name blocks the save", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-tech_name"));
    fireEvent.change(screen.getByTestId("inline-input-tech_name"), { target: { value: "  " } });
    expect(await screen.findByText("Tool name is required")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  // (f) — the payload carries every edited field and NEVER is_to_replace.
  it("(f) payload = the edited fields, WITHOUT is_to_replace", async () => {
    renderEdit();
    editNotes("Renewal in June, unhappy with support.");
    await save();
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch).toEqual({
      tech_name: "HubSpot",
      usage_scope: "DEPARTMENT",
      usage_departments: ["5"],
      usage_start_year: 2021,
      renewal_date: "2026-06-15",
      cost_description: "~50k/year",
      is_discontinued: false,
      discontinued_date: null,
      notes: "Renewal in June, unhappy with support.",
      source_quote: "Sales lives in HubSpot.",
    });
    expect(patch).not.toHaveProperty("is_to_replace");
  });

  it("onSaved receives the rebuilt signal (departments as {id,name}, scope label)", async () => {
    const onSaved = vi.fn();
    renderEdit(TECH, { onSaved });
    fireEvent.click(screen.getByTestId("scope-pill-COMPANY"));
    await save();
    expect(onSaved).toHaveBeenCalledTimes(1);
    const updated = onSaved.mock.calls[0][0];
    expect(updated.usage_scope).toBe("COMPANY");
    expect(updated.usage_scope_display).toBe("Company");
    expect(updated.usage_departments).toEqual([]);
    // is_to_replace untouched (not edited, still on the signal).
    expect(updated.is_to_replace).toBe(true);
  });
});
