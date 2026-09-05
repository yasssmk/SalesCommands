// frontend/src/__tests__/components/signals/SignalTypeHeader.test.jsx
//
// SIG-1 — the per-type group header renders the type LABEL as COLOURED TEXT
// (its dedicated signal-type colour), NOT a Chip/pill.

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import AphoriqTheme, { testTheme } from "../../_utils/aphoriqTheme";
import SignalTypeHeader from "components/signals/SignalTypeHeader";
import { getSignalTypeColor } from "utils/signalTypes";

function renderHeader(signalType) {
  return render(
    <AphoriqTheme>
      <SignalTypeHeader signalType={signalType} />
    </AphoriqTheme>,
  );
}

describe("SignalTypeHeader (SIG-1)", () => {
  it("renders the type label as text", () => {
    renderHeader("pain");
    expect(screen.getByText("Pain")).toBeInTheDocument();
  });

  it("renders the label in the type's dedicated colour", () => {
    renderHeader("impact");
    const el = screen.getByText("Impact");
    const expected = getSignalTypeColor("impact", testTheme);
    // MUI applies sx `color` inline; jsdom exposes it via style.color.
    expect(el).toHaveStyle({ color: expected });
  });

  it("is NOT a Chip/pill (renders plain text, no MuiChip)", () => {
    const { container } = renderHeader("blockers");
    expect(container.querySelector(".MuiChip-root")).toBeNull();
    // The blockers type is labelled "Objection".
    expect(screen.getByText("Objection")).toBeInTheDocument();
  });

  it("renders nothing for an unknown type", () => {
    const { container } = render(
      <AphoriqTheme>
        <SignalTypeHeader signalType="nope" />
      </AphoriqTheme>,
    );
    expect(container.textContent).toBe("");
  });
});
