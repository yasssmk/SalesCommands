// frontend/src/__tests__/sections/activities/workspace/ActivityContextSection.test.jsx
//
// UX Activity S2a — read-only aphoriQ Context card, matched to the mockup:
// single compact card, dense two-column rows (Objective|Scheduled,
// Internal team|External contacts), no avatars/icons on people rows, hairline
// group separators, and a provenance + linked-context group (branch icon) that
// renders the origin line (3 cases, with links) above the current
// campaign/DC rattachement line.

import { render, screen, cleanup, within } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));
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

const ACCOUNT = { id: "acc-1", company_name: "RED RUBAN" };
const OWNER = { id: "u1", email: "admin@test.com", first_name: "Admin", last_name: "Tenant A", full_name: "Admin Tenant A" };
const CONTACT = { id: "c1", first_name: "Chevalier", last_name: "Iki", full_name: "Chevalier Iki", email: "iki@rr.com", phone_number: "+33124354657", job_title: "Head of HR", department_name: "HR" };

// DC rattachement (rule a: DC wins over campaign), no provenance.
const dcActivity = {
  call_to_action: null,
  scheduled_date: "2026-08-20",
  scheduled_time: null,
  due_date: null,
  description: "Initial outreach call",
  account: "acc-1",
  account_detail: ACCOUNT,
  owner_detail: OWNER,
  invited_users_detail: [],
  contacts_detail: [CONTACT],
  campaign_detail: { id: "cmp1", name: "Q2 Outbound", campaign_status: "ACTIVE", sequence_position: 3 },
  decision_cycle_detail: { id: "dc1", name: "HQ rollout" },
  decision_step_detail: { id: "st1", name: "Discovery", stage: "DISCOVERY", stage_display: "Qualification" },
  source_activity_detail: null,
};

// Campaign rattachement (no DC), no provenance.
const campaignActivity = {
  ...dcActivity,
  decision_cycle_detail: null,
  decision_step_detail: null,
  source_activity_detail: null,
};

// Provenance CAMPAIGN (isolated: no current rattachement).
const provCampaign = {
  ...dcActivity,
  campaign_detail: null,
  decision_cycle_detail: null,
  decision_step_detail: null,
  source_activity_detail: {
    id: "act9",
    title: "Initial Outreach Call",
    activity_type: "CALL",
    status: "COMPLETED",
    source_context: { type: "CAMPAIGN", id: "cmp1", name: "CAMP-B" },
  },
};

// Provenance DECISION_CYCLE.
const provDC = {
  ...provCampaign,
  source_activity_detail: {
    id: "act9",
    title: "Prep call",
    activity_type: "CALL",
    status: "COMPLETED",
    source_context: { type: "DECISION_CYCLE", id: "dc9", name: "RED RUBAN deal" },
  },
};

// No rattachement, no provenance.
const bareActivity = {
  ...dcActivity,
  campaign_detail: null,
  decision_cycle_detail: null,
  decision_step_detail: null,
  source_activity_detail: null,
};

function renderCtx(activity) {
  return render(
    <ThemeCustomization>
      <ActivityContextSection activity={activity} />
    </ThemeCustomization>,
  );
}

describe("ActivityContextSection — mockup-matched read-only card", () => {
  it("renders a single card with dense two-column grids using minmax(0,...) tracks", () => {
    renderCtx(dcActivity);
    expect(screen.getAllByTestId("ctx-card")).toHaveLength(1);
    const grids = screen.getAllByTestId("ctx-grid");
    expect(grids.length).toBeGreaterThanOrEqual(2);
    grids.forEach((g) => expect(rulesForElement(g)).toMatch(/grid-template-columns/));
    const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
    expect(css).toMatch(/minmax\(0/);
  });

  it("renders Objective placeholder, Scheduled date and Description", () => {
    renderCtx(dcActivity);
    expect(screen.getByText("Click to define an objective…")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByText("Initial outreach call")).toBeInTheDocument();
  });

  it("people rows carry NO avatar and show inline suffixes (owner / department)", () => {
    const { container } = renderCtx(dcActivity);
    // no avatar chrome anywhere in the card
    expect(container.querySelector(".MuiAvatar-root")).toBeNull();
    // internal: name + '· owner'
    expect(screen.getByText("Admin Tenant A")).toBeInTheDocument();
    expect(screen.getByText(/· owner/)).toBeInTheDocument();
    // external: name + '· HR' (department)
    expect(screen.getByText("Chevalier Iki")).toBeInTheDocument();
    expect(screen.getByText(/· HR/)).toBeInTheDocument();
  });

  it("separates groups with hairline rules", () => {
    renderCtx(dcActivity);
    const seps = screen.getAllByTestId("ctx-sep");
    expect(seps.length).toBeGreaterThanOrEqual(2);
    seps.forEach((s) => expect(rulesForElement(s)).toContain("0.5px"));
  });

  it("linked context — DC present → cycle + step, campaign excluded (rule a)", () => {
    renderCtx(dcActivity);
    expect(screen.getByText(/HQ rollout/)).toBeInTheDocument();
    expect(screen.getByText(/Discovery/)).toBeInTheDocument();
    expect(screen.queryByText(/Q2 Outbound/)).not.toBeInTheDocument();
  });

  it("linked context — no DC → campaign line", () => {
    renderCtx(campaignActivity);
    expect(screen.getByText(/Q2 Outbound/)).toBeInTheDocument();
    expect(screen.queryByText(/HQ rollout/)).not.toBeInTheDocument();
  });

  it("provenance CAMPAIGN — campaign link + account text + source-activity link", () => {
    renderCtx(provCampaign);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText(/From campaign/i)).toBeInTheDocument();
    // account name is plain text (never a link)
    expect(screen.getByText(/RED RUBAN/)).toBeInTheDocument();
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/campaigns/cmp1");
    expect(hrefs).toContain("/activities/act9");
  });

  it("provenance DECISION_CYCLE — DC link to the deal timeline", () => {
    renderCtx(provDC);
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/accounts/acc-1/dc/dc9?tab=timeline");
    expect(hrefs).toContain("/activities/act9");
  });

  it("origin group is absent when there is neither provenance nor rattachement", () => {
    renderCtx(bareActivity);
    expect(screen.queryByText(/^From /)).not.toBeInTheDocument();
    // only the single Details|People separator remains
    expect(screen.getAllByTestId("ctx-sep")).toHaveLength(1);
  });

  it("does NOT render ComingSoon nor Previous/Next activity", () => {
    renderCtx(dcActivity);
    expect(screen.queryByText(/Coming Soon/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Previous Activity/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Next Activity/i)).not.toBeInTheDocument();
  });

  it("consumes aphoriQ tokens (hairline border on the card)", () => {
    renderCtx(dcActivity);
    expect(rulesForElement(screen.getAllByTestId("ctx-card")[0])).toContain("0.5px");
  });
});
