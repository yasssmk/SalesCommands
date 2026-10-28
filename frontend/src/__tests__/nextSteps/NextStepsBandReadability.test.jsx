// frontend/src/__tests__/nextSteps/NextStepsBandReadability.test.jsx
//
// Sprint Next steps 5.8f — READABILITY of the "Next steps" band, on the Activity
// workspace PAGE as really rendered (views/activities/workspace/index.jsx):
//   * two sub-blocks, clearly separated: "Next planned step" (+ the "+ Add next
//     step" pill on its right) then "Suggested next steps" — each with the
//     section header of the Signals band (CollapsibleStrip, the header of its
//     To validate / Validated / Rejected sections);
//   * gone: the Divider, the dashed boxes in raw MUI colours (→ the shared
//     EmptyState, aphoriQ theme), "Create a follow-up to continue.", "… from
//     the Overview tab …", the redundant "Next step" type-group header;
//   * line 2 of a next step = type · action date (PO exception; a next-steps
//     branch of SignalLine, same line template) — 5.8g: no names cited;
//   * the band HALO: the same SignalsHaloBox as the Signals band;
//   * the activity header "N to validate" counter includes the PENDING next
//     steps.
// The band, the header hook, SignalsHaloBox, SignalsValidationList, SignalLine
// and the coque are REAL; data hooks, API calls and the other bands are mocked.

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
vi.mock("sections/activities/workspace/ActivitySignalsTab", () => ({
  default: () => null,
  ACTIVITY_FLAT_TYPES: ["pain"],
}));
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

const render = (ui) => rtlRender(<WorkspaceCoque>{ui}</WorkspaceCoque>);

const nextStep = (over = {}) => ({
  id: "ns-p", _signalType: "next-steps", signal_type: "next-steps", status: "PENDING",
  suggested_title: "Send the DPA", suggested_activity_type: "EMAIL",
  suggested_due_date: "2026-11-03", suggested_date_text: "early November",
  suggested_people: [{ id: "pp-1", full_name: "Isabelle Roux", role: "UNKNOWN", target_contact: null }],
  suggested_people_names: ["Karim"],
  created_at: "2026-10-20T10:00:00Z",
  source_context: { contacts: [{ id: "c-1", first_name: "Thomas", last_name: "Lefèvre", job_title: "CTO" }] },
  linked_activity: null, attached_activity: null, ...over,
});

const NEXT_STEPS = [
  nextStep(),
  nextStep({ id: "ns-v", status: "VALIDATED", suggested_title: "Book the security review" }),
];

const PAIN = { id: "p-1", _signalType: "pain", status: "PENDING", summary: "Manual reporting",
               created_at: "2026-10-20T10:00:00Z", source_context: { contacts: [] } };

const dcActivity = (over = {}) => ({
  id: "act-1", title: "Atelier", activity_type: "MEETING", status: "PLANNED",
  account: "acc-1", decision_cycle: "dc-1", campaign_detail: null,
  sequence_context: { position: 1, total: 1, next_activities: [] },
  next_planned_step: null, ...over,
});

const renderPage = (activity = dcActivity(), nextSteps = NEXT_STEPS, others = []) => {
  mockActivity = activity;
  mockNextSteps = nextSteps;
  mockOtherSignals = others;
  return render(<ActivityWorkspacePage />);
};

// The "Next steps" band: its halo wrapper (5.8f), else its strip.
const band = () => screen.getByTestId("next-steps-halo");
const rowOf = (title) => screen.getByText(title).closest('[data-testid="signal-line"]');
const stripHeaderOf = (title) => screen.getByText(title).closest('[aria-expanded]');

afterEach(() => { cleanup(); vi.clearAllMocks(); });

// ==============================|| TWO SUB-BLOCKS ||============================== //

describe("5.8f — two sub-blocks, the Signals band's section header", () => {
  it("'Next planned step' then 'Suggested next steps', each a CollapsibleStrip header", () => {
    renderPage();
    const planned = stripHeaderOf("Next planned step");
    const suggested = stripHeaderOf("Suggested next steps");
    // The header of the Signals band's sections (To validate…): the same strip.
    const toValidate = stripHeaderOf("To validate");
    [planned, suggested].forEach((h) => {
      expect(h).toHaveAttribute("role", "button");
      expect(h.className).toBe(toValidate.className);
    });
    // In this order, the list inside the second one.
    expect(planned.compareDocumentPosition(suggested) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const suggestedBlock = screen.getByTestId("suggested-next-steps-block");
    expect(within(suggestedBlock).getByText("To validate")).toBeInTheDocument();
    expect(within(screen.getByTestId("next-planned-step-block")).queryByText("To validate")).toBeNull();
  });

  it("the '+ Add next step' pill sits on the right of the 'Next planned step' header", () => {
    renderPage();
    const pill = within(stripHeaderOf("Next planned step")).getByRole("button", { name: "+ Add next step" });
    expect(pill).toHaveAttribute("data-testid", "status-pill");
  });

  it("a click on the pill opens the type row, never folds the sub-block", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "+ Add next step" }));
    expect(stripHeaderOf("Next planned step")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("add-next-step-types")).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("button", { name: "+ Add next step" }), { key: "Enter" });
    expect(stripHeaderOf("Next planned step")).toHaveAttribute("aria-expanded", "true");
  });

  // 5.8g (d) — on a FOLDED sub-block, "+ Add next step" unfolds it (the type
  // row is in its body); on an open one it only toggles the type row.
  it("on a folded 'Next planned step', the pill unfolds it and shows the type row", () => {
    renderPage();
    fireEvent.click(screen.getByText("Next planned step"));
    expect(stripHeaderOf("Next planned step")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByRole("button", { name: "+ Add next step" }));
    expect(stripHeaderOf("Next planned step")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("add-next-step-types")).toBeVisible();
  });

  it("folded after the type row was opened: the pill unfolds it, the row stays open", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "+ Add next step" }));
    fireEvent.click(screen.getByText("Next planned step"));
    fireEvent.click(screen.getByRole("button", { name: "+ Add next step" }));
    expect(stripHeaderOf("Next planned step")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("add-next-step-types")).toBeInTheDocument();
  });

  it("the header still folds / unfolds the sub-block", () => {
    renderPage();
    fireEvent.click(screen.getByText("Next planned step"));
    expect(stripHeaderOf("Next planned step")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByText("Next planned step"));
    expect(stripHeaderOf("Next planned step")).toHaveAttribute("aria-expanded", "true");
  });

  it("outside a DC: 'Next planned step' only (DC-only guard)", () => {
    renderPage(dcActivity({ decision_cycle: null, campaign_detail: { id: "camp-1" } }));
    expect(screen.getByText("Next planned step")).toBeInTheDocument();
    expect(screen.queryByText("Suggested next steps")).toBeNull();
  });
});

// ==============================|| REMOVED ||============================== //

describe("5.8f — removed: Divider, dashed boxes, stale texts, the 'Next step' group header", () => {
  it("no Divider in the band", () => {
    renderPage();
    expect(band().querySelector("hr, .MuiDivider-root")).toBeNull();
  });

  it("no dashed box: the empty next planned step is the shared EmptyState", () => {
    renderPage();
    const empty = within(band()).getByText("No next step planned yet.");
    expect(empty.closest('[data-testid="empty-state"]')).not.toBeNull();
    band().querySelectorAll("*").forEach((el) => {
      expect(getComputedStyle(el).borderStyle).not.toContain("dashed");
    });
    expect(screen.queryByText(/Create a follow-up to continue/)).toBeNull();
  });

  it("an activity in no sequence: the EmptyState, no 'Overview tab' text", () => {
    renderPage(dcActivity({ decision_cycle: null, campaign_detail: null }));
    const empty = within(band()).getByText("No sequence linked.");
    expect(empty.closest('[data-testid="empty-state"]')).not.toBeNull();
    expect(screen.queryByText(/Overview tab/)).toBeNull();
    band().querySelectorAll("*").forEach((el) => {
      expect(getComputedStyle(el).borderStyle).not.toContain("dashed");
    });
  });

  // 5.8g (d) — no suggestion → the shared EmptyState, zero hex colour.
  it("no suggestion: the shared EmptyState, zero hex colour", () => {
    renderPage(dcActivity(), []);
    const block = screen.getByTestId("suggested-next-steps-block");
    const message = within(block).getByText("No next-step suggestions for this activity");
    expect(message.closest('[data-testid="empty-state"]')).not.toBeNull();
    block.querySelectorAll("[style]").forEach((el) => {
      expect(el.getAttribute("style")).not.toMatch(/#[0-9a-f]{3,6}\b|rgb\(140, 140, 140\)/i);
    });
  });

  it("no 'Next step' type-group header over the rows", () => {
    renderPage();
    const block = screen.getByTestId("suggested-next-steps-block");
    expect(within(block).queryByText("Next step")).toBeNull();
    expect(rowOf("Send the DPA")).toBeInTheDocument();
  });
});

// ==============================|| LINE 2 ||============================== //

describe("5.8f/5.8g — line 2 of a next step: type · action date (no names cited)", () => {
  const meta = (title) => within(rowOf(title)).getByTestId("next-step-line-meta");

  it("the type then the due date formatted as elsewhere — nothing else", () => {
    renderPage();
    const m = meta("Send the DPA");
    expect(within(m).getByTestId("next-step-line-type")).toHaveTextContent("Email");
    expect(within(m).getByTestId("next-step-line-date")).toHaveTextContent("3 Nov 2026");
    expect(m.textContent.indexOf("Email")).toBeLessThan(m.textContent.indexOf("3 Nov 2026"));
  });

  it("5.8g — no names cited on the line (the data is there, not shown)", () => {
    renderPage();
    const row = rowOf("Send the DPA");
    expect(within(row).queryByTestId("next-step-line-names")).toBeNull();
    expect(within(row).queryByText(/Isabelle Roux|Karim/)).toBeNull();
  });

  it("not the generic meta: neither the creation date nor the origin contact", () => {
    renderPage();
    const row = rowOf("Send the DPA");
    expect(within(row).queryByText("20 Oct 2026")).toBeNull();
    expect(within(row).queryByText(/Lefèvre/)).toBeNull();
  });

  it("no due date → the date as said; neither → 'Unknown'", () => {
    renderPage(dcActivity(), [
      nextStep({ suggested_due_date: null }),
      nextStep({ id: "ns-2", suggested_title: "Train Karim", suggested_due_date: null,
                 suggested_date_text: "" }),
    ]);
    expect(within(meta("Send the DPA")).getByTestId("next-step-line-date"))
      .toHaveTextContent("“early November”");
    expect(within(meta("Train Karim")).getByTestId("next-step-line-date")).toHaveTextContent("Unknown");
  });

  it("the type label of the surface ('Phone Call')", () => {
    renderPage(dcActivity(), [nextStep({ suggested_activity_type: "CALL" })]);
    expect(within(meta("Send the DPA")).getByTestId("next-step-line-type")).toHaveTextContent("Phone Call");
  });

  it("the same line template: the line-2 meta row of every signal", () => {
    renderPage(dcActivity(), NEXT_STEPS);
    const m = meta("Send the DPA");
    // Line 1 (message) then line 2 (meta), in the same content column.
    const column = within(rowOf("Send the DPA")).getByText("Send the DPA").parentElement.parentElement;
    expect(column.children[1]).toBe(m);
  });
});

// ==============================|| HALO ||============================== //

describe("5.8f — the band halo: the same SignalsHaloBox as the Signals band", () => {
  it(">=1 next step to validate → the warning halo", () => {
    renderPage();
    expect(band()).toHaveAttribute("data-halo-color", "warning");
    expect(within(band()).getByText("Next steps")).toBeInTheDocument();
  });

  it("all processed → the primary halo; none → no halo", () => {
    renderPage(dcActivity(), [nextStep({ status: "VALIDATED" })]);
    expect(band()).toHaveAttribute("data-halo-color", "primary");
    cleanup();
    renderPage(dcActivity(), []);
    expect(band()).toHaveAttribute("data-halo-color", "none");
  });

  it("outside a DC: no halo (the suggestions are not proposed)", () => {
    renderPage(dcActivity({ decision_cycle: null, campaign_detail: { id: "camp-1" } }));
    expect(band()).toHaveAttribute("data-halo-color", "none");
  });

  it("the Signals band halo is unchanged (its own types only)", () => {
    renderPage(dcActivity(), NEXT_STEPS, []);
    const halos = screen.getAllByTestId("signals-halo");
    expect(halos).toHaveLength(1);
    expect(halos[0]).toHaveAttribute("data-halo-color", "none");
  });
});

// ==============================|| HEADER COUNTER ||============================== //

describe("5.8f — the header 'N to validate' counter includes the PENDING next steps", () => {
  const header = () => screen.getByTestId("header");

  it("pending signals + pending next steps", () => {
    renderPage(dcActivity(), NEXT_STEPS, [PAIN]);
    expect(within(header()).getByText("2 to validate")).toBeInTheDocument();
  });

  it("next steps only", () => {
    renderPage(dcActivity(), NEXT_STEPS, []);
    expect(within(header()).getByText("1 to validate")).toBeInTheDocument();
  });

  it("outside a DC: the next steps are not counted", () => {
    renderPage(dcActivity({ decision_cycle: null, campaign_detail: { id: "camp-1" } }), NEXT_STEPS, [PAIN]);
    expect(within(header()).getByText("1 to validate")).toBeInTheDocument();
  });
});
