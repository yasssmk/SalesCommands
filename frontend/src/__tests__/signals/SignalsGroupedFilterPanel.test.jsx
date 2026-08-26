// frontend/src/__tests__/signals/SignalsGroupedFilterPanel.test.jsx
//
// The grouped (cluster) filter drawer: accordion sections by family. The
// Qualification section is filled (Perimeter / Contact / Domain / Dimension /
// Status); Tech Stack and Objection are empty placeholders.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, within } from "@testing-library/react";

// AsyncContactSelect fetches contacts — stub it to a stable marker.
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: () => <div data-testid="contact-filter" />,
}));

import SignalsGroupedFilterPanel from "sections/accounts/signals/SignalsGroupedFilterPanel";

const PERIMETER_OPTIONS = [
  { value: "BUSINESS", label: "Business" },
  { value: "3", label: "Marketing" },
  { value: "5", label: "Finance" },
];

function renderPanel(overrides = {}) {
  const onChange = vi.fn();
  const onClear = vi.fn();
  render(
    <SignalsGroupedFilterPanel
      open
      onClose={vi.fn()}
      perimeterOptions={PERIMETER_OPTIONS}
      contactFilters={{}}
      value={{
        perimeter: [],
        contacts: [],
        whats: [],
        dimensions: [],
        statuses: ["PENDING", "VALIDATED"],
      }}
      onChange={onChange}
      onClear={onClear}
      activeCount={0}
      {...overrides}
    />,
  );
  return { onChange, onClear };
}

afterEach(() => cleanup());

describe("SignalsGroupedFilterPanel — accordion sections by family", () => {
  it("renders the three family sections", () => {
    renderPanel();
    expect(screen.getByText("Qualification")).toBeInTheDocument();
    expect(screen.getByText("Tech Stack")).toBeInTheDocument();
    expect(screen.getByText("Objection")).toBeInTheDocument();
  });

  it("Qualification section shows Perimeter, Contact, Domain, Dimension, Status", () => {
    renderPanel();
    expect(screen.getByLabelText("Perimeter")).toBeInTheDocument();
    expect(screen.getByTestId("contact-filter")).toBeInTheDocument();
    expect(screen.getByLabelText("Domain")).toBeInTheDocument();
    expect(screen.getByLabelText("Dimension")).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeInTheDocument();
  });

  it("Tech Stack and Objection are empty placeholders (no controls)", () => {
    renderPanel();
    expect(
      screen.getByText(/Filters for the Tech Stack family/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Filters for the Objection family/i),
    ).toBeInTheDocument();
  });

  it("selecting a Perimeter option fires onChange('perimeter', …)", () => {
    const { onChange } = renderPanel();
    const perimeter = screen.getByLabelText("Perimeter");
    fireEvent.mouseDown(perimeter);
    // MUI Autocomplete opens a listbox; pick "Business".
    const option = screen.getByRole("option", { name: "Business" });
    fireEvent.click(option);
    expect(onChange).toHaveBeenCalledWith("perimeter", ["BUSINESS"]);
  });

  it("Clear all fires onClear (enabled only when a filter is active)", () => {
    const { onClear } = renderPanel({ activeCount: 2 });
    const clear = screen.getByRole("button", { name: /clear all/i });
    expect(clear).not.toBeDisabled();
    fireEvent.click(clear);
    expect(onClear).toHaveBeenCalled();
  });
});
