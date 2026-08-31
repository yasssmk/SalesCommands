// frontend/src/__tests__/signals/TechStackCard.test.jsx
//
// TechStackCard renders the tool's own identity (S10): `tech_name` as
// the label, and one chip per qualification boolean.
//
// It used to read a `tech_catalog_entry` payload — a compact dict from
// the tenant tech catalogue carrying the label plus is_competitor /
// is_integration_target. The catalogue is gone, so a card still reading
// it would render "Unknown tool" with no flags on every signal.
//
// Real render, no mocking of the component under test — mirrors
// SignalDetailCard.test.jsx (:1-40).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import TechStackCard from "components/cards/signals/TechStackCard";

afterEach(() => {
  cleanup();
});

const BASE = {
  id: "ts1",
  status: "VALIDATED",
  tech_name: "Salesforce",
  tech_name_normalized: "salesforce",
  is_competitor: false,
  is_integration: false,
  is_to_replace: false,
  usage_scope: null,
  usage_departments: [],
  usage_start_year: null,
  renewal_date: null,
  cost_description: "",
  is_discontinued: false,
  discontinued_date: null,
  notes: "",
  created_at: "2026-06-01T10:00:00Z",
};

function renderCard(overrides = {}) {
  return render(
    <TechStackCard
      techStack={{ ...BASE, ...overrides }}
      onValidate={vi.fn()}
      onReject={vi.fn()}
      onEdit={vi.fn()}
      onDelete={vi.fn()}
    />,
  );
}

// ==============================|| LABEL ||============================== //

describe("TechStackCard — tool label", () => {
  it("renders tech_name as the label", () => {
    renderCard();
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
  });

  it("renders the raw spelling, not the normalised key", () => {
    renderCard({
      tech_name: "Salesforce CRM",
      tech_name_normalized: "salesforce crm",
    });
    expect(screen.getByText("Salesforce CRM")).toBeInTheDocument();
    expect(screen.queryByText("salesforce crm")).not.toBeInTheDocument();
  });

  it("falls back to 'Unknown tool' on an empty name", () => {
    renderCard({ tech_name: "" });
    expect(screen.getByText("Unknown tool")).toBeInTheDocument();
  });

  it("does not crash without any catalogue payload", () => {
    renderCard();
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
  });
});

// ==============================|| QUALIFICATION CHIPS ||============================== //

describe("TechStackCard — qualification chips", () => {
  it("shows no qualification chip when all three booleans are false", () => {
    renderCard();
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    expect(screen.queryByText("Integration")).not.toBeInTheDocument();
    expect(screen.queryByText("To replace")).not.toBeInTheDocument();
  });

  it("no longer renders a Competitor chip (competitors are their own signal type)", () => {
    renderCard({ is_competitor: true });
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    expect(screen.queryByText("Integration")).not.toBeInTheDocument();
    expect(screen.queryByText("To replace")).not.toBeInTheDocument();
  });

  it("no longer renders an Integration chip (integration is a TECHNICAL constraint now)", () => {
    renderCard({ is_integration: true });
    expect(screen.queryByText("Integration")).not.toBeInTheDocument();
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    expect(screen.queryByText("To replace")).not.toBeInTheDocument();
  });

  it("renders the To replace chip from is_to_replace", () => {
    renderCard({ is_to_replace: true });
    expect(screen.getByText("To replace")).toBeInTheDocument();
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    expect(screen.queryByText("Integration")).not.toBeInTheDocument();
  });

  it("renders only the surviving To replace chip — competitor and integration never show", () => {
    renderCard({
      is_competitor: true,
      is_integration: true,
      is_to_replace: true,
    });
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    expect(screen.queryByText("Integration")).not.toBeInTheDocument();
    expect(screen.getByText("To replace")).toBeInTheDocument();
  });

  it("ignores a stale catalogue payload if one ever lands", () => {
    // Defensive: a cached API response from before S10 must not
    // resurrect the old flags.
    renderCard({
      tech_catalog_entry: {
        company_name: "Legacy",
        product_name: "Entry",
        is_competitor: true,
        is_integration_target: true,
      },
    });
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.queryByText("Legacy Entry")).not.toBeInTheDocument();
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    expect(screen.queryByText("Integration")).not.toBeInTheDocument();
  });
});
