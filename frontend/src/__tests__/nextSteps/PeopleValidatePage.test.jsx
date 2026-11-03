// frontend/src/__tests__/nextSteps/PeopleValidatePage.test.jsx
//
// Sprint « Cycle de vie des contacts », étape 5 (4) — validating a People
// signal on the Activity Signals band = « true? » + « which stakeholder of the
// DC? »: the row ✓ and the detail's Validate open PeopleValidateFlow (built on
// the generic ResolutionFlow) — Link (a stakeholder of the DC, or the shortcut
// « an account contact »), the exact match « Proposed » and pre-selected, or
// Create a « not linked » stakeholder; the generic validate is never called
// for People of a DC. 8b-1 (PO): WITHOUT a decision cycle, a People is
// validated (true / false) by the generic validate, like any signal; once its
// activity joins a DC, a VALIDATED People without stakeholder carries an
// orange « Link to the deal » action opening the SAME flow (resolve).
// The page, the Signals band, its detail, the flow and the coque are REAL;
// data hooks and API calls are mocked (harness of SignalsBandLock.test.jsx).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";

const mockPush = vi.fn();
let mockActivity;
let mockNextSteps;

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/activities/act-1",
  useSearchParams: () => new URLSearchParams(),
}));
// The coque in push mode (large screen), as in workspaceDrawer tests.
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
vi.mock("@mui/x-date-pickers/DatePicker", () => ({ DatePicker: () => <input /> }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetActivity: () => ({
    activity: mockActivity, activityLoading: false, activityError: null, mutateActivity: vi.fn(),
  }),
  updateActivity: vi.fn(),
  // 5.8d — the creation in the coque.
  createActivity: vi.fn(async () => mockCreateActivityResult),
  createActivityWithEntities: vi.fn(async () => mockCreateActivityResult),
}));
let mockCreateActivityResult = { success: true, data: { id: "act-new" } };
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u-1", first_name: "Yasmine", last_name: "Kawi" }, tenantId: "t-1" }),
  default: () => ({ user: { id: "u-1", first_name: "Yasmine", last_name: "Kawi" }, tenantId: "t-1" }),
}));
// The inline contact sub-form → a one-click save (as in the ActivityModal tests).
vi.mock("sections/accounts/activities/components", async (importOriginal) => ({
  ...(await importOriginal()),
  InlineContactForm: ({ onSave }) => (
    <button type="button" onClick={() => onSave({ first_name: "Isabelle", last_name: "Roux" })}>
      save inline contact
    </button>
  ),
}));
vi.mock("api/aiPipelines/lastRun", () => ({
  useGetLastExtractionRun: () => ({
    lastRun: { id: "run-1" }, latestRun: null, runsByPipeline: {}, mutateLastRun: vi.fn(),
  }),
}));
vi.mock("api/signals/signalCounts", () => ({
  useActivitySignalCounts: () => ({ counts: {}, mutateCounts: vi.fn() }),
}));
// The aggregated endpoint: the next steps for a next-steps query; nothing for
// the Signals band halo (the other types).
const mockMutateList = vi.fn();
let mockOtherSignals = [];
// The real module's other exports (AGGREGATED_URL — read at load time by
// api/aiPipelines/activityExtraction, through the real usePipelineRunner).
vi.mock("api/signals/aggregatedSignals", async (importOriginal) => ({
  ...(await importOriginal()),
  default: (args) => ({
    signals: (args?.signalTypes || []).includes("next-steps") ? mockNextSteps : mockOtherSignals,
    loading: false, error: null, mutate: mockMutateList,
  }),
}));
vi.mock("hooks/usePipelineRunner", async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => ({ state: {} }),
}));
vi.mock("contexts/BreadcrumbContext", () => ({ useBreadcrumb: () => ({ setCrumbs: vi.fn() }) }));
// The REAL header hook (useActivityHeaderProps); the shell renders its info
// items (the "N to validate" counter is one of them).
vi.mock("components/WorkspaceHeader", () => ({
  default: ({ infoItems }) => <div data-testid="header">{infoItems}</div>,
}));
vi.mock("sections/campaigns/CampaignOutcomeModal", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityContextSection", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityPreparationTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityNotesTab", () => ({ default: () => null }));
// The REAL Signals band (ActivitySignalsTab) — the component under test.
// The REAL SignalsHaloBox (the colour rule); the generic HaloBox primitive
// exposes the colour role it receives (the test theme has no customShadows).
vi.mock("components/display/HaloBox", () => ({
  default: ({ color, children, ...rest }) => (
    <div data-testid="halo-box" {...rest} data-halo-color={color || "none"}>{children}</div>
  ),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn(),
}));
let mockDcPeople = [];
let mockPatchResponse = null;
vi.mock("api/signals/signals", async (importOriginal) => ({
  // The real module's other exports (SIGNAL_LIST_ENDPOINTS, read at load time
  // by api/aiPipelines/activityExtraction).
  ...(await importOriginal()),
  useGetSignalChoices: () => ({ choices: {}, choicesLoading: false }),
  validateSignal: vi.fn(async () => ({ success: true })),
  rejectSignal: vi.fn(async () => ({ success: true })),
  reopenSignal: vi.fn(async () => ({ success: true })),
  // 5.5 — the DC People (the People picker) and the PATCH.
  useGetSignalsByAccount: vi.fn(() => ({ signals: mockDcPeople, signalsLoading: false })),
  updateSignal: vi.fn(async (_type, id, payload) => ({
    success: true, data: mockPatchResponse ?? { id, ...payload },
  })),
  // 5.6 — the link candidates and the next step read back from the server.
  useNextStepLinkCandidates: vi.fn(() => ({ candidates: mockCandidates, candidatesLoading: false })),
  getSignal: vi.fn(async () => ({ success: true, data: mockServerNextStep })),
  // 5.7 — the link.
  attachNextStepToActivity: vi.fn(async () => mockAttachResult),
  // 5.8d — the names cited with their account contact (server, TD-279 rule).
  // mockCitedDelayMs > 0: the response arrives that long after the mount.
  useNextStepCitedContacts: vi.fn(() => mockUseCited()),
  // Étape 5 — the People resolution (candidates + resolve).
  usePeopleResolutionCandidates: vi.fn(() => mockResolution),
  resolvePeopleSignal: vi.fn(async () => mockResolveResult),
}));
let mockResolution = { hasCycle: true, stakeholders: [], contacts: [], candidatesLoading: false };
let mockResolveResult = { success: true, data: {} };
let mockCited = [];
let mockCitedDelayMs = 0;
function mockUseCited() {
  const { useState, useEffect } = require("react");
  const [ready, setReady] = useState(mockCitedDelayMs === 0);
  useEffect(() => {
    if (ready) return undefined;
    const t = setTimeout(() => setReady(true), mockCitedDelayMs);
    return () => clearTimeout(t);
  }, [ready]);
  return ready
    ? { citedContacts: mockCited, citedLoading: false }
    : { citedContacts: [], citedLoading: true };
}
let mockAttachResult = { success: true, data: {} };
let mockCandidates = [];
let mockServerNextStep = null;
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionCyclesByAccount: vi.fn(() => ({
    cycles: [{ id: "dc-1", name: "Deal Acme", is_active: true },
             { id: "dc-2", name: "Deal Other", is_active: true }],
    cyclesLoading: false,
  })),
  useGetDecisionStepsByCycle: vi.fn(() => ({
    steps: [
      { id: "step-4", name: "Technical Fit", order: 4 },
      { id: "step-5", name: "Business Case", order: 5 },
    ],
    stepsLoading: false,
  })),
}));
// The real ActivityModal is out of scope; this stand-in exposes what the flow
// relies on: the next step it is pre-filled from, onSuccess then onClose (the
// real modal's order on a successful create), or onClose alone (cancel).
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: ({ open, nextStepSignal, onSuccess, onClose }) =>
    open ? (
      <div data-testid="activity-modal">
        <span data-testid="modal-prefill">{nextStepSignal?.suggested_title ?? ""}</span>
        <button type="button" onClick={() => { onSuccess?.({ id: "act-new" }); onClose(); }}>
          modal-create
        </button>
        <button type="button" onClick={() => onClose()}>modal-cancel</button>
      </div>
    ) : null,
}));
vi.mock("components/signals/SignalEditDrawer", () => ({
  default: ({ open }) => (open ? <div data-testid="legacy-signal-edit-drawer" /> : null),
}));

// The extraction (the shared Run AI action, 5.12 B) is out of scope here —
// covered by NextStepsBandLayoutPage.
vi.mock("sections/activities/workspace/RunAIAnalysisButton", () => ({
  default: () => null,
  RUN_AI_TRIGGER_VARIANTS: { BUTTON: "button", PILL: "pill" },
}));

import ActivityWorkspacePage from "views/activities/workspace";
import { validateSignal, resolvePeopleSignal } from "api/signals/signals";

const render = (ui) => rtlRender(<WorkspaceCoque>{ui}</WorkspaceCoque>);

const PAIN = { id: "p-1", _signalType: "pain", status: "PENDING", summary: "Manual reporting",
               created_at: "2026-10-20T10:00:00Z", source_context: { contacts: [] } };
const PERSON = { id: "ps-1", _signalType: "people", status: "PENDING", full_name: "Marc Dupont",
                 role: "CHAMPION", role_display: "Champion", target_contact: null,
                 target_department: null, created_at: "2026-10-20T10:00:00Z",
                 source_context: { contacts: [] } };

const STAKEHOLDERS = [
  { id: "st-marc", full_name: "marc dupont", contact: null, department: null,
    current_role: "CHAMPION", current_role_display: "Champion", proposed: true },
  { id: "st-ana", full_name: "", contact: { id: "c-ana", first_name: "Ana", last_name: "Lopez" },
    department: null, current_role: null, current_role_display: null, proposed: false },
];
const CONTACTS = [
  { id: "c-zoe", first_name: "Zoe", last_name: "Martin", job_title: "CFO", department: null,
    proposed: false },
];

const withCycle = (signal, cycle) => ({
  ...signal,
  source_context: { ...signal.source_context, decision_cycle: cycle ? { id: cycle, name: "Deal" } : null },
});

const renderPage = ({ cycle = "dc-1", stakeholders = STAKEHOLDERS, contacts = CONTACTS } = {}) => {
  mockActivity = {
    id: "act-1", title: "Atelier", activity_type: "MEETING", status: "COMPLETED",
    account: "acc-1", decision_cycle: cycle, campaign_detail: null,
    sequence_context: { position: 1, total: 1, next_activities: [] },
    next_planned_step: null,
  };
  mockNextSteps = [];
  // The signal's own DC (source_context.decision_cycle, as the server sends).
  mockOtherSignals = [PAIN, withCycle(PERSON, cycle)];
  mockResolution = { hasCycle: Boolean(cycle), stakeholders: cycle ? stakeholders : [],
                     contacts: cycle ? contacts : [], candidatesLoading: false };
  mockResolveResult = { success: true, data: { ...PERSON, status: "VALIDATED", stakeholder: "st-marc" } };
  return render(<ActivityWorkspacePage />);
};

const rowOf = (text) => screen.getByText(text).closest('[data-testid="signal-line"]');
const personRow = () => rowOf("Marc Dupont");
const openFlowFromRow = async () => {
  fireEvent.click(within(personRow()).getByLabelText("Validate signal"));
  return screen.findByTestId("people-validate-flow");
};
const next = (flow) => fireEvent.click(within(flow).getByRole("button", { name: "Next" }));
const confirm = (flow) => fireEvent.click(within(flow).getByRole("button", { name: "Confirm" }));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("People validation = signal → stakeholder (étape 5)", () => {
  it("the row ✓ opens the People flow, never the generic validate", async () => {
    renderPage();
    const flow = await openFlowFromRow();
    expect(within(flow).getByText(/Who is this person in the decision cycle\?/)).toBeInTheDocument();
    expect(validateSignal).not.toHaveBeenCalled();
  });

  it("the detail's Validate opens the People flow too", async () => {
    renderPage();
    fireEvent.click(personRow());
    const coque = await screen.findByTestId("coque-panel");
    fireEvent.click(within(coque).getByRole("button", { name: /Validate/ }));
    expect(await screen.findByTestId("people-validate-flow")).toBeInTheDocument();
    expect(validateSignal).not.toHaveBeenCalled();
  });

  it("Link: the exact match is « Proposed » and pre-selected; Confirm resolves to it", async () => {
    renderPage();
    const flow = await openFlowFromRow();
    fireEvent.click(within(flow).getByLabelText("Link to an existing stakeholder or contact"));
    next(flow);
    const list = await within(flow).findByTestId("people-candidates");
    expect(within(within(list).getByTestId("people-candidate-st-marc")).getByText("Proposed")).toBeInTheDocument();
    expect(within(within(list).getByTestId("people-candidate-st-ana")).queryByText("Proposed")).toBeNull();
    expect(within(list).getByLabelText("Select marc dupont")).toBeChecked();
    confirm(flow);
    await waitFor(() => expect(resolvePeopleSignal).toHaveBeenCalledWith("ps-1", { stakeholder_id: "st-marc" }));
  });

  it("Link: an account contact is the shortcut (contact_id)", async () => {
    renderPage();
    const flow = await openFlowFromRow();
    fireEvent.click(within(flow).getByLabelText("Link to an existing stakeholder or contact"));
    next(flow);
    const list = await within(flow).findByTestId("people-candidates");
    expect(within(list).getByTestId("people-candidate-c-zoe")).toHaveTextContent("Account contact");
    fireEvent.click(within(list).getByLabelText("Select Zoe Martin"));
    confirm(flow);
    await waitFor(() => expect(resolvePeopleSignal).toHaveBeenCalledWith("ps-1", { contact_id: "c-zoe" }));
  });

  it("Create: a « not linked » stakeholder, the name pre-filled from the signal", async () => {
    renderPage();
    const flow = await openFlowFromRow();
    fireEvent.click(within(flow).getByLabelText("Create a new stakeholder"));
    next(flow);
    expect(within(flow).getByLabelText("Name")).toHaveValue("Marc Dupont");
    confirm(flow);
    await waitFor(() =>
      expect(resolvePeopleSignal).toHaveBeenCalledWith("ps-1", { create: { full_name: "Marc Dupont" } }),
    );
  });

  it("Create with an empty name and no department cannot be confirmed", async () => {
    renderPage();
    const flow = await openFlowFromRow();
    fireEvent.click(within(flow).getByLabelText("Create a new stakeholder"));
    next(flow);
    fireEvent.change(within(flow).getByLabelText("Name"), { target: { value: "  " } });
    expect(within(flow).getByRole("button", { name: "Confirm" })).toBeDisabled();
  });

  it("no candidate at all: Link is disabled, Create stays", async () => {
    renderPage({ stakeholders: [], contacts: [] });
    const flow = await openFlowFromRow();
    expect(within(flow).getByLabelText("Link to an existing stakeholder or contact")).toBeDisabled();
    expect(within(flow).getByLabelText("Create a new stakeholder")).not.toBeDisabled();
  });

  it("the other signal types keep the generic validate", async () => {
    renderPage();
    fireEvent.click(within(rowOf("Manual reporting")).getByLabelText("Validate signal"));
    await waitFor(() => expect(validateSignal).toHaveBeenCalledWith("pain", "p-1"));
    expect(screen.queryByTestId("people-validate-flow")).toBeNull();
  });
});

describe("People without a decision cycle — validated like any signal (8b-1)", () => {
  it("the row ✓ is enabled and validates directly (generic validate, no flow)", async () => {
    renderPage({ cycle: null });
    const button = within(personRow()).getByLabelText("Validate signal");
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    await waitFor(() => expect(validateSignal).toHaveBeenCalledWith("people", "ps-1"));
    expect(screen.queryByTestId("people-validate-flow")).toBeNull();
    expect(resolvePeopleSignal).not.toHaveBeenCalled();
    expect(screen.queryByText(/Validable once/)).toBeNull();
  });

  it("the detail's Validate validates directly too, no mention", async () => {
    renderPage({ cycle: null });
    fireEvent.click(personRow());
    const coque = await screen.findByTestId("coque-panel");
    const validate = within(coque).getByRole("button", { name: /Validate/ });
    expect(validate).not.toBeDisabled();
    expect(within(coque).queryByText(/Validable once/)).toBeNull();
    fireEvent.click(validate);
    await waitFor(() => expect(validateSignal).toHaveBeenCalledWith("people", "ps-1"));
  });
});

describe("« Link to the deal » — a validated People without stakeholder, once in a DC (8b-1)", () => {
  const renderValidated = ({ cycle = "dc-1", stakeholder = null } = {}) => {
    renderPage({ cycle });
    mockOtherSignals = [PAIN, withCycle({ ...PERSON, status: "VALIDATED", stakeholder }, cycle)];
    cleanup();
    return render(<ActivityWorkspacePage />);
  };
  // The Validated section is folded by default (SignalsValidationList).
  const linkAction = () => {
    if (!screen.queryByText("Marc Dupont")) fireEvent.click(screen.getByText("Validated"));
    return within(personRow()).queryByRole("button", { name: "Link to the deal" });
  };

  it("the row carries « Link to the deal »; it opens the SAME People flow and resolves", async () => {
    renderValidated();
    fireEvent.click(linkAction());
    const flow = await screen.findByTestId("people-validate-flow");
    fireEvent.click(within(flow).getByLabelText("Create a new stakeholder"));
    next(flow);
    confirm(flow);
    await waitFor(() =>
      expect(resolvePeopleSignal).toHaveBeenCalledWith("ps-1", { create: { full_name: "Marc Dupont" } }),
    );
    expect(validateSignal).not.toHaveBeenCalled();
  });

  // 8c-1 (PO): the « Validated » section OPENS by itself when it holds a
  // People to link (VALIDATED, with a DC, no stakeholder); else folded.
  it("the Validated section opens by itself when a People needs « Link to the deal »", () => {
    renderValidated();
    expect(screen.getByText("Marc Dupont")).toBeInTheDocument();          // no click
    expect(within(personRow()).getByRole("button", { name: "Link to the deal" })).toBeInTheDocument();
  });

  it("otherwise it stays folded (a People already affiliated)", () => {
    renderValidated({ stakeholder: "st-marc" });
    expect(screen.queryByText("Marc Dupont")).toBeNull();
    expect(screen.getByText("Validated")).toBeInTheDocument();
  });

  it("it opens when a revalidation brings a People to link (Start Decision Cycle)", () => {
    const view = renderValidated({ cycle: null });                     // no DC yet: folded
    expect(screen.queryByText("Marc Dupont")).toBeNull();
    mockOtherSignals = [PAIN, withCycle({ ...PERSON, status: "VALIDATED", stakeholder: null }, "dc-1")];
    view.rerender(<WorkspaceCoque><ActivityWorkspacePage /></WorkspaceCoque>);
    expect(screen.getByText("Marc Dupont")).toBeInTheDocument();
  });

  it("no action for a People already affiliated, nor without a DC, nor still pending", async () => {
    renderValidated({ stakeholder: "st-marc" });
    expect(linkAction()).toBeNull();
    cleanup();
    renderValidated({ cycle: null });
    expect(linkAction()).toBeNull();
    cleanup();
    renderPage();                                   // PENDING in a DC: the ✓ + flow
    expect(linkAction()).toBeNull();
  });
});
