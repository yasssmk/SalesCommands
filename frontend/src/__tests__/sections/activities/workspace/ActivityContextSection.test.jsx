// frontend/src/__tests__/sections/activities/workspace/ActivityContextSection.test.jsx
//
// UX Activity S2a — the READ-ONLY, aphoriQ-themed Context display that replaces
// the legacy ActivityOverviewTab in the Context block. Proves: it renders the
// core fields, applies the DC-priority-exclusive linked-context rule (a), shows
// provenance as an integrated info line (not an Alert) with a conditional link,
// drops ComingSoon + prev/next, and consumes theme.aphoriQ tokens.

import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));
// next/link renders an anchor; keep it a plain passthrough <a> in jsdom.
vi.mock("next/link", () => ({
  default: ({ href, children }) => <a href={typeof href === "string" ? href : "#"}>{children}</a>,
}));

import ThemeCustomization from "themes/index";
import ActivityContextSection from "sections/activities/workspace/ActivityContextSection";

function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style"))
    .map((s) => s.textContent || "")
    .join("");
  const classes = (el.getAttribute("class") || "")
    .split(/\s+/)
    .filter((c) => c.startsWith("css-"));
  return classes
    .map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join(""))
    .join("");
}

const dcActivity = {
  call_to_action: "Book the security review",
  scheduled_date: "2026-06-10",
  scheduled_time: "14:30:00",
  due_date: null,
  description: "Prospect asked for a deep-dive on SSO.",
  owner_detail: { id: "u1", email: "rep@acme.io", first_name: "Sam", last_name: "Rep", full_name: "Sam Rep" },
  invited_users_detail: [
    { id: "u2", email: "se@acme.io", first_name: "Pat", last_name: "Eng", full_name: "Pat Eng" },
  ],
  contacts_detail: [
    { id: "c1", first_name: "Marc", last_name: "Dubois", full_name: "Marc Dubois", email: "marc@corp.com", phone_number: "+33100000000", job_title: "CTO", department_name: "Engineering" },
  ],
  // BOTH set on purpose: this is the ambiguous case rule (a) resolves — a DC
  // present must win and exclude the campaign from the linked-context block.
  campaign_detail: { id: "cmp1", name: "Q2 Outbound", campaign_status: "ACTIVE", sequence_position: 3 },
  decision_cycle_detail: { id: "dc1", name: "HQ rollout" },
  decision_step_detail: { id: "st1", name: "Discovery", stage: "DISCOVERY", stage_display: "Discovery" },
  source_activity_detail: {
    id: "act9",
    title: "Intro call",
    activity_type: "CALL",
    status: "COMPLETED",
    source_context: { type: "CAMPAIGN", id: "cmp1", name: "Q2 Outbound" },
  },
};

const campaignActivity = {
  ...dcActivity,
  decision_cycle_detail: null,
  decision_step_detail: null,
  campaign_detail: { id: "cmp1", name: "Q2 Outbound", campaign_status: "ACTIVE", sequence_position: 3 },
  source_activity_detail: null,
};

function renderCtx(activity) {
  return render(
    <ThemeCustomization>
      <ActivityContextSection activity={activity} />
    </ThemeCustomization>,
  );
}

describe("ActivityContextSection (read-only)", () => {
  it("renders objective, description, owner, invited and contacts", () => {
    renderCtx(dcActivity);
    expect(screen.getByText("Book the security review")).toBeInTheDocument();
    expect(screen.getByText("Prospect asked for a deep-dive on SSO.")).toBeInTheDocument();
    expect(screen.getByText("Sam Rep")).toBeInTheDocument();
    expect(screen.getByText("Pat Eng")).toBeInTheDocument();
    expect(screen.getByText("Marc Dubois")).toBeInTheDocument();
    expect(screen.getByText(/CTO/)).toBeInTheDocument();
  });

  it("linked context — DC present → shows cycle + step, NOT the campaign (rule a)", () => {
    renderCtx(dcActivity);
    expect(screen.getByText("HQ rollout")).toBeInTheDocument();
    expect(screen.getByText(/Discovery/)).toBeInTheDocument();
    // rule (a): campaign is never shown when a DC is present.
    expect(screen.queryByText("Q2 Outbound")).not.toBeInTheDocument();
  });

  it("linked context — no DC, campaign present → shows the campaign", () => {
    renderCtx(campaignActivity);
    expect(screen.getByText("Q2 Outbound")).toBeInTheDocument();
    expect(screen.queryByText("HQ rollout")).not.toBeInTheDocument();
  });

  it("provenance is an integrated info line (not an Alert), with a link when id is set", () => {
    renderCtx(dcActivity);
    // integrated line, never an Alert.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText(/From campaign/i)).toBeInTheDocument();
    // links to the source activity (route is live) because id is non-null.
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("/activities/act9");
  });

  it("does NOT render ComingSoon nor Previous/Next activity", () => {
    renderCtx(dcActivity);
    expect(screen.queryByText(/Coming Soon/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Previous Activity/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Next Activity/i)).not.toBeInTheDocument();
  });

  it("consumes aphoriQ tokens (hairline border on the card, not a hardcoded px)", () => {
    renderCtx(dcActivity);
    const card = screen.getAllByTestId("ctx-card")[0];
    expect(rulesForElement(card)).toContain("0.5px");
  });
});
