// frontend/src/__tests__/sections/accounts/dc-workspace/PeopleTab.fullName.test.jsx
//
// Sprint Next steps 5.8b — a qualified People WITHOUT contact (e.g. created by
// "Add as person": MANUAL, role UNKNOWN, full_name only) is named by its
// full_name in the DC People tab (PeopleConsolidationService exposes it since
// 5.8a), not "Unknown". A People with a contact keeps the contact's name.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

afterEach(() => cleanup());

const useGetDCPeople = vi.fn();
const useGetSignalChoices = vi.fn();
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDCPeople: (...a) => useGetDCPeople(...a),
}));
vi.mock("api/signals/signals", () => ({
  createSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: (...a) => useGetSignalChoices(...a),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: () => <div data-testid="contact-select" />,
}));

import PeopleTab from "sections/accounts/dc-workspace/PeopleTab";

// The choices endpoint payload (PeopleRole.choices, UNKNOWN last).
const PEOPLE_ROLES = [
  { value: "DECISION_MAKER", label: "Decision Maker" },
  { value: "ECONOMIC_BUYER", label: "Economic Buyer" },
  { value: "CHAMPION", label: "Champion" },
  { value: "BLOCKER", label: "Blocker" },
  { value: "END_USER", label: "End User" },
  { value: "PROCUREMENT", label: "Procurement" },
  { value: "INFLUENCER", label: "Influencer" },
  { value: "UNKNOWN", label: "Unknown" },
];
// Influence choices -- labels distinct from any hard-coded list, so a test
// seeing them proves the endpoint is the source.
const PEOPLE_INFLUENCES = [
  { value: "HIGH", label: "High (endpoint)" },
  { value: "MEDIUM", label: "Medium (endpoint)" },
  { value: "LOW", label: "Low (endpoint)" },
];

const person = (id, role, role_display, first_name) => ({
  signal_id: id,
  role,
  role_display,
  influence: null,
  influence_display: null,
  target_contact: { id: `c-${id}`, first_name, last_name: "Doe" },
  target_department: null,
  notes: "",
});

beforeEach(() => {
  vi.clearAllMocks();
  useGetSignalChoices.mockReturnValue({
    choices: { people_roles: PEOPLE_ROLES, people_influences: PEOPLE_INFLUENCES },
    choicesLoading: false,
  });
  useGetDCPeople.mockReturnValue({
    people: {
      qualified: [
        person("s1", "UNKNOWN", "Unknown", "Alex"),
        person("s2", "CHAMPION", "Champion", "Sam"),
      ],
      unqualified: [],
    },
    peopleLoading: false,
    peopleError: null,
    mutatePeople: vi.fn(),
  });
});

const renderTab = () =>
  render(<PeopleTab cycleId="dc-1" accountId="acc-1" />, { wrapper: AphoriqTheme });

const nameless = { ...person("s3", "UNKNOWN", "Unknown", "x"), target_contact: null,
                   full_name: "Karim Benali" };

describe("PeopleTab — a People without contact is named (5.8b)", () => {
  it("shows the full_name of a People without contact, not 'Unknown'", () => {
    useGetDCPeople.mockReturnValue({
      people: { qualified: [nameless], unqualified: [] },
      peopleLoading: false, peopleError: null, mutatePeople: vi.fn(),
    });
    renderTab();
    expect(screen.getByText("Karim Benali")).toBeInTheDocument();
  });

  it("a People with a contact keeps the contact's name", () => {
    renderTab();
    expect(screen.getByText("Alex Doe")).toBeInTheDocument();
  });

  it("no contact and no full_name: still 'Unknown'", () => {
    useGetDCPeople.mockReturnValue({
      people: { qualified: [{ ...nameless, full_name: "" }], unqualified: [] },
      peopleLoading: false, peopleError: null, mutatePeople: vi.fn(),
    });
    renderTab();
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
  });
});
