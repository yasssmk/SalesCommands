// frontend/src/__tests__/components/display/SectionHeader.test.jsx
//
// UI-3 — the shared numbered SectionHeader (index badge + title + optional
// subtitle). One component, replacing the inline copies in EditObjectiveContent
// and SignalDetailContent. Badge = primary role; subtitle shows only when passed.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";
import SectionHeader from "components/display/SectionHeader";

const renderSH = (props) =>
  render(
    <AphoriqTheme>
      <SectionHeader {...props} />
    </AphoriqTheme>,
  );

afterEach(() => cleanup());

describe("SectionHeader (shared)", () => {
  it("renders the numbered index badge (primary role) + the title", () => {
    renderSH({ index: 2, title: "Scope" });
    expect(screen.getByText("Scope")).toBeInTheDocument();
    const badge = screen.getByText("2");
    // the badge is a primary-coloured MUI Chip (P-BADGE-PRIMARY)
    const chipRoot = badge.closest(".MuiChip-root");
    expect(chipRoot).not.toBeNull();
    expect(chipRoot).toHaveClass("MuiChip-colorPrimary");
    expect(chipRoot).not.toHaveClass("MuiChip-colorInfo");
  });

  it("renders the subtitle only when provided", () => {
    renderSH({ index: 1, title: "Goal", subtitle: "Describe the objective." });
    expect(screen.getByText("Describe the objective.")).toBeInTheDocument();
  });

  it("omits the subtitle when not provided", () => {
    const { container } = renderSH({ index: 1, title: "Goal" });
    // only the title text, no caption subtitle line
    expect(container.querySelector(".MuiTypography-caption")).toBeNull();
  });

  it("omits the badge when no index is given (title only)", () => {
    renderSH({ title: "Plain header" });
    expect(screen.getByText("Plain header")).toBeInTheDocument();
    expect(document.querySelector(".MuiChip-root")).toBeNull();
  });
});
