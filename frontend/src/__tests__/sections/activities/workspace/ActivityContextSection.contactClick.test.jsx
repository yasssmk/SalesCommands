// frontend/src/__tests__/sections/activities/workspace/ActivityContextSection.contactClick.test.jsx
//
// CT-2b — clicking an external contact in the Context card opens the read-only
// Contact fiche in the coque: openDrawer(<ContactDrawerContent contactId … />,
// { title: "Contact" }). The click was inert before CT-2b.

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
import ContactDrawerContent from "sections/activities/workspace/ContactDrawerContent";

const CONTACT = {
  id: "c1",
  first_name: "Chevalier",
  last_name: "Iki",
  full_name: "Chevalier Iki",
  job_title: "Head of HR",
  department_name: "HR",
};

const activity = {
  call_to_action: null,
  scheduled_date: "2026-08-20",
  description: "Initial outreach call",
  account_detail: { id: "acc-1", company_name: "RED RUBAN" },
  owner_detail: null,
  invited_users_detail: [],
  contacts_detail: [CONTACT],
  decision_cycle: "dc-1",
  decision_cycle_detail: null,
  source_activity_detail: null,
};

describe("ActivityContextSection — external contact click opens the Contact fiche", () => {
  it("calls openDrawer with ContactDrawerContent (contactId + activity) and title 'Contact'", () => {
    openDrawer.mockClear();
    render(
      <ThemeCustomization>
        <ActivityContextSection activity={activity} />
      </ThemeCustomization>,
    );

    fireEvent.click(screen.getByText("Chevalier Iki"));

    expect(openDrawer).toHaveBeenCalledTimes(1);
    const node = openDrawer.mock.calls[0][0];
    expect(node.type).toBe(ContactDrawerContent);
    expect(node.props.contactId).toBe("c1");
    expect(node.props.activity).toBe(activity);
    expect(openDrawer.mock.calls[0][1]).toEqual({ title: "Contact" });
  });
});
