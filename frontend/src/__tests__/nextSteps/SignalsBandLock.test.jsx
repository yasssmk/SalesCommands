// frontend/src/__tests__/nextSteps/SignalsBandLock.test.jsx
//
// Sprint Next steps 5.11 — the Signals band follows the Next steps band's lock
// rule, through ONE shared predicate (utils/activitySignalsLock.js,
// isActivitySignalsLocked): a COMPLETED activity stays workable on the
// signals side (the row ✓ / ✗, the detail's Validate / Reject); ONLY a
// CANCELLED activity locks. Before 5.11 the page locked the band on
// COMPLETED too (views/activities/workspace/index.jsx, isLocked) — for the
// detail only: the row ✓ / ✗ ignored any lock, even CANCELLED.
// The page, the Signals band (ActivitySignalsTab, SignalsValidationList,
// SignalLine), its detail and the coque are REAL; data hooks, API calls and
// the other bands are mocked.

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
}));
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

import ActivityWorkspacePage from "views/activities/workspace";
import { isActivitySignalsLocked, ACTIVITY_SIGNALS_LOCKED_STATUSES } from "utils/activitySignalsLock";
import * as NextStepsTabModule from "sections/activities/workspace/ActivityNextStepsTab";

const render = (ui) => rtlRender(<WorkspaceCoque>{ui}</WorkspaceCoque>);

const PAIN = { id: "p-1", _signalType: "pain", status: "PENDING", summary: "Manual reporting",
               created_at: "2026-10-20T10:00:00Z", source_context: { contacts: [] } };

const activityWith = (status) => ({
  id: "act-1", title: "Atelier", activity_type: "MEETING", status,
  account: "acc-1", decision_cycle: "dc-1", campaign_detail: null,
  sequence_context: { position: 1, total: 1, next_activities: [] },
  next_planned_step: null,
});

const renderPage = (status) => {
  mockActivity = activityWith(status);
  mockNextSteps = [];
  mockOtherSignals = [PAIN];
  return render(<ActivityWorkspacePage />);
};

const painRow = () => screen.getByText("Manual reporting").closest('[data-testid="signal-line"]');
const openDetail = async () => {
  fireEvent.click(painRow());
  return screen.findByTestId("coque-panel");
};

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("Signals band lock — ONLY CANCELLED locks (5.11)", () => {
  it("COMPLETED: the row ✓ / ✗ are offered", () => {
    renderPage("COMPLETED");
    expect(within(painRow()).getByLabelText("Validate signal")).toBeInTheDocument();
    expect(within(painRow()).getByLabelText("Reject signal")).toBeInTheDocument();
  });

  it("COMPLETED: the detail offers Validate / Reject", async () => {
    renderPage("COMPLETED");
    const coque = await openDetail();
    expect(within(coque).getByRole("button", { name: /Validate/ })).toBeInTheDocument();
    expect(within(coque).getByRole("button", { name: /Reject/ })).toBeInTheDocument();
  });

  it("CANCELLED: no row ✓ / ✗", () => {
    renderPage("CANCELLED");
    expect(within(painRow()).queryByLabelText("Validate signal")).toBeNull();
    expect(within(painRow()).queryByLabelText("Reject signal")).toBeNull();
  });

  it("CANCELLED: the detail is read-only (no Validate / Reject)", async () => {
    renderPage("CANCELLED");
    const coque = await openDetail();
    expect(within(coque).queryByRole("button", { name: /Validate/ })).toBeNull();
    expect(within(coque).queryByRole("button", { name: /Reject/ })).toBeNull();
  });

  it("PLANNED: workable, as before", () => {
    renderPage("PLANNED");
    expect(within(painRow()).getByLabelText("Validate signal")).toBeInTheDocument();
  });
});

describe("ONE shared predicate for the two bands (5.11)", () => {
  it("the constant: CANCELLED only", () => {
    expect(ACTIVITY_SIGNALS_LOCKED_STATUSES).toEqual(["CANCELLED"]);
  });

  it("no duplicate: the Next steps band no longer carries its own rule", () => {
    expect(NextStepsTabModule.isNextStepsBandLocked).toBeUndefined();
    expect(NextStepsTabModule.NEXT_STEPS_LOCKED_STATUSES).toBeUndefined();
  });

  it("the predicate: CANCELLED locks, COMPLETED / PLANNED do not", () => {
    expect(isActivitySignalsLocked({ status: "CANCELLED" })).toBe(true);
    expect(isActivitySignalsLocked({ status: "COMPLETED" })).toBe(false);
    expect(isActivitySignalsLocked({ status: "PLANNED" })).toBe(false);
  });
});
