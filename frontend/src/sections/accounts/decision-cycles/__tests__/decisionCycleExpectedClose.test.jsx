// frontend/src/sections/accounts/decision-cycles/__tests__/decisionCycleExpectedClose.test.jsx
//
// The DC form's Expected Close Date input — the data-entry surface for the
// manual half of the effective close date.
//
// `expected_close_date` is level 1 of the backend's effective close date
// (decision_cycles/services/close_date_sql.py): set it and it wins, leave it
// blank and the date falls back to the CLOSING step's last activity. That date
// is what puts a deal inside a personal PIPELINE objective's period, so an
// input that does not reach the API means the rep cannot say which period a
// deal belongs to — the reason the objective read 0.
//
// These tests drive the REAL form and assert the PAYLOAD that reaches the API
// client, not the presence of a label: a field rendered but never submitted
// would pass a smoke test and fail the user.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ==============================|| MOCKS ||============================== //

// MainCard pulls the theme config, which calls next/font at import time.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

vi.mock("api/accounts/decisionCycles", () => ({
  createDecisionCycle: vi.fn(),
  updateDecisionCycle: vi.fn(),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import DecisionCycleModal from "sections/accounts/decision-cycles/DecisionCycleModal";
import {
  createDecisionCycle,
  updateDecisionCycle,
} from "api/accounts/decisionCycles";

// ==============================|| HELPERS ||============================== //

function renderModal(props = {}) {
  return render(
    <DecisionCycleModal
      open
      onClose={vi.fn()}
      accountId="acc-1"
      onSuccess={vi.fn()}
      {...props}
    />,
  );
}

const dateInput = () =>
  document.querySelector('input[name="expected_close_date"]');

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
});

// ==============================|| TESTS ||============================== //

describe("DecisionCycleModal — expected close date", () => {
  it("renders the input", () => {
    renderModal();

    expect(screen.getByText("Expected Close Date")).toBeInTheDocument();
    expect(dateInput()).toBeInTheDocument();
  });

  it("sends the typed date on create", async () => {
    vi.mocked(createDecisionCycle).mockResolvedValue({ success: true, data: {} });
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByPlaceholderText(/Main Sales Cycle/), "Big Deal");
    await user.type(dateInput(), "2026-06-15");
    await user.click(screen.getByRole("button", { name: /create/i }));

    await waitFor(() => expect(createDecisionCycle).toHaveBeenCalled());
    expect(createDecisionCycle).toHaveBeenCalledWith(
      expect.objectContaining({ expected_close_date: "2026-06-15" }),
    );
  });

  it("sends null when left blank, so the closing-step fallback applies", async () => {
    vi.mocked(createDecisionCycle).mockResolvedValue({ success: true, data: {} });
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByPlaceholderText(/Main Sales Cycle/), "No Date");
    await user.click(screen.getByRole("button", { name: /create/i }));

    await waitFor(() => expect(createDecisionCycle).toHaveBeenCalled());
    expect(createDecisionCycle).toHaveBeenCalledWith(
      expect.objectContaining({ expected_close_date: null }),
    );
  });

  it("prefills from the cycle and sends the edited date on update", async () => {
    vi.mocked(updateDecisionCycle).mockResolvedValue({ success: true, data: {} });
    const user = userEvent.setup();
    renderModal({
      cycle: {
        id: "cyc-1",
        name: "Existing",
        description: "",
        expected_close_date: "2026-06-15",
      },
    });

    expect(dateInput()).toHaveValue("2026-06-15");

    await user.clear(dateInput());
    await user.type(dateInput(), "2026-09-30");
    await user.click(screen.getByRole("button", { name: /update|save/i }));

    await waitFor(() => expect(updateDecisionCycle).toHaveBeenCalled());
    expect(updateDecisionCycle).toHaveBeenCalledWith(
      "cyc-1",
      expect.objectContaining({ expected_close_date: "2026-09-30" }),
    );
  });

  it("clears the manual date when the field is emptied on edit", async () => {
    vi.mocked(updateDecisionCycle).mockResolvedValue({ success: true, data: {} });
    const user = userEvent.setup();
    renderModal({
      cycle: {
        id: "cyc-1",
        name: "Existing",
        description: "",
        expected_close_date: "2026-06-15",
      },
    });

    await user.clear(dateInput());
    await user.click(screen.getByRole("button", { name: /update|save/i }));

    await waitFor(() => expect(updateDecisionCycle).toHaveBeenCalled());
    expect(updateDecisionCycle).toHaveBeenCalledWith(
      "cyc-1",
      expect.objectContaining({ expected_close_date: null }),
    );
  });
});
