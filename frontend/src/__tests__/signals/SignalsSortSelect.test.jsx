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

    expect(screen.getByText("Date ↓")).toBeInTheDocument();
  });

  it("exports SORT_OPTIONS with 5 entries in correct order", () => {
    expect(SORT_OPTIONS).toHaveLength(5);
    expect(SORT_OPTIONS.map((o) => o.value)).toEqual([
      "type",
      "theme",
      "status",
      "date-desc",
      "date-asc",
    ]);
  });

  it("renders the Sort label", () => {
    render(<SignalsSortSelect value="date-desc" onChange={vi.fn()} />);

    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
  });

  it("calls onChange when a new option is selected", () => {
    const onChange = vi.fn();
    render(<SignalsSortSelect value="date-desc" onChange={onChange} />);

    const selectButton = screen.getByRole("combobox");
    fireEvent.mouseDown(selectButton);

    const typeOption = screen.getByRole("option", { name: "Type" });
    fireEvent.click(typeOption);

    expect(onChange).toHaveBeenCalledWith("type");
  });

  it("shows all 5 options in dropdown with Date last", () => {
    render(<SignalsSortSelect value="date-desc" onChange={vi.fn()} />);

    const selectButton = screen.getByRole("combobox");
    fireEvent.mouseDown(selectButton);

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(5);
    expect(options[0]).toHaveTextContent("Type");
    expect(options[1]).toHaveTextContent("Theme");
    expect(options[2]).toHaveTextContent("Status");
    expect(options[3]).toHaveTextContent("Date ↓");
    expect(options[4]).toHaveTextContent("Date ↑");
  });
});
