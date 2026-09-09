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
    // S3-fix: the scope section is now the departments-only control (no manual scope).
    expect(
      screen.getByText("Pick the departments this pain concerns — leave empty for company-wide."),
    ).toBeInTheDocument();
    expect(screen.getByText("Source quote")).toBeInTheDocument();
    expect(screen.getByText(/This is a/)).toBeInTheDocument();
    expect(screen.getByText("Operations × Time")).toBeInTheDocument();
    expect(screen.getByText(/pain:OPS:TIME/)).toBeInTheDocument();
  });

  it("does NOT render its own 'Edit pain' title (the coque owns it)", () => {
    renderEdit();
    expect(screen.queryByText("Edit pain")).not.toBeInTheDocument();
  });

  it("S3-fix: no manual scope control — the ObjectiveScopePill is gone", () => {
    renderEdit();
    expect(screen.queryByTestId("scope-pill-BUSINESS")).not.toBeInTheDocument();
    expect(screen.queryByTestId("scope-pill-DEPARTMENT")).not.toBeInTheDocument();
  });

  it("shows the M2M department multi-select ALWAYS present, pre-filled with the current departments", () => {
    renderEdit();
    const field = screen.getByTestId("pain-departments-field");
    // Field is present regardless of scope, and the current department is a chip.
    expect(within(field).getByText("Finance")).toBeInTheDocument();
    // No Objective-style "Target Department *" mono select.
    expect(screen.queryByText("Target Department *")).not.toBeInTheDocument();
  });

  it("S3-fix: the department multi-select ACCUMULATES and supports remove via the × chip", () => {
    renderEdit(); // PAIN starts with Finance (d1)
    const field = screen.getByTestId("pain-departments-field");
    expect(within(field).getByText("Finance")).toBeInTheDocument();

    // Open the picker and add Marketing — it accumulates (Finance stays).
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    expect(within(field).getByText("Finance")).toBeInTheDocument();
    expect(within(field).getByText("Marketing")).toBeInTheDocument();

    // Remove Finance via its × (chip delete) — only Marketing remains.
    const financeChip = within(field).getByText("Finance").closest(".MuiChip-root");
    fireEvent.click(within(financeChip).getByTestId("CancelIcon"));
    expect(within(field).queryByText("Finance")).not.toBeInTheDocument();
    expect(within(field).getByText("Marketing")).toBeInTheDocument();
  });

  it("Save PATCHes via updateSignal('pain', ...) — target_departments accumulate, scope DEPARTMENT, NO FK", async () => {
    renderEdit();
    // Edit the summary (makes the form dirty + valid).
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "Reporting eats a whole day every single week" },
    });
    // Add a second department via the pills multi-select (Autocomplete popup —
    // not a modal, so the Save button stays reachable with it open).
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });

    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("pain");
    expect(id).toBe("pain-1");
    expect(patch).toMatchObject({
      summary: "Reporting eats a whole day every single week",
      what: "OPS",
      dimension: "TIME",
      // scope_level is DERIVED: ≥1 department → DEPARTMENT.
      scope_level: "DEPARTMENT",
      notes: "Priority for the VP",
      related_techstack_mention: "Excel",
      source_quote: "We lose five hours every week",
    });
    // M2M list of ids (BOTH departments — accumulation), NO singular FK fields.
    expect(patch.target_departments).toEqual(["1", "2"]);
    expect(patch).not.toHaveProperty("target_department");
    expect(patch).not.toHaveProperty("target_contact");
  });

  it("derived scope: removing every department saves scope_level BUSINESS + empty list", async () => {
    renderEdit(); // PAIN starts with Finance (d1)
    const field = screen.getByTestId("pain-departments-field");
    // Remove the only department via its ×.
    const financeChip = within(field).getByText("Finance").closest(".MuiChip-root");
    fireEvent.click(within(financeChip).getByTestId("CancelIcon"));
    // Make the form dirty via summary so Save is enabled.
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "Company-wide reporting overhead across teams" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [, , patch] = updateSignal.mock.calls[0];
    // 0 departments → BUSINESS (derived), empty list, still no FK.
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
