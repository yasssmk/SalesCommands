// frontend/src/__tests__/sections/campaigns/create/StepObjectiveMembers.objectiveDepartments.test.jsx
//
// S13 sub-step 6b — the OUTBOUND creation wizard's Details step gains an
// "Activity Objective" free-text input (activity_objective) and a
// "Target Departments" multi-select (target_department_ids, integer ids).
// Both OUTBOUND-only. Real render; api SWR hooks + next/font + date pickers
// mocked (project convention — mirrors the 6a label tests).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" }, variable: "" }),
}));

vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: (props) => <input aria-label={props.label} />,
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

// StandardDepartment choices are already {value: id(int), label} from
// /contacts/choices/.
vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: () => ({
    standardDepartments: [
      { value: 16, label: "IT" },
      { value: 17, label: "Sales" },
    ],
    choicesLoading: false,
  }),
}));

// AsyncUserSelect pulls its own data layer — stub it out (Team section).
vi.mock("components/AsyncSelection/AsyncUserSelect", () => ({
  default: () => <div data-testid="async-user-select" />,
}));

import StepObjectiveMembers from "sections/campaigns/create/StepObjectiveMembers";

afterEach(cleanup);

const base = {
  family: "OUTBOUND",
  name: "Q3 Outbound",
  description: "",
  activity_objective: "",
  target_department_ids: [],
  start_date: null,
  end_date: null,
  channel_override: "AUTO",
};

function renderStep(overrides = {}, onUpdate = vi.fn()) {
  render(<StepObjectiveMembers data={{ ...base, ...overrides }} onUpdate={onUpdate} />);
  return onUpdate;
}

describe("StepObjectiveMembers — Activity Objective + Target Departments (6b)", () => {
  it("renders both OUTBOUND-only fields when family=OUTBOUND", () => {
    renderStep();
    expect(screen.getByText("Activity Objective")).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Target Departments" }),
    ).toBeInTheDocument();
  });

  it("does NOT render them when family is not OUTBOUND", () => {
    renderStep({ family: "" });
    expect(screen.queryByText("Activity Objective")).toBeNull();
    expect(screen.queryByText("Target Departments")).toBeNull();
  });

  it("typing the objective calls onUpdate with {activity_objective}", () => {
    const onUpdate = renderStep();
    const input = screen.getByPlaceholderText(
      "Describe the goal — the AI recommendations will be more accurate.",
    );
    fireEvent.change(input, { target: { value: "Book a discovery call" } });
    expect(onUpdate).toHaveBeenCalledWith({ activity_objective: "Book a discovery call" });
  });

  it("selecting a department calls onUpdate with integer {target_department_ids}", () => {
    const onUpdate = renderStep();
    // Open the Target Departments Autocomplete and pick "IT".
    const combobox = screen.getByRole("combobox", { name: "Target Departments" });
    fireEvent.mouseDown(combobox);
    fireEvent.click(screen.getByText("IT"));
    expect(onUpdate).toHaveBeenCalledWith({ target_department_ids: [16] });
  });
});
