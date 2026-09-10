// frontend/src/__tests__/sections/activities/workspace/EditImpactContent.test.jsx
//
// S3 — the Impact EDIT drawer, a mirror of EditPainContent on the standard
// chassis. Fields are InlineEditableValue (double-click). Scope is IDENTICAL to
// Pain: two EXCLUSIVE pills Company | Department, "+ add department" multi-select
// (deletable pills), scope_level EXPLICIT, payload derives target_departments
// from scope (Company → []). Save PATCHes via updateSignal("impact", id, payload)
// with ONLY Impact's writable fields — Metrics (impact_type/metric_text/
// human_impact), NO FK, NO notes / related_techstack_mention.

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
      impact_types: [
        { value: "FINANCIAL", label: "Financial" },
        { value: "TIME", label: "Time impact" },
      ],
      human_impacts: [
        { value: "FRUSTRATION", label: "Frustration" },
        { value: "OVERLOAD", label: "Overload" },
      ],
    },
    choicesLoading: false,
  })),
}));
// Mirror the REAL backend contact-choices shape: department `value` is the
// INTEGER pk, whereas the signal payload carries department ids as STRINGS.
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

import EditImpactContent from "sections/activities/workspace/EditImpactContent";
import { updateSignal } from "api/signals/signals";

const IMPACT = {
  id: "impact-1",
  status: "VALIDATED",
  summary: "Five hours a week lost to manual consolidation",
  what: "OPS",
  dimension: "TIME",
  scope_level: "DEPARTMENT",
  // detail serializer shape: [{id,name}]
  target_departments: [{ id: "1", name: "Finance" }],
  // Metrics (raw values, not *_display).
  impact_type: "TIME",
  metric_text: "5 hours per week",
  human_impact: "FRUSTRATION",
  source_quote: "We lose five hours every week",
};

const renderEdit = (impact = IMPACT, props = {}) =>
  render(
    <AphoriqTheme>
      <EditImpactContent impact={impact} accountId="acc-1" {...props} />
    </AphoriqTheme>,
  );

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditImpactContent (S3)", () => {
  it("renders the editable fields as InlineEditableValue, pre-filled in read mode", () => {
    renderEdit();
    ["summary", "what", "dimension", "impact_type", "metric_text", "human_impact", "source_quote"].forEach(
      (name) => expect(screen.getByTestId(`inline-read-${name}`)).toBeInTheDocument(),
    );
    expect(screen.getByText("Five hours a week lost to manual consolidation")).toBeInTheDocument();
    expect(screen.getByText("We lose five hours every week")).toBeInTheDocument();
    // NO Pain-only fields.
    expect(screen.queryByTestId("inline-read-notes")).not.toBeInTheDocument();
    expect(screen.queryByTestId("inline-read-related_techstack_mention")).not.toBeInTheDocument();
  });

  it("renders the 4 chassis sections incl. Metrics + the Domain × Dimension recap", () => {
    renderEdit();
    expect(screen.getByText("Describe the impact and pick its canonical axes.")).toBeInTheDocument();
    expect(screen.getByText("Company-wide, or one or more departments.")).toBeInTheDocument();
    // The Metrics section (Impact-specific).
    expect(screen.getByText("Metrics")).toBeInTheDocument();
    expect(screen.getByText("The nature of the impact, its metric, and any human dimension.")).toBeInTheDocument();
    expect(screen.getByText("Source quote")).toBeInTheDocument();
    expect(screen.getByText("Operations × Time")).toBeInTheDocument();
    expect(screen.getByText(/impact:OPS:TIME/)).toBeInTheDocument();
  });

  it("does NOT render its own 'Edit impact' title (the coque owns it)", () => {
    renderEdit();
    expect(screen.queryByText("Edit impact")).not.toBeInTheDocument();
  });

  // ==== Metrics section ====

  it("Metrics: impact_type is a select pre-filled with the current value's label", () => {
    renderEdit();
    // impact_type "TIME" → label "Time impact" from the choices mock.
    expect(within(screen.getByTestId("inline-read-impact_type")).getByText("Time impact")).toBeInTheDocument();
    // human_impact "FRUSTRATION" → "Frustration".
    expect(within(screen.getByTestId("inline-read-human_impact")).getByText("Frustration")).toBeInTheDocument();
    expect(screen.getByText("5 hours per week")).toBeInTheDocument();
  });

  it("Metrics: impact_type is REQUIRED — an impact with no impact_type cannot be saved (Yup blocks the PATCH)", async () => {
    renderEdit({ ...IMPACT, impact_type: "" });
    // Make the form dirty WITHOUT fixing impact_type (add a department).
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    fireEvent.click(screen.getByTestId("confirm-add-departments"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    // Yup (impact_type required) blocks submit → no PATCH is sent.
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("human_impact select carries an empty option so it can be cleared", () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-human_impact"));
    // Open the MUI select dropdown to inspect the options.
    fireEvent.mouseDown(screen.getByRole("combobox"));
    expect(screen.getByRole("option", { name: "—" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Frustration" })).toBeInTheDocument();
  });

  // ==== Scope gesture (identical to Pain) ====

  it("shows the two explicit scope pills (Company / Department); DEPARTMENT active", () => {
    renderEdit();
    expect(screen.getByTestId("scope-pill-BUSINESS")).toBeInTheDocument();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toBeInTheDocument();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "true");
  });

  it("Company/Department are EXCLUSIVE — exactly one pill pressed at a time", () => {
    renderEdit();
    const company = () => screen.getByTestId("scope-pill-BUSINESS");
    const dept = () => screen.getByTestId("scope-pill-DEPARTMENT");
    const pressedCount = () =>
      [company(), dept()].filter((el) => el.getAttribute("aria-pressed") === "true").length;

    expect(pressedCount()).toBe(1);
    fireEvent.click(company());
    expect(company()).toHaveAttribute("aria-pressed", "true");
    expect(dept()).toHaveAttribute("aria-pressed", "false");
    expect(pressedCount()).toBe(1);
  });

  it("the '+ add department' menu EXCLUDES already-chosen departments", () => {
    renderEdit(); // Finance (id 1) already chosen
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.queryByRole("option", { name: "Finance" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Marketing" })).toBeInTheDocument();
  });

  it("'+ add department' accumulates chosen departments as pills, × removes one", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    fireEvent.click(screen.getByTestId("confirm-add-departments"));

    const field = screen.getByTestId("impact-departments-field");
    expect(within(field).getByText("Finance")).toBeInTheDocument();
    expect(within(field).getByText("Marketing")).toBeInTheDocument();
    expect(screen.queryByTestId("impact-add-department-picker")).not.toBeInTheDocument();

    fireEvent.click(within(field).getByTestId("remove-dept-1"));
    expect(within(field).queryByText("Finance")).not.toBeInTheDocument();
    expect(within(field).getByText("Marketing")).toBeInTheDocument();
  });

  it("Company pill MASKS the departments field (does not clear) and back restores them", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    expect(screen.queryByTestId("impact-departments-field")).not.toBeInTheDocument();
    // Back to Department → Finance still there.
    fireEvent.click(screen.getByTestId("scope-pill-DEPARTMENT"));
    expect(within(screen.getByTestId("impact-departments-field")).getByText("Finance")).toBeInTheDocument();
  });

  // ==== Save payloads ====

  it("Save PATCHes via updateSignal('impact', ...) — Department + 2 depts → scope DEPARTMENT + [id1,id2], Metrics, NO FK", async () => {
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
    expect(type).toBe("impact");
    expect(id).toBe("impact-1");
    expect(patch).toMatchObject({
      what: "OPS",
      dimension: "TIME",
      scope_level: "DEPARTMENT",
      impact_type: "TIME",
      metric_text: "5 hours per week",
      human_impact: "FRUSTRATION",
    });
    expect(patch.target_departments).toEqual(["1", "2"]);
    // No FK, no Pain-only fields.
    expect(patch).not.toHaveProperty("target_department");
    expect(patch).not.toHaveProperty("target_contact");
    expect(patch).not.toHaveProperty("notes");
    expect(patch).not.toHaveProperty("related_techstack_mention");
  });

  it("Save PATCHes — Company scope → scope BUSINESS + empty list, NO FK", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [, , patch] = updateSignal.mock.calls[0];
    expect(patch.scope_level).toBe("BUSINESS");
    expect(patch.target_departments).toEqual([]);
    expect(patch).not.toHaveProperty("target_department");
  });

  it("Save returns to the detail — onSaved gets the updated signal (rebuilt departments + metric displays), drawer not closed", async () => {
    const onSaved = vi.fn();
    renderEdit(IMPACT, { onSaved });
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "Ten hours a week vanish into manual consolidation work" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(onSaved.mock.calls[0][0]).toMatchObject({
      id: "impact-1",
      summary: "Ten hours a week vanish into manual consolidation work",
      impact_type: "TIME",
      impact_type_display: "Time impact",
      human_impact_display: "Frustration",
    });
    expect(onSaved.mock.calls[0][0].target_departments).toEqual([{ id: "1", name: "Finance" }]);
    expect(closeDrawer).not.toHaveBeenCalled();
  });
});
