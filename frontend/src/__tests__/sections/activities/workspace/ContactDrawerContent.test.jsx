// frontend/src/__tests__/sections/activities/workspace/ContactDrawerContent.test.jsx
//
// CT-2b(-fix) — the read-only Contact fiche. Guiding principle: push the user
// to act → EVERYTHING is always shown, empty included, with a discreet
// placeholder that reveals what is missing.
//   - Contact identity + coordinates → useGetContact. The 3 coordinate lines
//     (Email / Phone / LinkedIn) are ALWAYS rendered, in two columns
//     (label left / value right); an empty one shows a "No …" placeholder.
//   - "Involved in N activities" + the decision role are READ from DC people
//     (useGetDCPeople) — the activity_count from EITHER the qualified or the
//     unqualified entry. The activities encart shows whenever a DC exists (even
//     0), absent outside a DC. The role section is ALWAYS present (placeholder
//     "No role defined" when unknown).
//   - Edit is a pencil next to the name (inert, CT-3); "See signals" sits at the
//     bottom (inert, future). No global Save/Cancel bar (CT-1).

import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));
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

function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
  const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
  return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
}

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

const activityInDC = { id: "a1", decision_cycle: "dc-1" };
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

// Unqualified entry shape (backend people_consolidation_service.py:174-179):
// { contact: {...}, department: {...}, activity_count: N }.
function unqualifiedEntry(over = {}) {
  return {
    contact: { id: "c1", first_name: "Chevalier", last_name: "Iki", job_title: "Head of HR" },
    department: null,
    activity_count: 2,
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

describe("ContactDrawerContent — identity + coordinates (always shown, 2 columns)", () => {
  it("renders the name, job · department and the three coordinate labels + values", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry()], unqualified: [] });
    renderFiche();

    expect(screen.getByText("Chevalier Iki")).toBeInTheDocument();
    expect(screen.getByText(/Head of HR/)).toBeInTheDocument();

    // labels always present (two-column label/value rows)
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("Phone")).toBeInTheDocument();
    expect(screen.getByText("LinkedIn")).toBeInTheDocument();

    // values
    expect(screen.getByRole("link", { name: /iki@rr\.com/ })).toBeInTheDocument();
    expect(screen.getByText("+33124354657")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /linkedin/i })).toBeInTheDocument();
  });

  it("keeps all three lines even when values are empty, showing 'No …' placeholders", () => {
    mockContact({ ...CONTACT, phone_number: null, linkedin: "" });
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();

    // lines still there
    expect(screen.getByText("Phone")).toBeInTheDocument();
    expect(screen.getByText("LinkedIn")).toBeInTheDocument();
    // placeholders instead of values
    expect(screen.getByText("No phone")).toBeInTheDocument();
    expect(screen.getByText("No LinkedIn")).toBeInTheDocument();
    // email still a real value
    expect(screen.getByRole("link", { name: /iki@rr\.com/ })).toBeInTheDocument();
  });

  it("shows 'No email' when the email is missing", () => {
    mockContact({ ...CONTACT, email: "" });
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    expect(screen.getByText("No email")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /iki@rr\.com/ })).not.toBeInTheDocument();
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

describe("ContactDrawerContent — Edit pencil pushed to the right (inert)", () => {
  it("shows an Edit pencil control, inert (no crash on click)", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry()], unqualified: [] });
    renderFiche();
    const edit = screen.getByTestId("contact-edit");
    expect(edit).toBeInTheDocument();
    fireEvent.click(edit);
    expect(edit).toBeInTheDocument();
  });

  it("puts the Edit pencil at the far right — last child of the flex identity row", () => {
    mockContact();
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    const edit = screen.getByTestId("contact-edit");
    const row = screen.getByTestId("contact-identity-row");
    // the row is a flex row, and the pencil is its LAST child (so the growing
    // name block pushes it to the far right).
    const rowRule = rulesForElement(row);
    expect(rowRule).toMatch(/display:\s*flex/);
    expect(row.lastElementChild).toBe(edit);
  });
});

describe("ContactDrawerContent — See signals at the bottom (inert)", () => {
  it("shows 'See signals', inert (no crash on click)", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry()], unqualified: [] });
    renderFiche();
    const signals = screen.getByTestId("contact-signals-link");
    expect(signals).toBeInTheDocument();
    fireEvent.click(signals);
    expect(signals).toBeInTheDocument();
  });
});

describe("ContactDrawerContent — N activités du deal (qualified OR unqualified)", () => {
  it("reads activity_count from the qualified entry", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry({ activity_count: 3 })], unqualified: [] });
    renderFiche();
    expect(screen.getByTestId("contact-activities")).toHaveTextContent("3");
  });

  it("reads activity_count from the unqualified entry", () => {
    mockContact();
    mockDCPeople({ qualified: [], unqualified: [unqualifiedEntry({ activity_count: 2 })] });
    renderFiche();
    expect(screen.getByTestId("contact-activities")).toHaveTextContent("2");
  });

  it("shows the encart with 0 when the contact is in a DC but on no activity", () => {
    mockContact();
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    const encart = screen.getByTestId("contact-activities");
    expect(encart).toHaveTextContent("0");
  });

  it("does NOT show the encart outside a DC (campaign activity)", () => {
    mockContact();
    mockDCPeople(undefined);
    renderFiche({ activity: activityNoDC });
    expect(screen.queryByTestId("contact-activities")).not.toBeInTheDocument();
  });
});

describe("ContactDrawerContent — decision role (always present, placeholder if empty)", () => {
  it("renders the role (+ influence) when the qualified entry has one", () => {
    mockContact();
    mockDCPeople({ qualified: [qualifiedEntry()], unqualified: [] });
    renderFiche();
    const role = screen.getByTestId("contact-role");
    expect(role).toHaveTextContent("Champion");
    expect(role).toHaveTextContent("High");
  });

  it("shows 'No role defined' when the contact has no DC-people entry", () => {
    mockContact();
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    expect(screen.getByTestId("contact-role")).toHaveTextContent(/No role defined/i);
  });

  it("shows 'No role defined' outside a DC", () => {
    mockContact();
    mockDCPeople(undefined);
    renderFiche({ activity: activityNoDC });
    expect(screen.getByTestId("contact-role")).toHaveTextContent(/No role defined/i);
  });

  it("shows 'No role defined' when the entry exists but carries no role", () => {
    mockContact();
    mockDCPeople({ qualified: [], unqualified: [unqualifiedEntry()] });
    renderFiche();
    expect(screen.getByTestId("contact-role")).toHaveTextContent(/No role defined/i);
  });
});

describe("ContactDrawerContent — loading", () => {
  it("shows a discreet loader while the contact loads (no crash)", () => {
    useGetContact.mockReturnValue({ contact: null, contactLoading: true, contactError: null });
    mockDCPeople({ qualified: [], unqualified: [] });
    renderFiche();
    expect(screen.getByTestId("contact-loading")).toBeInTheDocument();
  });
});
