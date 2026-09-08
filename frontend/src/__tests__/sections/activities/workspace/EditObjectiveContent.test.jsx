// frontend/src/__tests__/sections/activities/workspace/EditObjectiveContent.test.jsx
//
// SIG-5d* — the Objective EDIT drawer. Keeps the original form's structure (3
// section headers + subtitles + the Domain × Dimension recap) but the fields are
// InlineEditableValue (double-click to edit, uniform with edit-activity /
// edit-contact). Scope is the pill + the original MUI department Select. The
// coque owns the "Edit objective" title (no duplicate in the content). source_quote
// is its own titled section. Save PATCHes via updateSignal("objective", id, patch).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: vi.fn(() => ({
    choices: {
      signal_whats: [{ value: "OPS", label: "Operations" }, { value: "DATA", label: "Data" }],
      signal_dimensions: [{ value: "TIME", label: "Time" }, { value: "QUALITY", label: "Quality" }],
    },
    choicesLoading: false,
  })),
}));
vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: vi.fn(() => ({
    standardDepartments: [
      { value: "d1", label: "Finance" },
      { value: "d2", label: "Marketing" },
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

// x-date-pickers — stubbed in tests (jsdom can't resolve its ESM), same as
// OutcomeDrawerContent.test. Renders an input labelled by the picker's `label`.
vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: ({ label, value }) => (
    <input
      aria-label={label}
      data-testid="objective-target-date"
      readOnly
      value={value && value.format ? value.format("YYYY-MM-DD") : ""}
    />
  ),
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => children,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

import EditObjectiveContent from "sections/activities/workspace/EditObjectiveContent";
import { updateSignal } from "api/signals/signals";

const OBJECTIVE = {
  id: "obj-1",
  status: "VALIDATED",
  summary: "Reduce reporting time by 50%",
  what: "OPS",
  dimension: "TIME",
  scope_level: "DEPARTMENT",
  target_department: { id: "d1", name: "Finance" },
  success_criteria: "Monthly reports in 2 hours",
  target_date: "2026-12-31",
  notes: "Priority for the VP",
  source_quote: "We want to cut reporting time by half",
};

const renderEdit = (objective = OBJECTIVE, props = {}) =>
  render(
    <AphoriqTheme>
      <EditObjectiveContent objective={objective} accountId="acc-1" {...props} />
    </AphoriqTheme>,
  );

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditObjectiveContent (SIG-5d-fix2)", () => {
  it("renders the fields as InlineEditableValue (double-click), pre-filled in read mode", () => {
    renderEdit();
    // Read rows exist for each editable text/select field…
    ["summary", "what", "dimension", "success_criteria", "notes", "source_quote"].forEach(
      (name) => expect(screen.getByTestId(`inline-read-${name}`)).toBeInTheDocument(),
    );
    // …and show the current values (not open MUI inputs).
    expect(screen.getByText("Reduce reporting time by 50%")).toBeInTheDocument();
    expect(screen.getByText("We want to cut reporting time by half")).toBeInTheDocument();
  });

  it("target_date reveals the project DatePicker only on double-click (✓/✗), like edit scheduled activity", () => {
    renderEdit();
    // Read row by default — the picker is hidden.
    expect(screen.getByTestId("inline-read-target_date")).toBeInTheDocument();
    expect(screen.queryByLabelText("Target date")).not.toBeInTheDocument();
    // Double-click reveals the project DatePicker + confirm/discard controls.
    fireEvent.doubleClick(screen.getByTestId("inline-read-target_date"));
    expect(screen.getByLabelText("Target date")).toBeInTheDocument();
    expect(screen.getByTestId("target-date-confirm")).toBeInTheDocument();
    expect(screen.getByTestId("target-date-cancel")).toBeInTheDocument();
  });

  it("keeps the 3 section subtitles and the Domain × Dimension recap", () => {
    renderEdit();
    expect(screen.getByText("Describe the objective and pick its canonical axes.")).toBeInTheDocument();
    expect(screen.getByText("Pick the organisational scope driving this goal.")).toBeInTheDocument();
    expect(screen.getByText("Optional — success criteria, deadline, and notes.")).toBeInTheDocument();
    expect(screen.getByText(/This is a/)).toBeInTheDocument();
    expect(screen.getByText("Operations × Time")).toBeInTheDocument();
  });

  it("does NOT render its own 'Edit objective' title (the coque owns it — no duplicate)", () => {
    renderEdit();
    expect(screen.queryByText("Edit objective")).not.toBeInTheDocument();
  });

  it("gives source_quote its own titled section", () => {
    renderEdit();
    expect(screen.getByText("Source quote")).toBeInTheDocument();
    expect(screen.getByText("Where does this signal come from")).toBeInTheDocument();
  });

  it("scope stays a pill + the ORIGINAL department Select (unchanged, mono-department)", () => {
    renderEdit();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByText("Target Department *").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("scope-department-select")).not.toBeInTheDocument();
  });

  it("double-click edits summary and Save PATCHes via updateSignal with the full payload", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "Reduce reporting time drastically now" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("objective");
    expect(id).toBe("obj-1");
    expect(patch).toMatchObject({
      summary: "Reduce reporting time drastically now",
      what: "OPS",
      dimension: "TIME",
      scope_level: "DEPARTMENT",
      target_department: "d1",
      success_criteria: "Monthly reports in 2 hours",
      target_date: "2026-12-31",
      notes: "Priority for the VP",
      source_quote: "We want to cut reporting time by half",
    });
  });

  it("source_quote edits on double-click", () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-source_quote"));
    expect(screen.getByTestId("inline-input-source_quote")).toBeInTheDocument();
  });

  it("switching to Company hides the dept select and clears it in the save patch", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    expect(screen.queryAllByText("Target Department *")).toHaveLength(0);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.scope_level).toBe("BUSINESS");
    expect(patch.target_department).toBeNull();
  });

  it("Cancel with no onCancel falls back to closing the drawer (legacy)", () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(closeDrawer).toHaveBeenCalled();
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("SIG-5e-fix5: Cancel returns to the detail — onCancel called, no save, drawer not closed", () => {
    const onCancel = vi.fn();
    renderEdit(OBJECTIVE, { onCancel });
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(updateSignal).not.toHaveBeenCalled();
    expect(closeDrawer).not.toHaveBeenCalled();
  });

  it("SIG-5e-fix5: Save returns to the detail — onSaved receives the updated signal, drawer not closed", async () => {
    const onSaved = vi.fn();
    renderEdit(OBJECTIVE, { onSaved });
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "Reduce reporting time drastically now" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
    // The updated signal carries the edited summary so the detail re-renders it.
    expect(onSaved.mock.calls[0][0]).toMatchObject({
      id: "obj-1",
      summary: "Reduce reporting time drastically now",
    });
    expect(closeDrawer).not.toHaveBeenCalled();
  });
});
