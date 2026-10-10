// frontend/src/__tests__/signals/SignalEditDrawer.blockers.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";

const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true, data: {} })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// The picker stub mirrors AsyncContactSelect's contract: onChange(event, contact).
// It exposes the props it receives (filters, a leaked accountId) so the tests
// can assert what would reach the underlying Autocomplete / DOM.
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: ({ value, onChange, label, filters, ...rest }) => (
    <div
      data-testid="contact-select"
      data-filters={JSON.stringify(filters ?? null)}
      data-leaked-account-id={rest.accountId === undefined ? "none" : String(rest.accountId)}
    >
      <label>{label}</label>
      <span>{value ? `${value.first_name} ${value.last_name}` : "none"}</span>
      <button
        type="button"
        onClick={(e) =>
          onChange(e, { id: "c-new", first_name: "Nina", last_name: "Newman", job_title: "COO" })
        }
      >
        pick contact
      </button>
      <button type="button" onClick={(e) => onChange(e, null)}>
        clear contact
      </button>
    </div>
  ),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import SignalEditDrawer from "components/signals/SignalEditDrawer";
import { updateSignal } from "api/signals/signals";
import { displaySuccessSnackbar } from "utils/displayError";

// ==============================|| TESTS ||============================== //

const MOCK_BLOCKER = {
  id: "b1",
  status: "PENDING",
  summary: "Budget frozen until Q1",
  contact: { id: "c1", first_name: "Pierre", last_name: "Dupont" },
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("SignalEditDrawer — blockers type", () => {
  it("renders BlockerEditForm with blocker initial values", () => {
    render(
      <SignalEditDrawer
        open={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        signal={MOCK_BLOCKER}
        signalType="blockers"
        accountId="acc-1"
        choices={{}}
        choicesLoading={false}
      />,
    );

    // Objection S4: the title reads the canonical type label (central constant).
    expect(screen.getByText("Edit Objection Signal")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Budget frozen until Q1")).toBeInTheDocument();
    expect(screen.getByTestId("contact-select")).toBeInTheDocument();
  });

  it("submits PATCH with updated summary", async () => {
    const onSuccess = vi.fn();
    const onClose = vi.fn();

    render(
      <SignalEditDrawer
        open={true}
        onClose={onClose}
        onSuccess={onSuccess}
        signal={MOCK_BLOCKER}
        signalType="blockers"
        accountId="acc-1"
        choices={{}}
        choicesLoading={false}
      />,
    );

    const summaryInput = screen.getByDisplayValue("Budget frozen until Q1");
    fireEvent.change(summaryInput, { target: { value: "Budget frozen until Q2" } });

    const saveButton = screen.getByRole("button", { name: /save changes/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(updateSignal).toHaveBeenCalledWith("blockers", "b1", {
        summary: "Budget frozen until Q2",
        contact: "c1",
      });
      expect(displaySuccessSnackbar).toHaveBeenCalled();
      expect(onSuccess).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("renders cancel button that closes dialog", () => {
    const onClose = vi.fn();
    render(
      <SignalEditDrawer
        open={true}
        onClose={onClose}
        onSuccess={vi.fn()}
        signal={MOCK_BLOCKER}
        signalType="blockers"
        accountId="acc-1"
        choices={{}}
        choicesLoading={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });

  // ==== Objection S4 — TD-251: picker contract (_event, contact) + account scope ====

  const renderBlockerDrawer = (props = {}) =>
    render(
      <SignalEditDrawer
        open={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        signal={MOCK_BLOCKER}
        signalType="blockers"
        accountId="acc-1"
        choices={{}}
        choicesLoading={false}
        {...props}
      />,
    );

  it("TD-251: picking a contact (onChange(event, contact)) → PATCH contact = its UUID", async () => {
    renderBlockerDrawer();
    fireEvent.click(screen.getByRole("button", { name: "pick contact" }));
    expect(screen.getByTestId("contact-select")).toHaveTextContent("Nina Newman");
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    await waitFor(() => {
      expect(updateSignal).toHaveBeenCalledWith("blockers", "b1", {
        summary: "Budget frozen until Q1",
        contact: "c-new",
      });
    });
  });

  it("TD-251: clearing the contact → PATCH contact = null", async () => {
    renderBlockerDrawer();
    fireEvent.click(screen.getByRole("button", { name: "clear contact" }));
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    await waitFor(() => {
      expect(updateSignal).toHaveBeenCalledWith("blockers", "b1", {
        summary: "Budget frozen until Q1",
        contact: null,
      });
    });
  });

  it("TD-251: the picker is scoped to the account — filters={{ account_id }}", () => {
    renderBlockerDrawer();
    expect(JSON.parse(screen.getByTestId("contact-select").dataset.filters)).toEqual({
      account_id: "acc-1",
    });
  });

  it("TD-251: no accountId prop reaches the picker (would be spread to the DOM)", () => {
    renderBlockerDrawer();
    expect(screen.getByTestId("contact-select").dataset.leakedAccountId).toBe("none");
  });
});
