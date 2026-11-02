// frontend/src/__tests__/sections/activities/workspace/EditTechStackContent.scope.test.jsx
//
// Sprint « Cycle de vie des contacts », étape 2b (2) — the SCOPE of a tech
// stack is editable in the Activity edit drawer: §1 Technology carries two
// EXCLUSIVE pills « Account-wide » / « This deal » (labels from the
// /signals/choices/ tech_scopes), never deselectable (scope is NOT NULL);
// a signal without scope (older payload) reads ACCOUNT; the payload carries
// `scope`.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, within } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: vi.fn(() => ({
    choices: {
      usage_scopes: [
        { value: "DEPARTMENT", label: "Department" },
        { value: "COMPANY", label: "Company" },
        { value: "UNKNOWN", label: "Unknown" },
      ],
      // Real /signals/choices/ tech_scopes (backend TechScope, étape 2b).
      tech_scopes: [
        { value: "ACCOUNT", label: "Account-wide" },
        { value: "DEAL", label: "This deal" },
      ],
    },
    choicesLoading: false,
  })),
}));
vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: vi.fn(() => ({ standardDepartments: [{ value: 5, label: "Sales" }] })),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
vi.mock("@mui/x-date-pickers/DatePicker", () => ({ DatePicker: () => null }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer: vi.fn(), openDrawer: vi.fn() }),
}));

import EditTechStackContent from "sections/activities/workspace/EditTechStackContent";
import { updateSignal } from "api/signals/signals";

const TECH = {
  id: "ts-1",
  status: "PENDING",
  tech_name: "HubSpot",
  scope: "ACCOUNT",
  scope_display: "Account-wide",
  usage_scope: "COMPANY",
  usage_scope_display: "Company",
  usage_departments: [],
  usage_start_year: null,
  renewal_date: null,
  cost_description: "",
  is_discontinued: false,
  discontinued_date: null,
  notes: "",
  source_quote: "We use HubSpot.",
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

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditTechStackContent — scope (étape 2b)", () => {
  it("§1 shows the two scope pills with the choices labels, the current one pressed", () => {
    renderEdit();
    const pills = screen.getByTestId("techstack-tech-scope-pills");
    expect(within(pills).getAllByRole("button")).toHaveLength(2);
    expect(screen.getByTestId("tech-scope-pill-ACCOUNT")).toHaveTextContent("Account-wide");
    expect(screen.getByTestId("tech-scope-pill-DEAL")).toHaveTextContent("This deal");
    expect(screen.getByTestId("tech-scope-pill-ACCOUNT")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("tech-scope-pill-DEAL")).toHaveAttribute("aria-pressed", "false");
  });

  it("a signal without scope (older payload) reads Account-wide", () => {
    const { scope, scope_display, ...legacy } = TECH;
    renderEdit({ ...legacy, id: "ts-legacy" });
    expect(screen.getByTestId("tech-scope-pill-ACCOUNT")).toHaveAttribute("aria-pressed", "true");
  });

  it("choosing « This deal » sends scope DEAL and returns its label", async () => {
    const onSaved = vi.fn();
    renderEdit(TECH, { onSaved });
    fireEvent.click(screen.getByTestId("tech-scope-pill-DEAL"));
    await save();
    expect(updateSignal).toHaveBeenCalledWith(
      "tech-stack", "ts-1", expect.objectContaining({ scope: "DEAL" }),
    );
    expect(onSaved).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "DEAL", scope_display: "This deal" }),
    );
  });

  it("a click on the ACTIVE pill never deselects it (scope is never empty)", async () => {
    renderEdit({ ...TECH, id: "ts-deal", scope: "DEAL", scope_display: "This deal" });
    fireEvent.click(screen.getByTestId("tech-scope-pill-DEAL"));
    expect(screen.getByTestId("tech-scope-pill-DEAL")).toHaveAttribute("aria-pressed", "true");
  });

  it("the payload always carries the scope (unchanged ACCOUNT included)", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-notes"));
    fireEvent.change(screen.getByTestId("inline-input-notes"), { target: { value: "x" } });
    await save();
    expect(updateSignal).toHaveBeenCalledWith(
      "tech-stack", "ts-1", expect.objectContaining({ scope: "ACCOUNT" }),
    );
  });
});
