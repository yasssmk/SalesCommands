// frontend/src/__tests__/sections/activities/workspace/EditImpactContent.test.jsx
//
// S3 — the Impact EDIT drawer, a mirror of EditPainContent on the standard
// chassis. Fields are InlineEditableValue (double-click). Scope is IDENTICAL to
// Pain: two EXCLUSIVE pills Company | Department, "+ add department" multi-select
// (deletable pills), scope_level EXPLICIT, payload derives target_departments
// from scope (Company → []). Save PATCHes via updateSignal("impact", id, payload)
// with ONLY Impact's writable fields — Metrics (impact_type/metric_text), NO FK,
// NO notes / related_techstack_mention. human_impact is no longer edited on the
// Activity surface and is OMITTED from the payload (non-destructive: the stored
// value is left untouched).

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
    ["summary", "what", "dimension", "impact_type", "metric_text", "source_quote"].forEach(
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
    expect(screen.getByText("The type of impact and its concrete consequences.")).toBeInTheDocument();
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
    expect(screen.getByText("5 hours per week")).toBeInTheDocument();
  });

  it("S5b (Voie B): the impact_type select carries an empty option '—' to clear it", () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-impact_type"));
    fireEvent.mouseDown(screen.getByRole("combobox"));
    expect(screen.getByRole("option", { name: "—" })).toBeInTheDocument();
    // Enum options still offered alongside the empty one.
    expect(screen.getByRole("option", { name: "Financial" })).toBeInTheDocument();
  });

  it("S5b (Voie B): clearing impact_type to '—' SENDS impact_type: '' (real clearing, not omitted)", async () => {
    renderEdit(); // IMPACT starts with impact_type "TIME"
    // Enter edit on impact_type, open the select, pick the empty option.
    fireEvent.doubleClick(screen.getByTestId("inline-read-impact_type"));
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(screen.getByRole("option", { name: "—" }));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [, , patch] = updateSignal.mock.calls[0];
    // Voie B: the key IS present and empty (real clearing), never omitted.
    expect(patch).toHaveProperty("impact_type", "");
  });

  it("S5b: onSaved reflects the cleared impact_type (empty display) for the detail's 'No metric defined'", async () => {
    const onSaved = vi.fn();
    renderEdit(IMPACT, { onSaved });
    fireEvent.doubleClick(screen.getByTestId("inline-read-impact_type"));
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(screen.getByRole("option", { name: "—" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(onSaved.mock.calls[0][0].impact_type).toBe("");
    expect(onSaved.mock.calls[0][0].impact_type_display).toBeNull();
  });

  it("Metrics simplify (a): NO human_impact field; metric_text is 'Describe the impact' + persistent help", () => {
    renderEdit(); // IMPACT carries human_impact "FRUSTRATION" — still not rendered.
    expect(screen.queryByTestId("inline-read-human_impact")).not.toBeInTheDocument();
    expect(screen.queryByText("Human impact")).not.toBeInTheDocument();
    expect(screen.queryByText("Frustration")).not.toBeInTheDocument();
    // metric_text relabelled + a persistent descriptive help (not an error).
    expect(screen.getByText("Describe the impact")).toBeInTheDocument();
    expect(
      screen.getByText("Be specific about the consequences, with numbers whenever possible"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Metric")).not.toBeInTheDocument();
    // The help stays visible while editing the field.
    fireEvent.doubleClick(screen.getByTestId("inline-read-metric_text"));
    expect(screen.getByTestId("inline-input-metric_text")).toBeInTheDocument();
    expect(
      screen.getByText("Be specific about the consequences, with numbers whenever possible"),
    ).toBeInTheDocument();
  });

  it("Metrics simplify (b): Save OMITS human_impact from the payload (non-destructive)", async () => {
    renderEdit(); // IMPACT carries human_impact "FRUSTRATION"
    // Dirty the form (Save is disabled on a pristine form).
    fireEvent.doubleClick(screen.getByTestId("inline-read-metric_text"));
    fireEvent.change(screen.getByTestId("inline-input-metric_text"), {
      target: { value: "5 hours per week — 260 hours a year" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, , patch] = updateSignal.mock.calls[0];
    expect(type).toBe("impact");
    expect(patch).not.toHaveProperty("human_impact");
    // metric_text still sent.
    expect(patch).toHaveProperty("metric_text", "5 hours per week — 260 hours a year");
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
    });
    expect(patch).not.toHaveProperty("human_impact");
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
      // human_impact is not edited here → the pre-edit value is carried through
      // untouched by the spread (non-destructive).
      human_impact: "FRUSTRATION",
    });
    expect(onSaved.mock.calls[0][0].target_departments).toEqual([{ id: "1", name: "Finance" }]);
    expect(closeDrawer).not.toHaveBeenCalled();
  });
});
