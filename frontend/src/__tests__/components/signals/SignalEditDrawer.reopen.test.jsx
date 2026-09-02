// frontend/src/__tests__/signals/SignalEditDrawer.reopen.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, act } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";

const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  reopenSignal: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("sections/activities/signals/wizard/forms/buildEditInitialValues", () => ({
  buildEditInitialValues: vi.fn(() => ({ summary: "test" })),
}));

vi.mock("sections/activities/signals/wizard/forms/InlinePainForm", () => ({
  default: ({ onCancel }) => (
    <div data-testid="inline-pain-form">
      <button onClick={onCancel}>Cancel</button>
    </div>
  ),
}));

vi.mock("sections/activities/signals/wizard/forms/InlineObjectiveForm", () => ({
  default: () => <div data-testid="inline-objective-form" />,
}));

vi.mock("sections/activities/signals/wizard/forms/InlineImpactForm", () => ({
  default: () => <div data-testid="inline-impact-form" />,
}));

vi.mock("sections/activities/signals/wizard/forms/InlineTechStackForm", () => ({
  default: () => <div data-testid="inline-tech-form" />,
}));

vi.mock("sections/activities/signals/BlockerEditForm", () => ({
  default: () => <div data-testid="blocker-edit-form" />,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import SignalEditDrawer from "components/signals/SignalEditDrawer";
import { reopenSignal } from "api/signals/signals";
import { displaySuccessSnackbar } from "utils/displayError";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const BASE_PROPS = {
  open: true,
  onClose: vi.fn(),
  onSuccess: vi.fn(),
  accountId: "acc-1",
  choices: {},
  choicesLoading: false,
};

describe("SignalEditDrawer — Reopen button", () => {
  it("does not show Reopen button when signal is PENDING", () => {
    render(
      <SignalEditDrawer
        {...BASE_PROPS}
        signal={{ id: "s1", status: "PENDING" }}
        signalType="pain"
      />,
    );

    expect(
      screen.queryByRole("button", { name: /reopen/i }),
    ).not.toBeInTheDocument();
  });

  it("shows Reopen button when signal is VALIDATED", () => {
    render(
      <SignalEditDrawer
        {...BASE_PROPS}
        signal={{ id: "s1", status: "VALIDATED" }}
        signalType="pain"
      />,
    );

    expect(
      screen.getByRole("button", { name: /reopen/i }),
    ).toBeInTheDocument();
  });

  it("shows Reopen button when signal is REJECTED", () => {
    render(
      <SignalEditDrawer
        {...BASE_PROPS}
        signal={{ id: "s1", status: "REJECTED" }}
        signalType="pain"
      />,
    );

    expect(
      screen.getByRole("button", { name: /reopen/i }),
    ).toBeInTheDocument();
  });

  it("calls reopenSignal with correct type and id on click", async () => {
    render(
      <SignalEditDrawer
        {...BASE_PROPS}
        signal={{ id: "s1", status: "VALIDATED" }}
        signalType="pain"
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /reopen/i }));
    });

    expect(reopenSignal).toHaveBeenCalledWith("pain", "s1");
    expect(displaySuccessSnackbar).toHaveBeenCalledWith(
      "Signal reopened — now pending",
    );
    expect(BASE_PROPS.onSuccess).toHaveBeenCalled();
    expect(BASE_PROPS.onClose).toHaveBeenCalled();
  });
});
