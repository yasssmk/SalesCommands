// frontend/src/__tests__/components/chips/ClickablePill.disabled.test.jsx
//
// Sprint Next steps 5.12c (3) — ClickablePill `disabled`: an unavailable action
// (the Next steps band's AI pill without transcript, its "Analyzing…" state):
// aria-disabled, out of the tab order, no click and no Enter / Space, the
// theme's disabled opacity. Without it, the pill behaves as before.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup } from "@testing-library/react";
import AphoriqTheme, { testTheme } from "../../_utils/aphoriqTheme";

import ClickablePill from "components/chips/ClickablePill";

const render = (ui) => rtlRender(<AphoriqTheme>{ui}</AphoriqTheme>);

afterEach(() => cleanup());

describe("ClickablePill — disabled (5.12c)", () => {
  it("disabled: aria-disabled, out of the tab order, the disabled opacity", () => {
    render(<ClickablePill label="Run AI on transcript" active disabled onClick={vi.fn()} />);
    const pill = screen.getByRole("button", { name: "Run AI on transcript" });
    expect(pill).toHaveAttribute("aria-disabled", "true");
    expect(pill).toHaveAttribute("tabindex", "-1");
    expect(pill).toHaveStyle({ opacity: String(testTheme.palette.action.disabledOpacity) });
  });

  it("disabled: neither a click nor Enter / Space fires onClick", () => {
    const onClick = vi.fn();
    render(<ClickablePill label="Run AI on transcript" active disabled onClick={onClick} />);
    const pill = screen.getByRole("button", { name: "Run AI on transcript" });
    fireEvent.click(pill);
    fireEvent.keyDown(pill, { key: "Enter" });
    fireEvent.keyDown(pill, { key: " " });
    expect(onClick).not.toHaveBeenCalled();
  });

  it("enabled (default): no aria-disabled, tab stop, a click and Enter fire onClick", () => {
    const onClick = vi.fn();
    render(<ClickablePill label="+ Add next step" active onClick={onClick} />);
    const pill = screen.getByRole("button", { name: "+ Add next step" });
    expect(pill).not.toHaveAttribute("aria-disabled");
    expect(pill).toHaveAttribute("tabindex", "0");
    fireEvent.click(pill);
    fireEvent.keyDown(pill, { key: "Enter" });
    expect(onClick).toHaveBeenCalledTimes(2);
  });
});
