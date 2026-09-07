// frontend/src/__tests__/sections/activities/workspace/EditObjectiveContent.test.jsx
//
// SIG-5d / SIG-5d-fix — the Objective EDIT drawer reproduces the original
// InlineObjectiveForm (MUI TextField/Select fields, 3 section subtitles, the
// Domain × Dimension recap, original department Select) on DrawerContentLayout,
// changing only: scope → ObjectiveScopePill, and an added editable source_quote.
// Save PATCHes via the existing generic updateSignal("objective", id, patch).

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

describe("EditObjectiveContent (SIG-5d / SIG-5d-fix)", () => {
  it("pre-fills the migrated fields (summary, success, notes, source_quote, date)", () => {
    renderEdit();
    expect(screen.getByDisplayValue("Reduce reporting time by 50%")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Monthly reports in 2 hours")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Priority for the VP")).toBeInTheDocument();
    expect(screen.getByDisplayValue("We want to cut reporting time by half")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2026-12-31")).toBeInTheDocument();
  });

  it("reproduces the 3 section subtitles and the Domain × Dimension recap", () => {
    renderEdit();
    expect(screen.getByText("Describe the objective and pick its canonical axes.")).toBeInTheDocument();
    expect(screen.getByText("Pick the organisational scope driving this goal.")).toBeInTheDocument();
    expect(screen.getByText("Optional — success criteria, deadline, and notes.")).toBeInTheDocument();
    expect(screen.getByText(/This is a/)).toBeInTheDocument();
    expect(screen.getByText("Operations × Time")).toBeInTheDocument();
  });

  it("scope: Department active + the ORIGINAL department Select (no ad-hoc native select)", () => {
    renderEdit();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "true");
    // MUI renders the Select label twice (InputLabel + outline legend).
    expect(screen.getAllByText("Target Department *").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("scope-department-select")).not.toBeInTheDocument();
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

  it("edits summary and Save PATCHes via updateSignal with the full payload", async () => {
    renderEdit();
    fireEvent.change(screen.getByDisplayValue("Reduce reporting time by 50%"), {
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

  it("source_quote is editable (added field)", () => {
    renderEdit();
    const sq = screen.getByDisplayValue("We want to cut reporting time by half");
    fireEvent.change(sq, { target: { value: "A newly picked quote" } });
    expect(sq).toHaveValue("A newly picked quote");
  });

  it("Cancel closes the drawer without saving", () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(closeDrawer).toHaveBeenCalled();
    expect(updateSignal).not.toHaveBeenCalled();
  });
});
