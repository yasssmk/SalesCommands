// frontend/src/__tests__/components/signals/SignalLine.tokens.test.jsx
//
// Lot 3 / 12 (TD-265) — SignalLine (the rows of the Activity Signals / Next
// steps bands) reads its compact visuals from the THEME, no hard-coded px /
// rem / hex: the chips from theme.aphoriQ.chip.compact (nature, scope,
// status) and .mini (the « +N » contact overflow), the meta icons from
// theme.iconSizes.xs + theme.aphoriQ.text.muted. Proven with a theme whose
// tokens differ from the former literals.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import AphoriQ from "themes/aphoriq";
import IconSizes from "themes/iconSizes";
import SignalLine from "components/signals/SignalLine";

afterEach(() => cleanup());

const base = createTheme();
const aq = AphoriQ(base);
const theme = createTheme(base, {
  iconSizes: { ...IconSizes(), xs: 13 },
  aphoriQ: {
    ...aq,
    text: { ...aq.text, muted: "rgb(1, 2, 3)" },
    chip: { compact: { height: 31, fontSize: "0.91rem" }, mini: { height: 27, fontSize: "0.77rem" } },
  },
});

const CONSTRAINT = {
  id: "c1", status: "PENDING", summary: "Must comply with SOC 2",
  nature_display: "Security", created_at: "2026-11-01T10:00:00Z",
  target_departments: [{ id: "d1", name: "IT" }],
  source_context: { contacts: [
    { id: "p1", first_name: "Paula", last_name: "One" },
    { id: "p2", first_name: "Marc", last_name: "Two" },
  ] },
};

const chipOf = (text) => screen.getByText(text).closest(".MuiChip-root");

describe("SignalLine — compact visuals from the theme (TD-265)", () => {
  it("the nature / status chips use theme.aphoriQ.chip.compact", () => {
    render(<ThemeProvider theme={theme}><SignalLine signal={CONSTRAINT} signalType="constraints" /></ThemeProvider>);
    for (const label of ["Security", "Pending"]) {
      const style = getComputedStyle(chipOf(label));
      expect(style.height).toBe("31px");
      expect(style.fontSize).toBe("0.91rem");
    }
  });

  it("the « +N » contact overflow uses theme.aphoriQ.chip.mini", () => {
    render(<ThemeProvider theme={theme}><SignalLine signal={CONSTRAINT} signalType="constraints" /></ThemeProvider>);
    const style = getComputedStyle(chipOf("+1"));
    expect(style.height).toBe("27px");
    expect(style.fontSize).toBe("0.77rem");
  });

  it("the meta icons use theme.iconSizes.xs + theme.aphoriQ.text.muted", () => {
    const { container } = render(
      <ThemeProvider theme={theme}><SignalLine signal={CONSTRAINT} signalType="constraints" /></ThemeProvider>,
    );
    const user = container.querySelector(".anticon-user");
    expect(user.style.fontSize).toBe("13px");
    expect(user.style.color).toBe("rgb(1, 2, 3)");
  });
});
