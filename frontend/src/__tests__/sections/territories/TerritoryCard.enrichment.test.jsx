// frontend/src/__tests__/sections/territories/TerritoryCard.enrichment.test.jsx
//
// Card enrichment (commit 5b): count arrives via a prop (the per-card workspace
// N+1 is gone), the in-active-campaign chip, owner+team attribution, coverage
// and created_at. Real renders — no SWR mocking needed because the card no
// longer fetches anything.

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
    is_in_active_campaign: false,
    owner: { full_name: "Paul DUPONT" },
    team: { name: "SALES EMEA" },
    created_at: "2026-01-15",
    ...overrides,
  };
}

describe("TerritoryCard — count comes from the prop (N+1 removed)", () => {
  it("renders the prop count for a CONTACT territory without any fetch", () => {
    // Pre-5b this number came from a per-card useGetTerritoryWorkspace fetch.
    render(<TerritoryCard territory={mk({ type: "CONTACT" })} count={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("contacts")).toBeInTheDocument();
    // Not stuck on the loading placeholder.
    expect(screen.queryByText("...")).toBeNull();
  });

  it("shows '...' only while the batched counts are loading", () => {
    render(<TerritoryCard territory={mk()} loading />);
    expect(screen.getByText("...")).toBeInTheDocument();
  });
});

describe("TerritoryCard — in-active-campaign chip", () => {
  it("renders the chip only when is_in_active_campaign is true", () => {
    const { rerender } = render(<TerritoryCard territory={mk()} count={1} />);
    expect(screen.queryByText("In campaign")).toBeNull();
    rerender(
      <TerritoryCard territory={mk({ is_in_active_campaign: true })} count={1} />,
    );
    expect(screen.getByText("In campaign")).toBeInTheDocument();
  });
});

describe("TerritoryCard — attribution + created_at", () => {
  it("shows owner and team", () => {
    render(<TerritoryCard territory={mk()} count={1} />);
    expect(screen.getByText("Paul DUPONT — SALES EMEA")).toBeInTheDocument();
  });

  it("shows a low-key created date", () => {
    render(<TerritoryCard territory={mk()} count={1} />);
    expect(screen.getByText("Created 2026-01-15")).toBeInTheDocument();
  });
});

describe("TerritoryCard — coverage", () => {
  it("renders a queue-framed coverage headline when a snapshot exists", () => {
    render(
      <TerritoryCard
        territory={mk({
          coverage_numerator: 12,
          coverage_denominator: 40,
          coverage_computed_at: "2026-02-01",
        })}
        count={40}
      />,
    );
    // 40 - 12 = 28 accounts to go (never "0% done").
    expect(screen.getByText("28 accounts to go")).toBeInTheDocument();
    expect(screen.getByText("Coverage")).toBeInTheDocument();
  });

  it("hides coverage entirely when no snapshot has been computed", () => {
    render(<TerritoryCard territory={mk()} count={1} />);
    expect(screen.queryByText("Coverage")).toBeNull();
  });
});
