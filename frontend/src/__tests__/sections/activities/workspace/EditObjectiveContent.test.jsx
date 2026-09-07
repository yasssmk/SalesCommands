// frontend/src/__tests__/sections/activities/workspace/EditObjectiveContent.test.jsx
//
// SIG-5d — the Objective EDIT drawer on the new pattern (DrawerContentLayout +
// InlineEditableValue + ObjectiveScopePill + Formik global Save). Migrates the
// old InlineObjectiveForm behaviour; the only functional changes are: scope via
// the pill (SIG-5b) and an added editable source_quote. Saves via the existing
// generic updateSignal("objective", id, patch).

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

describe("EditObjectiveContent (SIG-5d)", () => {
  it("pre-fills the migrated fields (summary, success, notes, source_quote)", () => {
    renderEdit();
    expect(screen.getByText("Reduce reporting time by 50%")).toBeInTheDocument();
    expect(screen.getByText("Monthly reports in 2 hours")).toBeInTheDocument();
    expect(screen.getByText("Priority for the VP")).toBeInTheDocument();
    expect(screen.getByText("We want to cut reporting time by half")).toBeInTheDocument();
  });

  it("renders the scope pill (Company/Department) with Department active + dept select", () => {
    renderEdit();
    expect(screen.getByTestId("scope-pill-BUSINESS")).toBeInTheDocument();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("scope-department-select")).toBeInTheDocument();
  });

  it("exposes an editable source_quote (added field)", () => {
    renderEdit();
    // The source_quote read row is present and enters edit on double-click.
    const readRow = screen.getByTestId("inline-read-source_quote");
    fireEvent.doubleClick(readRow);
    expect(screen.getByTestId("inline-input-source_quote")).toBeInTheDocument();
  });

  it("exposes an editable target_date (date field)", () => {
    renderEdit();
    expect(screen.getByTestId("objective-target-date")).toHaveValue("2026-12-31");
  });

  it("double-click edits summary (draft) and Save PATCHes via updateSignal", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "Reduce reporting time drastically" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("objective");
    expect(id).toBe("obj-1");
    expect(patch).toMatchObject({
      summary: "Reduce reporting time drastically",
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

  it("switching the scope pill to Company clears the department in the patch", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.scope_level).toBe("BUSINESS");
    expect(patch.target_department).toBeNull();
  });

  it("Cancel closes the drawer without saving", () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(closeDrawer).toHaveBeenCalled();
    expect(updateSignal).not.toHaveBeenCalled();
  });
});
