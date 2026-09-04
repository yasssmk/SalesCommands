// frontend/src/__tests__/components/outcomes/OutcomeChip.test.jsx
//
// O-1 — the shared outcome chip: renders the unified label + palette-role colour
// on the standard StatusPill.

import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import OutcomeChip from "components/outcomes/OutcomeChip";
import { OUTCOME_META } from "utils/outcomes";

function renderChip(outcome) {
  return render(
    <ThemeCustomization>
      <OutcomeChip outcome={outcome} />
    </ThemeCustomization>,
  );
}

describe("OutcomeChip", () => {
  it("renders the unified label of the outcome", () => {
    renderChip("MEETING_SCHEDULED");
    expect(screen.getByText(OUTCOME_META.MEETING_SCHEDULED.label)).toBeInTheDocument();
  });

  it("renders on the shared StatusPill primitive", () => {
    renderChip("SUCCESSFUL");
    expect(screen.getByTestId("status-pill")).toBeInTheDocument();
  });

  it("renders nothing for an empty outcome", () => {
    const { container } = renderChip(null);
    expect(container.querySelector('[data-testid="status-pill"]')).toBeNull();
  });
});
