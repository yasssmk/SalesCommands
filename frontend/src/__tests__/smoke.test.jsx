// frontend/src/__tests__/smoke.test.jsx
//
// Smoke test — validates that the Vitest + RTL infrastructure works.
// This file is kept permanently as a baseline canary.

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

// ---------------------------------------------------------------------------
// 1. Pure logic — proves Vitest runs
// ---------------------------------------------------------------------------

describe("Vitest smoke", () => {
  it("evaluates basic arithmetic", () => {
    expect(1 + 1).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// 2. React rendering — proves jsdom + RTL + jest-dom matchers work
// ---------------------------------------------------------------------------

function Hello() {
  return <p>Hello</p>;
}

describe("React Testing Library smoke", () => {
  it("renders a React component and queries the DOM", () => {
    render(<Hello />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });
});
