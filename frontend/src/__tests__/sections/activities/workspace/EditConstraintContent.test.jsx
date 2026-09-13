// frontend/src/__tests__/sections/activities/workspace/EditConstraintContent.test.jsx
//
// S3 — the Constraint EDIT drawer, a mirror of EditImpactContent on the standard
// chassis. Fields: nature (select, REQUIRED) + rigidity (select, OPTIONAL with an
// empty "—" option, clearable) + summary + notes. Scope = Company/Department pills
// as a PURE UI AFFORDANCE (NOT persisted — Constraint has no scope_level); the
// payload emits ONLY target_departments. Save PATCHes updateSignal("constraints",
// id, payload) — front type key is PLURAL.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, within } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: vi.fn(() => ({
    choices: {
      scope_levels: [
        { value: "BUSINESS", label: "Business" },
        { value: "DEPARTMENT", label: "Department" },
      ],
      constraint_natures: [
        { value: "TECHNICAL", label: "Technical" },
        { value: "SECURITY", label: "Security" },
      ],
      rigidities: [
        { value: "FIRM", label: "Firm" },
        { value: "FLEXIBLE", label: "Flexible" },
      ],
    },
    choicesLoading: false,
  })),
}));
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

import EditConstraintContent from "sections/activities/workspace/EditConstraintContent";
import { updateSignal } from "api/signals/signals";

const CONSTRAINT = {
  id: "constraint-1",
  status: "VALIDATED",
  summary: "Must integrate with the existing on-prem SAP install",
  // Raw values (not *_display).
  nature: "TECHNICAL",
  rigidity: "FIRM",
  target_departments: [{ id: "1", name: "Finance" }],
  notes: "Legacy system, migration blocked until 2027",
  source_quote: "It has to work with our SAP box",
};

const renderEdit = (constraint = CONSTRAINT, props = {}) =>
  render(
    <AphoriqTheme>
      <EditConstraintContent constraint={constraint} accountId="acc-1" {...props} />
    </AphoriqTheme>,
  );

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditConstraintContent (S3)", () => {
  it("renders the fields pre-filled + does NOT render its own 'Edit constraint' title", () => {
    renderEdit();
    ["summary", "nature", "rigidity", "notes", "source_quote"].forEach((name) =>
      expect(screen.getByTestId(`inline-read-${name}`)).toBeInTheDocument(),
    );
    expect(screen.getByText("Must integrate with the existing on-prem SAP install")).toBeInTheDocument();
    // nature "TECHNICAL" → "Technical"; rigidity "FIRM" → "Firm".
    expect(within(screen.getByTestId("inline-read-nature")).getByText("Technical")).toBeInTheDocument();
    expect(within(screen.getByTestId("inline-read-rigidity")).getByText("Firm")).toBeInTheDocument();
    // NO what/dimension/metric fields.
    expect(screen.queryByTestId("inline-read-what")).not.toBeInTheDocument();
    expect(screen.queryByTestId("inline-read-dimension")).not.toBeInTheDocument();
    expect(screen.queryByTestId("inline-read-impact_type")).not.toBeInTheDocument();
    expect(screen.queryByText("Edit constraint")).not.toBeInTheDocument();
  });

  it("rigidity select carries an empty option '—' to clear it", () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-rigidity"));
    fireEvent.mouseDown(screen.getByRole("combobox"));
    expect(screen.getByRole("option", { name: "—" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Flexible" })).toBeInTheDocument();
  });

  // ==== Scope affordance (Company/Department, NOT persisted) ====

  it("Department active initially (has a department); pills are exclusive", () => {
    renderEdit();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("scope-pill-BUSINESS")).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    expect(screen.getByTestId("scope-pill-BUSINESS")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "false");
  });

  it("'+ add department' accumulates pills (menu excludes chosen); × removes; Company masks without clearing", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.queryByRole("option", { name: "Finance" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    fireEvent.click(screen.getByTestId("confirm-add-departments"));
    const field = screen.getByTestId("constraint-departments-field");
    expect(within(field).getByText("Finance")).toBeInTheDocument();
    expect(within(field).getByText("Marketing")).toBeInTheDocument();
    // Company masks the field (kept in memory), back to Department restores.
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    expect(screen.queryByTestId("constraint-departments-field")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("scope-pill-DEPARTMENT"));
    expect(within(screen.getByTestId("constraint-departments-field")).getByText("Marketing")).toBeInTheDocument();
    // × removes one.
    fireEvent.click(within(screen.getByTestId("constraint-departments-field")).getByTestId("remove-dept-1"));
    expect(within(screen.getByTestId("constraint-departments-field")).queryByText("Finance")).not.toBeInTheDocument();
  });

  // ==== Save payloads ====

  it("Save PATCHes updateSignal('constraints', …) — Department + 2 depts → {nature, target_departments:[1,2]}, NO scope_level / FK / what / dimension", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    fireEvent.click(screen.getByTestId("confirm-add-departments"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("constraints");
    expect(id).toBe("constraint-1");
    expect(patch).toMatchObject({ nature: "TECHNICAL", rigidity: "FIRM", summary: expect.any(String) });
    expect(patch.target_departments).toEqual(["1", "2"]);
    expect(patch).not.toHaveProperty("scope_level");
    expect(patch).not.toHaveProperty("target_department");
    expect(patch).not.toHaveProperty("what");
    expect(patch).not.toHaveProperty("dimension");
  });

  it("Company scope → target_departments [] (no scope_level)", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.target_departments).toEqual([]);
    expect(patch).not.toHaveProperty("scope_level");
  });

  it("rigidity cleared via '—' → payload rigidity: '' (real clearing)", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-rigidity"));
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(screen.getByRole("option", { name: "—" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    expect(updateSignal.mock.calls[0][2]).toHaveProperty("rigidity", "");
  });

  it("nature is REQUIRED — a constraint with no nature cannot be saved (Yup blocks the PATCH)", async () => {
    renderEdit({ ...CONSTRAINT, nature: "" });
    // Make the form dirty without setting nature (add a department).
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    fireEvent.click(screen.getByTestId("confirm-add-departments"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("Save returns to the detail — onSaved gets the updated signal (rebuilt departments + displays)", async () => {
    const onSaved = vi.fn();
    renderEdit(CONSTRAINT, { onSaved });
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "Must run entirely on the on-premise SAP estate, no cloud" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(onSaved.mock.calls[0][0]).toMatchObject({
      id: "constraint-1",
      nature: "TECHNICAL",
      nature_display: "Technical",
      rigidity_display: "Firm",
    });
    expect(onSaved.mock.calls[0][0].target_departments).toEqual([{ id: "1", name: "Finance" }]);
    expect(closeDrawer).not.toHaveBeenCalled();
  });
});
