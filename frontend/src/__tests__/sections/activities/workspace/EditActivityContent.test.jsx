// frontend/src/__tests__/sections/activities/workspace/EditActivityContent.test.jsx
//
// S2c-2.2 — the Activity EDIT drawer, refactored into a READ layout: a bold
// "Edit activity" h3 title + FOUR stacked section boxes (Title & type · Date &
// time · Objective & description · People), each a background.default box with
// radius lg, separated by the header hairline filet, and each carrying an "Edit"
// button (inert here — wired to per-section edit in S2c-2.3). This step displays
// the current values only; no form, no save yet.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import { useTheme } from "@mui/material/styles";
import ThemeCustomization from "themes/index";
import EditActivityContent from "sections/activities/workspace/EditActivityContent";

// The emotion rule text for an element's own css-* classes (scoped).
function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
  const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
  return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
}

// Read the ACTUAL theme the app provider hands down, so the assertions compare
// against resolved tokens (never a hardcoded hex/px).
let probed = {};
function ThemeProbe() {
  const theme = useTheme();
  probed = {
    bgDefault: theme.palette.background.default,
    radiusLg: theme.aphoriQ.radius.lg,
    hairline: theme.aphoriQ.border.width.hairline,
    borderColor: theme.aphoriQ.border.color,
  };
  return null;
}

const ACTIVITY = {
  id: "act-1",
  title: "Discovery call",
  activity_type: "CALL",
  scheduled_date: "2026-09-10",
  scheduled_time: "14:30:00",
  due_date: null,
  call_to_action: "Qualify budget",
  description: "Intro call",
  account: "acc-1",
  account_detail: { id: "acc-1", company_name: "ACME" },
  owner_detail: { id: "u1", first_name: "Ann", last_name: "Owner", email: "ann@x.com", full_name: "Ann Owner" },
  invited_users_detail: [{ id: "u2", first_name: "Ivan", last_name: "Invit", email: "ivan@x.com", full_name: "Ivan Invit" }],
  contacts_detail: [{ id: "c1", full_name: "Cara Contact", first_name: "Cara", last_name: "Contact" }],
};

function renderEdit(activity = ACTIVITY) {
  return render(
    <ThemeCustomization>
      <ThemeProbe />
      <EditActivityContent activity={activity} />
    </ThemeCustomization>,
  );
}

describe("EditActivityContent — S2c-2.2 read layout: title + 4 section boxes", () => {
  it('renders a bold "Edit activity" h3 title', () => {
    renderEdit();
    const title = screen.getByText("Edit activity");
    expect(title).toHaveClass("MuiTypography-h3");
  });

  it("renders exactly FOUR section boxes", () => {
    renderEdit();
    expect(screen.getAllByTestId("edit-section")).toHaveLength(4);
  });

  it("each section box uses the page background token (background.default) and radius lg", () => {
    renderEdit();
    const boxes = screen.getAllByTestId("edit-section");
    expect(boxes).toHaveLength(4);
    boxes.forEach((box) => {
      const rule = rulesForElement(box);
      expect(rule).toContain(`background-color:${probed.bgDefault}`);
      expect(rule).toContain(`border-radius:${probed.radiusLg}px`);
    });
  });

  it("separates the sections with the header hairline filet (3 filets for 4 sections)", () => {
    renderEdit();
    const filets = screen.getAllByTestId("section-filet");
    expect(filets).toHaveLength(3);
    const rule = rulesForElement(filets[0]);
    expect(rule).toContain(`border-top-width:${probed.hairline}px`);
    expect(rule).toContain(`border-top-color:${probed.borderColor}`);
  });

  it("shows an Edit button on each section (4 total)", () => {
    renderEdit();
    expect(screen.getAllByRole("button", { name: /edit/i })).toHaveLength(4);
  });
});

describe("EditActivityContent — S2c-2.2 read values", () => {
  it("displays title, type label, date+time, objective, description, owner and contact", () => {
    renderEdit();
    expect(screen.getByText("Discovery call")).toBeInTheDocument();
    expect(screen.getByText("Phone Call")).toBeInTheDocument();
    // scheduled date + time on one line (Sep 10, 2026 · 2:30 PM)
    expect(screen.getByText(/Sep 10, 2026/)).toBeInTheDocument();
    expect(screen.getByText(/2:30 PM/)).toBeInTheDocument();
    expect(screen.getByText("Qualify budget")).toBeInTheDocument();
    expect(screen.getByText("Intro call")).toBeInTheDocument();
    expect(screen.getByText("Ann Owner")).toBeInTheDocument();
    expect(screen.getByText("Cara Contact")).toBeInTheDocument();
  });

  it("shows a due-date row (not scheduled) when only due_date is set", () => {
    renderEdit({ ...ACTIVITY, scheduled_date: null, scheduled_time: null, due_date: "2026-10-01" });
    expect(screen.getByText(/Due date/i)).toBeInTheDocument();
    expect(screen.getByText(/Oct 1, 2026/)).toBeInTheDocument();
  });

  it("uses placeholders when objective/description are empty", () => {
    renderEdit({ ...ACTIVITY, call_to_action: null, description: null });
    expect(screen.getByText(/No objective/i)).toBeInTheDocument();
    expect(screen.getByText(/No description/i)).toBeInTheDocument();
  });

  it("does NOT render a status or a cycle/step field", () => {
    renderEdit();
    expect(screen.queryByText(/^Status$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Pipeline step/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Decision cycle/i)).not.toBeInTheDocument();
  });
});
