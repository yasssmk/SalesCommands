// frontend/src/sections/accounts/dc-workspace/__tests__/DCWorkspaceHeader.title.test.jsx
//
// Regression test for the DC inline-title save payload.
//
// EditableField invokes onSave(fieldKey, newValue) (a two-arg contract).
// The header hook's onTitleSave must bind the SECOND argument (the typed
// value). A one-arg handler captured the fieldKey ("title") instead, so
// every rename sent {"name":"title"} regardless of input. This test drives
// onTitleSave the way EditableField does and asserts the typed value — not
// the literal "title" — reaches updateDecisionCycle.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/accounts/decisionCycles", () => ({
  updateDecisionCycle: vi.fn(),
  useGetDecisionCyclesByAccount: vi.fn(() => ({ cycles: [] })),
  CYCLE_DERIVED_STATUS_LABELS: {},
  CYCLE_STATUS_COLORS: {},
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Heavy children rendered only inside returned JSX — stub them so the hook
// can be exercised without pulling their dependency trees.
vi.mock("sections/accounts/decision-cycles/DecisionCycleModal", () => ({
  default: () => null,
}));
vi.mock("sections/accounts/dc-workspace/DealHealthRunButton", () => ({
  default: () => null,
}));
vi.mock("sections/accounts/dc-workspace/CycleCloseDialog", () => ({
  default: () => null,
  useCycleCloseReopen: () => ({
    handleReopenCycle: vi.fn(),
    reopenLoading: false,
    closeDialogOpen: false,
    setCloseDialogOpen: vi.fn(),
    handleCloseDialogDismiss: vi.fn(),
    closeFormik: {},
  }),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import useDCWorkspaceHeaderProps from "sections/accounts/dc-workspace/DCWorkspaceHeader";
import { updateDecisionCycle } from "api/accounts/decisionCycles";

// ==============================|| TESTS ||============================== //

const baseCycle = {
  id: "cyc-1",
  name: "Old Name",
  outcome: null,
  cycle_status: "IN_PROGRESS",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useDCWorkspaceHeaderProps — title save", () => {
  it("sends the typed value, not the fieldKey literal", async () => {
    vi.mocked(updateDecisionCycle).mockResolvedValue({ success: true });

    const { result } = renderHook(() =>
      useDCWorkspaceHeaderProps({
        cycle: baseCycle,
        accountId: "acc-1",
        onUpdate: vi.fn(),
      }),
    );

    // EditableField calls onSave(fieldKey, newValue).
    const saved = await result.current.onTitleSave("title", "Renamed Cycle");

    expect(saved).toBe(true);
    expect(updateDecisionCycle).toHaveBeenCalledWith("cyc-1", {
      name: "Renamed Cycle",
    });
    // Regression guard: the fieldKey must never leak in as the name.
    expect(updateDecisionCycle).not.toHaveBeenCalledWith("cyc-1", {
      name: "title",
    });
  });

  it("trims the typed value before sending", async () => {
    vi.mocked(updateDecisionCycle).mockResolvedValue({ success: true });

    const { result } = renderHook(() =>
      useDCWorkspaceHeaderProps({
        cycle: baseCycle,
        accountId: "acc-1",
        onUpdate: vi.fn(),
      }),
    );

    await result.current.onTitleSave("title", "  Spaced Name  ");

    expect(updateDecisionCycle).toHaveBeenCalledWith("cyc-1", {
      name: "Spaced Name",
    });
  });
});
