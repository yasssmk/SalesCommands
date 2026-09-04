// frontend/src/__tests__/components/outcomes/OutcomeSelector.test.jsx
//
// O-1 — the shared outcome pill selector: renders getOutcomesForType(type) as
// single-select pills; clicking one raises onChange(outcome); the selected pill
// is visually distinct (aria-pressed).

import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import OutcomeSelector from "components/outcomes/OutcomeSelector";
import { getOutcomesForType } from "utils/outcomes";

function renderSel(props) {
  return render(
    <ThemeCustomization>
      <OutcomeSelector activityType="CALL" onChange={() => {}} {...props} />
    </ThemeCustomization>,
  );
}

describe("OutcomeSelector", () => {
  it("renders one pill per outcome valid for the type (CALL)", () => {
    renderSel({ activityType: "CALL" });
    const expected = getOutcomesForType("CALL");
    expected.forEach((o) => {
      expect(screen.getByTestId(`outcome-pill-${o}`)).toBeInTheDocument();
    });
    // a CALL-invalid outcome is NOT offered
    expect(screen.queryByTestId("outcome-pill-WRONG_EMAIL")).not.toBeInTheDocument();
  });

  it("filters by type: TASK excludes CALLBACK_REQUESTED / WRONG_CONTACT / UNSUBSCRIBE_OPTOUT", () => {
    renderSel({ activityType: "TASK" });
    expect(screen.getByTestId("outcome-pill-SUCCESSFUL")).toBeInTheDocument();
    expect(screen.queryByTestId("outcome-pill-CALLBACK_REQUESTED")).not.toBeInTheDocument();
    expect(screen.queryByTestId("outcome-pill-WRONG_CONTACT")).not.toBeInTheDocument();
    expect(screen.queryByTestId("outcome-pill-UNSUBSCRIBE_OPTOUT")).not.toBeInTheDocument();
  });

  it("clicking a pill raises onChange with that outcome", () => {
    const onChange = vi.fn();
    renderSel({ activityType: "CALL", onChange });
    fireEvent.click(screen.getByTestId("outcome-pill-MEETING_SCHEDULED"));
    expect(onChange).toHaveBeenCalledWith("MEETING_SCHEDULED");
  });

  it("marks the selected pill as pressed (visually distinct)", () => {
    renderSel({ activityType: "CALL", value: "SUCCESSFUL" });
    expect(screen.getByTestId("outcome-pill-SUCCESSFUL")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("outcome-pill-NO_ANSWER")).toHaveAttribute("aria-pressed", "false");
  });
});
