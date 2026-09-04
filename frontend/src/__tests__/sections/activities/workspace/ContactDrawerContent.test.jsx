// frontend/src/__tests__/sections/activities/workspace/ContactDrawerContent.test.jsx
//
// CT-2b — the read-only Contact fiche (drawer content). Identity + coordinates
// come from the durable Contact (useGetContact); "N activités du deal" and the
// decision role come from the contact's QUALIFIED entry in DC people
// (useGetDCPeople) — never from a PeopleSignal or a cluster directly. The role
// block and the activities encart are ABSENT outside a DC / when the contact
// has no DC-people entry. Edit + "See signals" are present but inert (CT-3 /
// future). No global Save/Cancel bar (CT-1).

import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

// Drawer close handler (the coque owns the cross) — stubbed.
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer: vi.fn() }),
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

const CONTACT = {
  id: "c1",
  first_name: "Chevalier",
  last_name: "Iki",
  full_name: "Chevalier Iki",
  job_title: "Head of HR",
  department_name: "HR",
  email: "iki@rr.com",
  phone_number: "+33124354657",
  linkedin: "https://linkedin.com/in/iki",
};

const DC = "dc-1";
const activityInDC = { id: "a1", decision_cycle: DC };
const activityNoDC = { id: "a2", decision_cycle: null };

function qualifiedEntry(over = {}) {
  return {
    signal_id: "s1",
    role: "CHAMPION",
    role_display: "Champion",
    influence: "HIGH",
    influence_display: "High",
    target_contact: { id: "c1", first_name: "Chevalier", last_name: "Iki" },
    target_department: null,
    activity_count: 3,
    notes: "",
    status: "VALIDATED",
    ...over,
  };
}

function mockContact(contact = CONTACT, extra = {}) {
  useGetContact.mockReturnValue({
    contact,
    contactLoading: false,
    contactError: null,
    contactValidating: false,
    ...extra,
  });
}
function mockDCPeople(peopleObj) {
  useGetDCPeople.mockReturnValue({
    people: peopleObj,
    peopleLoading: false,
    peopleError: null,
    peopleValidating: false,
    mutatePeople: vi.fn(),
  });
}

function renderFiche(props = {}) {
  return render(
    <ThemeCustomization>
      <ContactDrawerContent contactId="c1" activity={activityInDC} {...props} />
    </ThemeCustomization>,
  );
}

beforeEach(() => {
  useGetContact.mockReset();
  useGetDCPeople.mockReset();
});

describe("ContactDrawerContent — identity + coordinates", () => {
  it("renders the name, job · department and all present coordinates", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry()], unqualified: [] });
    renderFiche();

    expect(screen.getByText("Chevalier Iki")).toBeInTheDocument();
    expect(screen.getByText(/Head of HR/)).toBeInTheDocument();
    // email + linkedin are accent links
    expect(screen.getByRole("link", { name: /iki@rr\.com/ })).toBeInTheDocument();
    expect(screen.getByText("+33124354657")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /linkedin/i })).toBeInTheDocument();
  });

  it("hides a coordinate line when its value is empty", () => {
    mockContact({ ...CONTACT, phone_number: null, linkedin: "" });
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();

    expect(screen.getByRole("link", { name: /iki@rr\.com/ })).toBeInTheDocument();
    expect(screen.queryByText("+33124354657")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /linkedin/i })).not.toBeInTheDocument();
  });

  it("renders NO global Save/Cancel action bar (CT-1)", () => {
    mockContact();
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    expect(screen.queryByTestId("drawer-actions")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^save$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^cancel$/i })).not.toBeInTheDocument();
  });
});

describe("ContactDrawerContent — N activités du deal (DC people qualified)", () => {
  it("shows the activity_count from the contact's qualified DC entry", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry({ activity_count: 3 })], unqualified: [] });
    renderFiche();
    const encart = screen.getByTestId("contact-activities");
    expect(encart).toHaveTextContent("3");
  });

  it("does NOT show the activities encart when the contact is not in DC people", () => {
    mockContact();
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    expect(screen.queryByTestId("contact-activities")).not.toBeInTheDocument();
  });

  it("does NOT show the activities encart outside a DC (campaign activity)", () => {
    mockContact();
    mockDCPeople(undefined); // no cycle → hook returns nothing useful
    renderFiche({ activity: activityNoDC });
    expect(screen.queryByTestId("contact-activities")).not.toBeInTheDocument();
  });
});

describe("ContactDrawerContent — decision role (read from DC people)", () => {
  it("renders the role (+ influence) when the qualified entry has one", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry()], unqualified: [] });
    renderFiche();
    const role = screen.getByTestId("contact-role");
    expect(role).toHaveTextContent("Champion");
    expect(role).toHaveTextContent("High");
  });

  it("is ABSENT when the contact has no DC-people entry", () => {
    mockContact();
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    expect(screen.queryByTestId("contact-role")).not.toBeInTheDocument();
  });

  it("is ABSENT outside a DC (campaign activity)", () => {
    mockContact();
    mockDCPeople(undefined);
    renderFiche({ activity: activityNoDC });
    expect(screen.queryByTestId("contact-role")).not.toBeInTheDocument();
  });

  it("is ABSENT when the entry exists but carries no role", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry({ role: null, role_display: null })], unqualified: [] });
    renderFiche();
    expect(screen.queryByTestId("contact-role")).not.toBeInTheDocument();
  });
});

describe("ContactDrawerContent — inert body actions", () => {
  it("shows Edit and 'See signals', both inert (no crash on click)", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry()], unqualified: [] });
    renderFiche();
    const edit = screen.getByRole("button", { name: /edit/i });
    const signals = screen.getByTestId("contact-signals-link");
    expect(edit).toBeInTheDocument();
    expect(signals).toBeInTheDocument();
    // inert: clicking does nothing observable and must not throw
    fireEvent.click(edit);
    fireEvent.click(signals);
    expect(edit).toBeInTheDocument();
  });
});

describe("ContactDrawerContent — loading / error", () => {
  it("shows a discreet loader while the contact loads (no crash)", () => {
    useGetContact.mockReturnValue({ contact: null, contactLoading: true, contactError: null });
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    expect(screen.getByTestId("contact-loading")).toBeInTheDocument();
  });
});
