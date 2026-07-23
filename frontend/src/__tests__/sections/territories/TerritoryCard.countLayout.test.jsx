// frontend/src/__tests__/sections/territories/TerritoryCard.countLayout.test.jsx
//
// The big count on the territory card is laid out as a horizontal row (number
// then label on the same line), mirroring the campaign card for visual
// homogeneity. The assertion is STRUCTURAL, not just text presence: the number
// and label must share a MuiStack row wrapper — the previous vertical layout had
// them as direct Box children with no Stack, so a presence-only test would pass
// on both. The loading placeholder behaviour is preserved.
//
// Real render, no shared-component mocks. Mirrors TerritoryCard.multiselect
// (mk() factory with the ...overrides spread).

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import TerritoryCard from "sections/territories/TerritoryCard";

afterEach(cleanup);

function mk(overrides = {}) {
  return {
    id: "t1",
    name: "Enterprise",
    type: "ACCOUNT",
    description: "",
    is_system: false,
    filter_definition: {},
    ...overrides,
  };
}

describe("TerritoryCard — big count layout", () => {
  it("renders the count and its label on the same row (MuiStack row wrapper)", () => {
    render(<TerritoryCard territory={mk({ type: "ACCOUNT" })} count={7} />);

    const number = screen.getByText("7");
    const label = screen.getByText("accounts");

    // Same wrapper element…
    expect(number.parentElement).toBe(label.parentElement);
    // …and that wrapper is a MuiStack row. The old vertical layout had no Stack
    // (the two Typographies were direct Box children), so this fails on it.
    const wrapper = number.parentElement;
    expect(wrapper.className).toMatch(/MuiStack-root/);
    expect(getComputedStyle(wrapper).flexDirection).toBe("row");
  });

  it("uses the contacts label for a CONTACT territory, still on one row", () => {
    render(<TerritoryCard territory={mk({ type: "CONTACT" })} count={3} />);

    const number = screen.getByText("3");
    const label = screen.getByText("contacts");
    expect(number.parentElement).toBe(label.parentElement);
    expect(number.parentElement.className).toMatch(/MuiStack-root/);
  });

  it("keeps the loading placeholder ('...') in the count slot", () => {
    render(<TerritoryCard territory={mk()} loading />);

    const placeholder = screen.getByText("...");
    // Still the row wrapper, shared with the label.
    const label = screen.getByText("accounts");
    expect(placeholder.parentElement).toBe(label.parentElement);
    expect(placeholder.parentElement.className).toMatch(/MuiStack-root/);
  });
});
