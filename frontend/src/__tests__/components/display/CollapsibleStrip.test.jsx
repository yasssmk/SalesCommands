// frontend/src/__tests__/components/display/CollapsibleStrip.test.jsx
//
// UX Activity S1 — CollapsibleStrip: the shared themed collapsible band used by
// the adaptive Activity page (Preparation / Source / Signals / Next step).
// Proves: collapsed hides its body, the header toggles it, defaultExpanded is
// honoured, and the strip consumes theme.aphoriQ.* tokens (no hardcoded px).
// Renders under the REAL ThemeCustomization so the emitted CSS comes from the
// live theme (same technique as primitives.test.jsx).

import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useTheme } from "@mui/material/styles";
import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => cleanup());

// theme-config.js calls next/font/google at import time — not loadable under vitest.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
// emotionCache uses next/navigation's useServerInsertedHTML (unmocked) — stub to passthrough.
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import CollapsibleStrip from "components/display/CollapsibleStrip";
import ExperimentOutlined from "@ant-design/icons/ExperimentOutlined";

// Exposes the live aphoriQ token values so assertions are mode-agnostic.
function TokenProbe() {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <div
      data-testid="tokens"
      data-radius-md={String(aq.radius.md)}
      data-hairline={String(aq.border.width.hairline)}
      data-muted={aq.text.muted}
    />
  );
}

function allStyleText() {
  return Array.from(document.querySelectorAll("style"))
    .map((s) => s.textContent || "")
    .join("");
}

// Return only the emotion CSS rules that target THIS element's own classes.
// Scoping to the element defeats cross-test <style> accumulation: a token that
// leaks into the document from a sibling test's Surface won't satisfy an
// assertion made against the header element's own rule.
function rulesForElement(el) {
  const css = allStyleText();
  const classes = (el.getAttribute("class") || "")
    .split(/\s+/)
    .filter((c) => c.startsWith("css-"));
  return classes
    .map((c) => {
      const re = new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g");
      return (css.match(re) || []).join("");
    })
    .join("");
}

const BODY = "interim band content";

describe("CollapsibleStrip", () => {
  it("collapsed by default: header visible, body not rendered", () => {
    render(
      <ThemeCustomization>
        <CollapsibleStrip title="Preparation" icon={ExperimentOutlined}>
          <div>{BODY}</div>
        </CollapsibleStrip>
      </ThemeCustomization>,
    );

    expect(screen.getByText("Preparation")).toBeInTheDocument();
    // unmountOnExit → collapsed content is absent from the DOM.
    expect(screen.queryByText(BODY)).not.toBeInTheDocument();
  });

  it("clicking the header expands and renders the body", async () => {
    const user = userEvent.setup();
    render(
      <ThemeCustomization>
        <CollapsibleStrip title="Signals" icon={ExperimentOutlined}>
          <div>{BODY}</div>
        </CollapsibleStrip>
      </ThemeCustomization>,
    );

    expect(screen.queryByText(BODY)).not.toBeInTheDocument();
    await user.click(screen.getByText("Signals"));
    expect(await screen.findByText(BODY)).toBeInTheDocument();
  });

  it("defaultExpanded renders the body immediately, and shows meta", () => {
    render(
      <ThemeCustomization>
        <CollapsibleStrip
          title="Next step"
          icon={ExperimentOutlined}
          defaultExpanded
          meta="2 pending"
        >
          <div>{BODY}</div>
        </CollapsibleStrip>
      </ThemeCustomization>,
    );

    expect(screen.getByText(BODY)).toBeInTheDocument();
    expect(screen.getByText("2 pending")).toBeInTheDocument();
  });

  it("consumes aphoriQ tokens (border.hairline in emitted CSS, not a hardcoded px)", () => {
    render(
      <ThemeCustomization>
        <TokenProbe />
        <CollapsibleStrip title="Source" icon={ExperimentOutlined}>
          <div>{BODY}</div>
        </CollapsibleStrip>
      </ThemeCustomization>,
    );

    const t = screen.getByTestId("tokens");
    const hairline = t.getAttribute("data-hairline"); // 0.5

    // Scope to the header element's OWN rule so the assertion genuinely tracks
    // the strip's token consumption (not styles leaked by sibling tests).
    const header = screen.getByRole("button");
    const headerCss = rulesForElement(header);

    // border.hairline (0.5px) is NOT a MUI default — its presence on the
    // header's own rule proves the strip consumes the aphoriQ border token.
    // (radius.md=8px is excluded: 8px also appears as theme.spacing(1).)
    expect(headerCss).toContain(`${hairline}px`);
  });
});
