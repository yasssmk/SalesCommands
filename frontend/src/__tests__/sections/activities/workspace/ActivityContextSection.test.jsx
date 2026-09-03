// frontend/src/__tests__/sections/activities/workspace/ActivityContextSection.test.jsx
//
// UX Activity S2a — read-only aphoriQ Context card, copied from the mockup:
// bold "Context" title, dense two-column Details (bold values), People rows with
// round initials avatars + inline suffix (no email/phone) and a "+" per column
// header + a "›" per contact (all inert), and a CONDITIONAL provenance-only
// origin line (never the current campaign/DC rattachement).

import { render, screen, cleanup } from "@testing-library/react";
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

const ACCOUNT = { id: "acc-1", company_name: "RED RUBAN" };
const OWNER = { id: "u1", email: "admin@test.com", first_name: "Admin", last_name: "Tenant A", full_name: "Admin Tenant A" };
const CONTACT = { id: "c1", first_name: "Chevalier", last_name: "Iki", full_name: "Chevalier Iki", email: "iki@rr.com", phone_number: "+33124354657", job_title: "Head of HR", department_name: "HR" };

// No provenance; campaign_detail is set on purpose to prove the rattachement is
// NOT rendered in Context (it lives in the header).
const baseActivity = {
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
  decision_cycle_detail: null,
  decision_step_detail: null,
  source_activity_detail: null,
};

const provCampaign = {
  ...baseActivity,
  source_activity_detail: {
    id: "act9",
    title: "Initial Outreach Call",
    activity_type: "CALL",
    status: "COMPLETED",
    source_context: { type: "CAMPAIGN", id: "cmp1", name: "CAMP-B" },
  },
};

const provDC = {
  ...baseActivity,
  source_activity_detail: {
    id: "act9",
    title: "Prep call",
    activity_type: "CALL",
    status: "COMPLETED",
    source_context: { type: "DECISION_CYCLE", id: "dc9", name: "RED RUBAN deal" },
  },
};

function renderCtx(activity) {
  return render(
    <ThemeCustomization>
      <ActivityContextSection activity={activity} />
    </ThemeCustomization>,
  );
}

describe("ActivityContextSection — mockup copy", () => {
  it("renders the Context title, Objective placeholder, Scheduled and Description", () => {
    renderCtx(baseActivity);
    expect(screen.getByText("Context")).toBeInTheDocument();
    expect(screen.getByText("Click to define an objective…")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByText("Initial outreach call")).toBeInTheDocument();
  });

  it("people rows have round initials avatars and inline suffixes, no email/phone", () => {
    const { container } = renderCtx(baseActivity);
    // avatars (owner + contact), initials first-word + last-word letters
    expect(container.querySelectorAll(".MuiAvatar-root").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("AA")).toBeInTheDocument(); // Admin … A
    expect(screen.getByText("CI")).toBeInTheDocument(); // Chevalier Iki
    expect(screen.getByText("Admin Tenant A")).toBeInTheDocument();
    expect(screen.getByText(/· owner/)).toBeInTheDocument();
    expect(screen.getByText("Chevalier Iki")).toBeInTheDocument();
    expect(screen.getByText(/· HR/)).toBeInTheDocument();
    // no coordinates on people rows
    expect(screen.queryByText(/admin@test.com/)).not.toBeInTheDocument();
    expect(screen.queryByText(/iki@rr.com/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\+33/)).not.toBeInTheDocument();
  });

  it("shows an inert '+' on each column header and a '›' per contact", () => {
    const { container } = renderCtx(baseActivity);
    // "+" on Internal team AND External contacts headers
    expect(container.querySelectorAll(".anticon-plus").length).toBeGreaterThanOrEqual(2);
    // one chevron per external contact
    expect(container.querySelectorAll(".anticon-right").length).toBeGreaterThanOrEqual(1);
  });

  it("does NOT render the current campaign/DC rattachement in Context", () => {
    renderCtx(baseActivity); // campaign_detail set, but source null → no origin group
    expect(screen.queryByText(/Q2 Outbound/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Active/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Step 3/)).not.toBeInTheDocument();
    // no origin group at all (no provenance) → single Details|People separator
    expect(screen.getAllByTestId("ctx-sep")).toHaveLength(1);
    expect(screen.queryByText(/^From/)).not.toBeInTheDocument();
  });

  it("provenance CAMPAIGN — single line, campaign link + source-activity link, no rattachement", () => {
    renderCtx(provCampaign);
    expect(screen.getByText(/From campaign/i)).toBeInTheDocument();
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/campaigns/cmp1");
    expect(hrefs).toContain("/activities/act9");
    // NOT the rattachement line
    expect(screen.queryByText(/Q2 Outbound/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Active/)).not.toBeInTheDocument();
    // provenance = second separator present
    expect(screen.getAllByTestId("ctx-sep")).toHaveLength(2);
  });

  it("provenance DECISION_CYCLE — 'From Decision Cycle' with DC link, no step (absent from payload)", () => {
    renderCtx(provDC);
    expect(screen.getByText(/From Decision Cycle/i)).toBeInTheDocument();
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/accounts/acc-1/dc/dc9?tab=timeline");
    expect(hrefs).toContain("/activities/act9");
  });

  it("does NOT render ComingSoon nor Previous/Next activity", () => {
    renderCtx(baseActivity);
    expect(screen.queryByText(/Coming Soon/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Previous Activity/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Next Activity/i)).not.toBeInTheDocument();
  });

  it("single card consuming aphoriQ tokens (hairline) with minmax grids", () => {
    renderCtx(baseActivity);
    const card = screen.getAllByTestId("ctx-card")[0];
    const rule = (() => {
      const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
      const classes = (card.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
      return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
    })();
    expect(rule).toContain("0.5px");
    const allCss = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
    expect(allCss).toMatch(/minmax\(0/);
  });
});
