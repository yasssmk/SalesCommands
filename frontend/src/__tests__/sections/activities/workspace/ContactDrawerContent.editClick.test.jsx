// frontend/src/__tests__/sections/activities/workspace/ContactDrawerContent.editClick.test.jsx
//
// CT-3 — the ✎ on the read-only Contact fiche opens the edit drawer:
// openDrawer(<EditContactContent contactId … />, { title: "Edit contact" }).
// It was inert before CT-3.

import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

const openDrawer = vi.fn();
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ isOpen: true, content: null, openDrawer, closeDrawer: vi.fn() }),
}));

const useGetContact = vi.fn();
const useGetDCPeople = vi.fn();
vi.mock("api/businessData/contacts", () => ({
  useGetContact: (...a) => useGetContact(...a),
}));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDCPeople: (...a) => useGetDCPeople(...a),
}));

import ThemeCustomization from "themes/index";
import ContactDrawerContent from "sections/activities/workspace/ContactDrawerContent";
import EditContactContent from "sections/activities/workspace/EditContactContent";

const CONTACT = { id: "c1", first_name: "Chevalier", last_name: "Iki", full_name: "Chevalier Iki" };

beforeEach(() => {
  openDrawer.mockClear();
  useGetContact.mockReturnValue({ contact: CONTACT, contactLoading: false, contactError: null });
  useGetDCPeople.mockReturnValue({ people: { qualified: [], unqualified: [] } });
});

describe("ContactDrawerContent — the ✎ opens the edit drawer", () => {
  it("openDrawer(EditContactContent contactId, {title:'Edit contact'})", () => {
    render(
      <ThemeCustomization>
        <ContactDrawerContent contactId="c1" activity={{ id: "a1", decision_cycle: "dc-1" }} />
      </ThemeCustomization>,
    );

    fireEvent.click(screen.getByTestId("contact-edit"));

    expect(openDrawer).toHaveBeenCalledTimes(1);
    const node = openDrawer.mock.calls[0][0];
    expect(node.type).toBe(EditContactContent);
    expect(node.props.contactId).toBe("c1");
    expect(openDrawer.mock.calls[0][1]).toEqual({ title: "Edit contact" });
  });
});
