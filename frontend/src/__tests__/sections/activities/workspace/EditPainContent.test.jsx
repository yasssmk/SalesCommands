// frontend/src/__tests__/sections/activities/workspace/EditPainContent.test.jsx
//
// S3 / S3-fix — the Pain EDIT drawer, a mirror of EditObjectiveContent on the
// standard chassis. Fields are InlineEditableValue (double-click). Scope (Option
// A): NO manual scope control — the single control is the department multi-select
// (MultiSelectFilter, deletable pills), ALWAYS present, NEVER required;
// scope_level is DERIVED at save (≥1 → DEPARTMENT, 0 → BUSINESS). Save PATCHes via
// updateSignal("pain", id, payload) with ONLY Pain's writable fields — NO FK.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, within } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: vi.fn(() => ({
    choices: {
      signal_whats: [{ value: "OPS", label: "Operations" }, { value: "DATA", label: "Data" }],
      signal_dimensions: [{ value: "TIME", label: "Time" }, { value: "QUALITY", label: "Quality" }],
      scope_levels: [
        { value: "BUSINESS", label: "Business" },
        { value: "DEPARTMENT", label: "Department" },
      ],
    },
    choicesLoading: false,
  })),
}));
// Mirror the REAL backend contact-choices shape: department `value` is the
// INTEGER pk ({'value': dept.id}, contacts/views/views.py), whereas the signal
// payload carries department ids as STRINGS (str(d.id)). This is exactly the
// type mismatch that broke accumulation — the fix stringifies the option values.
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

import EditPainContent from "sections/activities/workspace/EditPainContent";
import { updateSignal } from "api/signals/signals";

const PAIN = {
  id: "pain-1",
  status: "VALIDATED",
  summary: "Reporting takes five hours a week",
  what: "OPS",
  dimension: "TIME",
  scope_level: "DEPARTMENT",
  // detail serializer shape: [{id,name}]
  target_departments: [{ id: "1", name: "Finance" }],
  notes: "Priority for the VP",
  related_techstack_mention: "Excel",
  source_quote: "We lose five hours every week",
};

const renderEdit = (pain = PAIN, props = {}) =>
  render(
    <AphoriqTheme>
      <EditPainContent pain={pain} accountId="acc-1" {...props} />
    </AphoriqTheme>,
  );

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditPainContent (S3)", () => {
  it("renders the editable fields as InlineEditableValue, pre-filled in read mode", () => {
    renderEdit();
    ["summary", "what", "dimension", "related_techstack_mention", "notes", "source_quote"].forEach(
      (name) => expect(screen.getByTestId(`inline-read-${name}`)).toBeInTheDocument(),
    );
    expect(screen.getByText("Reporting takes five hours a week")).toBeInTheDocument();
    expect(screen.getByText("We lose five hours every week")).toBeInTheDocument();
  });

  it("renders the 4 chassis sections + the Domain × Dimension recap", () => {
    renderEdit();
    expect(screen.getByText("Describe the pain and pick its canonical axes.")).toBeInTheDocument();
    // S3-fix-2: the scope section is now the explicit Company | Department control.
    expect(screen.getByText("Company-wide, or one or more departments.")).toBeInTheDocument();
    expect(screen.getByText("Source quote")).toBeInTheDocument();
    expect(screen.getByText(/This is a/)).toBeInTheDocument();
    expect(screen.getByText("Operations × Time")).toBeInTheDocument();
    expect(screen.getByText(/pain:OPS:TIME/)).toBeInTheDocument();
  });

  it("does NOT render its own 'Edit pain' title (the coque owns it)", () => {
    renderEdit();
    expect(screen.queryByText("Edit pain")).not.toBeInTheDocument();
  });

  it("S3-fix-2: shows the two explicit scope pills (Company / Department)", () => {
    renderEdit(); // PAIN carries a department → DEPARTMENT is active
    expect(screen.getByTestId("scope-pill-BUSINESS")).toBeInTheDocument();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toBeInTheDocument();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "true");
  });

  it("Department scope shows the current departments as pills + a '+ add department' trigger", () => {
    renderEdit();
    const field = screen.getByTestId("pain-departments-field");
    // Committed department pill (Chip).
    expect(within(field).getByTestId("dept-pill-1")).toHaveTextContent("Finance");
    // The "+ add department" gesture (picker collapsed).
    expect(screen.getByTestId("add-department")).toBeInTheDocument();
    expect(screen.queryByTestId("pain-add-department-picker")).not.toBeInTheDocument();
  });

  it("S3-fix-2: '+ add department' grouped picker accumulates chosen departments as pills, × removes one", () => {
    renderEdit(); // PAIN starts with Finance (id 1)

    // Open the grouped picker, stage Marketing, then CONFIRM (grouped validation).
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    fireEvent.click(screen.getByTestId("confirm-add-departments"));

    const field = screen.getByTestId("pain-departments-field");
    // Both pills present (accumulation), picker collapsed.
    expect(within(field).getByText("Finance")).toBeInTheDocument();
    expect(within(field).getByText("Marketing")).toBeInTheDocument();
    expect(screen.queryByTestId("pain-add-department-picker")).not.toBeInTheDocument();

    // Remove Finance via its × — only Marketing remains.
    const financeChip = within(field).getByText("Finance").closest(".MuiChip-root");
    fireEvent.click(within(financeChip).getByTestId("CancelIcon"));
    expect(within(field).queryByText("Finance")).not.toBeInTheDocument();
    expect(within(field).getByText("Marketing")).toBeInTheDocument();
  });

  it("Company pill clears the departments and hides the add gesture", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    expect(screen.queryByTestId("pain-departments-field")).not.toBeInTheDocument();
    expect(screen.queryByTestId("add-department")).not.toBeInTheDocument();
  });

  it("Save PATCHes via updateSignal('pain', ...) — Department + 2 depts → scope DEPARTMENT + [id1,id2], NO FK", async () => {
    renderEdit();
    // Add a second department via the grouped picker (makes the form dirty).
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    fireEvent.click(screen.getByTestId("confirm-add-departments"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });

    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("pain");
    expect(id).toBe("pain-1");
    expect(patch).toMatchObject({
      what: "OPS",
      dimension: "TIME",
      // scope_level is EXPLICIT (the Department pill).
      scope_level: "DEPARTMENT",
      notes: "Priority for the VP",
      related_techstack_mention: "Excel",
    });
    // Ids extracted from the stored {value,label} objects (both departments).
    expect(patch.target_departments).toEqual(["1", "2"]);
    expect(patch).not.toHaveProperty("target_department");
    expect(patch).not.toHaveProperty("target_contact");
  });

  it("Save PATCHes — Company scope → scope BUSINESS + empty list, NO FK", async () => {
    renderEdit();
    // Switch to Company (explicit): clears departments, derives BUSINESS.
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.scope_level).toBe("BUSINESS");
    expect(patch.target_departments).toEqual([]);
    expect(patch).not.toHaveProperty("target_department");
    expect(patch).not.toHaveProperty("target_contact");
  });

  it("Save returns to the detail — onSaved receives the updated signal, drawer not closed", async () => {
    const onSaved = vi.fn();
    renderEdit(PAIN, { onSaved });
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "Reporting eats a whole day every single week" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(onSaved.mock.calls[0][0]).toMatchObject({
      id: "pain-1",
      summary: "Reporting eats a whole day every single week",
    });
    // The updated signal rebuilds target_departments as [{id,name}] for the detail.
    expect(onSaved.mock.calls[0][0].target_departments).toEqual([
      { id: "1", name: "Finance" },
    ]);
    expect(closeDrawer).not.toHaveBeenCalled();
  });

  it("Cancel returns to the detail — onCancel called, no save", () => {
    const onCancel = vi.fn();
    renderEdit(PAIN, { onCancel });
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(updateSignal).not.toHaveBeenCalled();
    expect(closeDrawer).not.toHaveBeenCalled();
  });
});
