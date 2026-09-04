// frontend/src/__tests__/sections/activities/workspace/ActivityContextSection.userClick.test.jsx
//
// CT-USER — clicking an internal team member (owner or invited) in the Context
// card opens the read-only User fiche in the coque:
// openDrawer(<UserDrawerContent userId … />, { title: "Team member" }).

import { render, screen, cleanup, fireEvent } from "@testing-library/react";
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

const openDrawer = vi.fn();
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ isOpen: false, content: null, openDrawer, closeDrawer: vi.fn() }),
}));

import ThemeCustomization from "themes/index";
import ActivityContextSection from "sections/activities/workspace/ActivityContextSection";
import UserDrawerContent from "sections/activities/workspace/UserDrawerContent";

const OWNER = { id: "u1", first_name: "Admin", last_name: "Tenant A", full_name: "Admin Tenant A" };
const INVITED = { id: "u2", first_name: "Bob", last_name: "Guest", full_name: "Bob Guest" };

const activity = {
  call_to_action: null,
  scheduled_date: "2026-08-20",
  description: "Initial outreach call",
  account_detail: { id: "acc-1", company_name: "RED RUBAN" },
  owner_detail: OWNER,
  invited_users_detail: [INVITED],
  contacts_detail: [],
  decision_cycle: "dc-1",
  decision_cycle_detail: null,
  source_activity_detail: null,
};

describe("ActivityContextSection — internal team click opens the User fiche", () => {
  it("owner click → openDrawer(UserDrawerContent, {title:'Team member'})", () => {
    openDrawer.mockClear();
    render(
      <ThemeCustomization>
        <ActivityContextSection activity={activity} />
      </ThemeCustomization>,
    );

    fireEvent.click(screen.getByText("Admin Tenant A"));

    expect(openDrawer).toHaveBeenCalledTimes(1);
    const node = openDrawer.mock.calls[0][0];
    expect(node.type).toBe(UserDrawerContent);
    expect(node.props.userId).toBe("u1");
    expect(openDrawer.mock.calls[0][1]).toEqual({ title: "Team member" });
  });

  it("invited click → openDrawer(UserDrawerContent) with the invited id", () => {
    openDrawer.mockClear();
    render(
      <ThemeCustomization>
        <ActivityContextSection activity={activity} />
      </ThemeCustomization>,
    );

    fireEvent.click(screen.getByText("Bob Guest"));

    expect(openDrawer).toHaveBeenCalledTimes(1);
    const node = openDrawer.mock.calls[0][0];
    expect(node.type).toBe(UserDrawerContent);
    expect(node.props.userId).toBe("u2");
    expect(openDrawer.mock.calls[0][1]).toEqual({ title: "Team member" });
  });
});
