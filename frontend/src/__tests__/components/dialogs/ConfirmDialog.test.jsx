// frontend/src/__tests__/components/dialogs/ConfirmDialog.test.jsx
//
// Sprint « Source / Notes » 2.1 (TD-120) — THE shared confirmation dialog: a
// title, an optional message / body, a cancel action and a coloured confirm
// action. Reused by the Activity header (cancel confirmation) and by the
// « unsaved changes » guard of the workspace coque (2.2).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import ConfirmDialog from "components/dialogs/ConfirmDialog";

afterEach(() => cleanup());

function renderDialog(props = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <ThemeCustomization>
      <ConfirmDialog
        open
        title="Discard your changes?"
        confirmLabel="Discard"
        cancelLabel="Keep editing"
        onConfirm={onConfirm}
        onCancel={onCancel}
        {...props}
      />
    </ThemeCustomization>,
  );
  return { onConfirm, onCancel };
}

describe("ConfirmDialog", () => {
  it("renders the title and both actions", () => {
    renderDialog();
    expect(screen.getByTestId("confirm-dialog")).toBeInTheDocument();
    expect(screen.getByText("Discard your changes?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep editing" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Discard" })).toBeInTheDocument();
  });

  it("confirm calls onConfirm, cancel calls onCancel", () => {
    const { onConfirm, onCancel } = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("renders an optional message and an optional body", () => {
    renderDialog({ message: "What you typed will be lost.", children: <span>extra body</span> });
    expect(screen.getByText("What you typed will be lost.")).toBeInTheDocument();
    expect(screen.getByText("extra body")).toBeInTheDocument();
  });

  it("has no body when neither message nor children are given", () => {
    renderDialog();
    expect(screen.getByTestId("confirm-dialog").querySelector(".MuiDialogContent-root")).toBeNull();
  });

  it("exposes the confirm test id and can disable the confirm action", () => {
    const { onConfirm } = renderDialog({ confirmTestId: "confirm-discard", confirmDisabled: true });
    const confirm = screen.getByTestId("confirm-discard");
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("renders nothing when closed", () => {
    renderDialog({ open: false });
    expect(screen.queryByTestId("confirm-dialog")).toBeNull();
  });
});
