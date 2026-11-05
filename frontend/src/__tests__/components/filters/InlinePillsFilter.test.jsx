// frontend/src/__tests__/components/filters/InlinePillsFilter.test.jsx
//
// 8h — THE inline filter: a controlled row of ClickablePill driven by a filter
// definition (utils/filters/filterDefinitions). Multi: a click adds / removes;
// single: a click replaces (the active one empties). Empty = no pill pressed
// (its meaning — all / the surface — is the definition's emptyMeans).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";
import InlinePillsFilter from "components/filters/InlinePillsFilter";

const render = (ui) => rtlRender(ui, { wrapper: AphoriqTheme });
afterEach(() => cleanup());

const DEF = {
  key: "types", param: "signal_type", label: "Type", multiple: true, emptyMeans: "surface",
  options: [{ value: "pain", label: "Pain" }, { value: "impact", label: "Impact" }, { value: "people", label: "People" }],
};
const pill = (label) => screen.getByRole("button", { name: label });

describe("InlinePillsFilter", () => {
  it("one pill per option, in a group named by the definition; the chosen ones pressed", () => {
    render(<InlinePillsFilter definition={DEF} value={["impact"]} onChange={vi.fn()} />);
    expect(screen.getByRole("group", { name: "Type" })).toBeInTheDocument();
    expect(pill("Pain")).toHaveAttribute("aria-pressed", "false");
    expect(pill("Impact")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("filter-pill-types-people")).toBeInTheDocument();
  });

  it("multi: a click adds, a click on a chosen one removes", () => {
    const onChange = vi.fn();
    render(<InlinePillsFilter definition={DEF} value={["impact"]} onChange={onChange} />);
    fireEvent.click(pill("Pain"));
    expect(onChange).toHaveBeenLastCalledWith(["impact", "pain"]);
    fireEvent.click(pill("Impact"));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it("single: a click replaces; the active one empties", () => {
    const onChange = vi.fn();
    render(<InlinePillsFilter definition={{ ...DEF, multiple: false }} value={["impact"]} onChange={onChange} />);
    fireEvent.click(pill("Pain"));
    expect(onChange).toHaveBeenLastCalledWith(["pain"]);
    fireEvent.click(pill("Impact"));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it("empty: no pill pressed", () => {
    render(<InlinePillsFilter definition={DEF} value={[]} onChange={vi.fn()} />);
    DEF.options.forEach((o) => expect(pill(o.label)).toHaveAttribute("aria-pressed", "false"));
  });
});
