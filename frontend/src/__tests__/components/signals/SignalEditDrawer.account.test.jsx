// frontend/src/__tests__/components/signals/SignalEditDrawer.account.test.jsx
//
// Proves the context divergence the unified drawer must preserve:
//   - context="activity" mounts the ACTIVITY (implicit-source) form and
//     normalizes target_contact only.
//   - context="account" mounts the ACCOUNT (explicit-source) form — the one
//     that renders the source pickers — and normalizes source_contact too.
//
// Forms are mocked to identifiable stubs so the drawer's own responsibilities
// (context routing + contact normalization) are asserted deterministically.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";

const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true, data: {} })),
  reopenSignal: vi.fn(() => Promise.resolve({ success: true, data: {} })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("sections/activities/signals/signalValidationRules", () => ({
  getMissingFields: vi.fn(() => []),
}));

vi.mock("components/signals/SignalIncompleteAlert", () => ({
  default: () => null,
}));

vi.mock(
  "sections/activities/signals/wizard/forms/buildEditInitialValues",
  () => ({ buildEditInitialValues: vi.fn(() => ({})) }),
);
vi.mock(
  "sections/accounts/signals/wizard/forms/buildEditInitialValues",
  () => ({ buildEditInitialValues: vi.fn(() => ({})) }),
);

// Activity pain form: implicit source — emits only target_contact (as object).
vi.mock("sections/activities/signals/wizard/forms/InlinePainForm", () => ({
  default: ({ onAdd }) => (
    <button
      data-testid="act-pain-form"
      onClick={() => onAdd({ summary: "x", target_contact: { id: "t1" } })}
    >
      save-act
    </button>
  ),
}));

// Account pain form: explicit source — emits source_contact + target_contact.
vi.mock("sections/accounts/signals/wizard/forms/InlinePainForm", () => ({
  default: ({ onAdd }) => (
    <button
      data-testid="acc-pain-form"
      onClick={() =>
        onAdd({
          summary: "x",
          source_contact: { id: "s1" },
          target_contact: { id: "t1" },
        })
      }
    >
      save-acc
    </button>
  ),
}));

// Other mounted forms stubbed out (module import side only).
vi.mock("sections/activities/signals/wizard/forms/InlineObjectiveForm", () => ({ default: () => null }));
vi.mock("sections/activities/signals/wizard/forms/InlineImpactForm", () => ({ default: () => null }));
vi.mock("sections/activities/signals/wizard/forms/InlineTechStackForm", () => ({ default: () => null }));
vi.mock("sections/activities/signals/BlockerEditForm", () => ({ default: () => null }));
vi.mock("sections/activities/signals/NextStepEditForm", () => ({ default: () => null }));
vi.mock("sections/accounts/signals/wizard/forms/InlineObjectiveForm", () => ({ default: () => null }));
vi.mock("sections/accounts/signals/wizard/forms/InlineTechStackForm", () => ({ default: () => null }));

// ==============================|| IMPORTS (after mocks) ||============================== //

import SignalEditDrawer from "components/signals/SignalEditDrawer";
import { updateSignal } from "api/signals/signals";

const BASE = {
  open: true,
  onClose: vi.fn(),
  onSuccess: vi.fn(),
  signal: { id: "p1", status: "PENDING" },
  signalType: "pain",
  accountId: "acc-1",
  choices: {},
  choicesLoading: false,
};

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

// ==============================|| TESTS ||============================== //

describe("SignalEditDrawer — context routing", () => {
  it("activity context mounts the implicit-source form", () => {
    render(<SignalEditDrawer {...BASE} context="activity" />);
    expect(screen.getByTestId("act-pain-form")).toBeInTheDocument();
    expect(screen.queryByTestId("acc-pain-form")).not.toBeInTheDocument();
  });

  it("account context mounts the explicit-source form (with the source pickers)", () => {
    render(<SignalEditDrawer {...BASE} context="account" />);
    expect(screen.getByTestId("acc-pain-form")).toBeInTheDocument();
    expect(screen.queryByTestId("act-pain-form")).not.toBeInTheDocument();
  });
});

describe("SignalEditDrawer — contact normalization by context", () => {
  it("activity: normalizes target_contact; no source_contact in payload", async () => {
    render(<SignalEditDrawer {...BASE} context="activity" />);
    fireEvent.click(screen.getByTestId("act-pain-form"));

    await waitFor(() => expect(updateSignal).toHaveBeenCalled());
    const [, , payload] = updateSignal.mock.calls[0];
    expect(payload.target_contact).toBe("t1");
    expect(payload).not.toHaveProperty("source_contact");
  });

  it("account: normalizes BOTH source_contact and target_contact to UUIDs", async () => {
    render(<SignalEditDrawer {...BASE} context="account" />);
    fireEvent.click(screen.getByTestId("acc-pain-form"));

    await waitFor(() => expect(updateSignal).toHaveBeenCalled());
    const [, , payload] = updateSignal.mock.calls[0];
    expect(payload.source_contact).toBe("s1");
    expect(payload.target_contact).toBe("t1");
  });
});
