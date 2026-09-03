// frontend/src/__tests__/signals/SignalsFilterPanel.grouped.test.jsx
//
// The shared filter drawer renders the secondary filters (status / department /
// contact / scope) on Flat, and on Grouped WHEN the grouped surface honors them
// (groupedFilters — the cluster-backed Account/DC Qualification view). Type
// always renders on both. A grouped surface that does NOT honor them keeps
// Type-only, so no dead controls are shown.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

// AsyncContactSelect fetches contacts — stub it to a stable marker.
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: () => <div data-testid="contact-filter" />,
}));

import SignalsFilterPanel from "components/signals/SignalsFilterPanel";

const BASE = {
  open: true,
  onClose: vi.fn(),
  availableTypes: ["pain", "objective", "impact", "tech-stack"],
  departmentOptions: [{ value: "1", label: "Marketing" }],
  contactFilters: {},
  pendingFilters: {},
  onFilterChange: vi.fn(),
  onApply: vi.fn(),
  onClear: vi.fn(),
  hasPendingChanges: false,
};

function hasSecondaryFilters() {
  // MUI Select renders its label twice (InputLabel + fieldset legend), so use
  // queryAllByText for the Select-backed controls to avoid a multi-match throw.
  return {
    status: Boolean(screen.queryByText("Include rejected")),
    department: screen.queryAllByText("Department").length > 0,
    contact: Boolean(screen.queryByTestId("contact-filter")),
    scope: screen.queryAllByText("Scope").length > 0,
  };
}

afterEach(() => cleanup());

describe("SignalsFilterPanel — secondary filters visibility", () => {
  it("Flat: renders Type + status/department/contact/scope", () => {
    render(<SignalsFilterPanel {...BASE} mode="flat" />);
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(hasSecondaryFilters()).toEqual({
      status: true,
      department: true,
      contact: true,
      scope: true,
    });
  });

  it("Grouped + groupedFilters (cluster-backed): renders the full secondary set", () => {
    render(<SignalsFilterPanel {...BASE} mode="grouped" groupedFilters />);
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(hasSecondaryFilters()).toEqual({
      status: true,
      department: true,
      contact: true,
      scope: true,
    });
  });

  it("Grouped without groupedFilters: Type only (no dead controls)", () => {
    render(<SignalsFilterPanel {...BASE} mode="grouped" />);
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(hasSecondaryFilters()).toEqual({
      status: false,
      department: false,
      contact: false,
      scope: false,
    });
  });
});
