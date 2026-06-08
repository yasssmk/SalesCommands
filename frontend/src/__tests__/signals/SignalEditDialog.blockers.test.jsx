// frontend/src/__tests__/signals/SignalEditDialog.blockers.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true, data: {} })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: ({ value, onChange, label }) => (
    <div data-testid="contact-select">
      <label>{label}</label>
      <span>{value ? `${value.first_name} ${value.last_name}` : "none"}</span>
    </div>
  ),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import SignalEditDialog from "sections/activities/signals/SignalEditDialog";
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

describe("SignalEditDialog — blockers type", () => {
  it("renders BlockerEditForm with blocker initial values", () => {
    render(
      <SignalEditDialog
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

    expect(screen.getByText("Edit Blocker Signal")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Budget frozen until Q1")).toBeInTheDocument();
    expect(screen.getByTestId("contact-select")).toBeInTheDocument();
  });

  it("submits PATCH with updated summary", async () => {
    const onSuccess = vi.fn();
    const onClose = vi.fn();

    render(
      <SignalEditDialog
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
      <SignalEditDialog
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
});
