// frontend/src/__tests__/components/chips/SignalTypeChip.objection.test.jsx
//
// Objection S4 — the single "Objection" type label: the blocker chip reads the
// central constant (utils/signalTypes.js, getSignalTypeLabel("blockers")).

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import SignalTypeChip from "components/chips/SignalTypeChip";

afterEach(() => cleanup());

describe("SignalTypeChip — blockers", () => {
  it("shows the canonical 'Objection' label (not 'Blocker')", () => {
    render(<SignalTypeChip signalType="blockers" />);
    expect(screen.getByText("Objection")).toBeInTheDocument();
    expect(screen.queryByText("Blocker")).not.toBeInTheDocument();
  });
});
