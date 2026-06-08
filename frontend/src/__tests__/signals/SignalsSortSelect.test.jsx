// frontend/src/__tests__/signals/SignalsSortSelect.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import SignalsSortSelect, {
  SORT_OPTIONS,
} from "sections/activities/signals/SignalsSortSelect";

afterEach(() => {
  cleanup();
});

describe("SignalsSortSelect", () => {
  it("renders with the selected value", () => {
    render(<SignalsSortSelect value="date-desc" onChange={vi.fn()} />);

    expect(screen.getByText("Date (newest)")).toBeInTheDocument();
  });

  it("exports SORT_OPTIONS with 5 entries", () => {
    expect(SORT_OPTIONS).toHaveLength(5);
    expect(SORT_OPTIONS.map((o) => o.value)).toEqual([
      "date-desc",
      "date-asc",
      "type",
      "theme",
      "status",
    ]);
  });

  it("renders the Sort label", () => {
    render(<SignalsSortSelect value="date-desc" onChange={vi.fn()} />);

    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
  });

  it("calls onChange when a new option is selected", () => {
    const onChange = vi.fn();
    render(<SignalsSortSelect value="date-desc" onChange={onChange} />);

    // Open the select dropdown
    const selectButton = screen.getByRole("combobox");
    fireEvent.mouseDown(selectButton);

    // Click "Type" option
    const typeOption = screen.getByRole("option", { name: "Type" });
    fireEvent.click(typeOption);

    expect(onChange).toHaveBeenCalledWith("type");
  });

  it("shows all 5 options in dropdown", () => {
    render(<SignalsSortSelect value="date-desc" onChange={vi.fn()} />);

    const selectButton = screen.getByRole("combobox");
    fireEvent.mouseDown(selectButton);

    expect(screen.getByRole("option", { name: "Date (newest)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Date (oldest)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Type" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Theme" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Status" })).toBeInTheDocument();
  });
});
