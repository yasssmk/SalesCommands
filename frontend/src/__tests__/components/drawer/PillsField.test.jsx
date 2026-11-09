// frontend/src/__tests__/components/drawer/PillsField.test.jsx
//
// Lot 3 / 6 (TD-303) — PillsField becomes THE pills + "+ add" gesture of
// ScopeDepartmentsField: optional props only (no caption when `label` is
// absent, picker label / placeholder, error line, test-id overrides so the
// department hooks of the drawers are kept).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";

vi.mock("components/filters/MultiSelectFilter", () => ({
  default: ({ label, placeholder, options, onChange }) => (
    <div data-testid="picker" data-label={label} data-placeholder={placeholder}>
      {options.map((o) => (
        <button key={o.value} type="button" onClick={() => onChange([o.value])}>{`pick ${o.label}`}</button>
      ))}
    </div>
  ),
}));

import PillsField from "components/drawer/PillsField";

const render = (ui) => rtlRender(<AphoriqTheme>{ui}</AphoriqTheme>);
const OPTIONS = [{ value: "1", label: "Finance" }, { value: "2", label: "IT" }];

afterEach(() => cleanup());

describe("PillsField — optional props (TD-303)", () => {
  it("default hooks derive from `name`, the caption shows the label", () => {
    const onChange = vi.fn();
    render(<PillsField name="tools" label="Tools" items={[{ value: "a", label: "A" }]}
      onChange={onChange} addLabel="Add tool" />);
    expect(screen.getByText("Tools")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("remove-tools-a"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("without `label`: no caption; the picker reads pickerLabel + placeholder", () => {
    render(<PillsField name="department" items={[]} onChange={vi.fn()} options={OPTIONS}
      addLabel="Add department" pickerLabel="Departments" placeholder="Select departments…" />);
    expect(screen.queryByText("Departments")).toBeNull();
    fireEvent.click(screen.getByTestId("add-department"));
    expect(screen.getByTestId("picker")).toHaveAttribute("data-label", "Departments");
    expect(screen.getByTestId("picker")).toHaveAttribute("data-placeholder", "Select departments…");
  });

  it("testIds override the hooks (pill, remove, confirm, cancel, pills, picker)", () => {
    const onChange = vi.fn();
    render(<PillsField name="department" items={[{ value: "1", label: "Finance" }]} onChange={onChange}
      options={OPTIONS} addLabel="Add department"
      testIds={{ pills: "x-department-pills", pill: "dept-pill", remove: "remove-dept",
        picker: "x-add-department-picker", confirm: "confirm-add-departments", cancel: "cancel-add-departments" }} />);
    expect(screen.getByTestId("x-department-pills")).toBeInTheDocument();
    expect(screen.getByTestId("dept-pill-1")).toHaveTextContent("Finance");
    fireEvent.click(screen.getByTestId("add-department"));
    expect(screen.getByTestId("x-add-department-picker")).toBeInTheDocument();
    fireEvent.click(screen.getByText("pick IT"));
    fireEvent.click(screen.getByTestId("confirm-add-departments"));
    expect(onChange).toHaveBeenLastCalledWith([{ value: "1", label: "Finance" }, { value: "2", label: "IT" }]);
    fireEvent.click(screen.getByTestId("remove-dept-1"));
    expect(onChange).toHaveBeenLastCalledWith([]);
    fireEvent.click(screen.getByTestId("add-department"));
    fireEvent.click(screen.getByTestId("cancel-add-departments"));
    expect(screen.queryByTestId("x-add-department-picker")).toBeNull();
  });

  it("shows the error line", () => {
    render(<PillsField name="department" items={[]} onChange={vi.fn()} options={OPTIONS}
      addLabel="Add department" error="Pick at least one department" />);
    expect(screen.getByText("Pick at least one department")).toBeInTheDocument();
  });
});
