// frontend/src/__tests__/sections/accounts/dc-workspace/PeopleTab.roles.test.jsx
//
// TD-279 UI — the DC People tab reads its roles from the signal choices
// endpoint (useGetSignalChoices().people_roles, the EditPeopleContent source),
// no hard-coded list: the UNKNOWN role ("Unknown") gets its filter chip and is
// an option of the qualify Select. CRITICAL_ROLES (coverage alert) unchanged.

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

describe("PeopleTab — roles from the choices endpoint (TD-279 UI)", () => {
  it("shows an 'Unknown' filter chip counting the UNKNOWN person", () => {
    renderTab();
    expect(screen.getByText("Unknown (1)")).toBeInTheDocument();
    expect(screen.getByText("Champion (1)")).toBeInTheDocument();
  });

  it("the 'Unknown' chip filters on the UNKNOWN role", () => {
    renderTab();
    fireEvent.click(screen.getByText("Unknown (1)"));
    expect(screen.getByText("Alex Doe")).toBeInTheDocument();
    expect(screen.queryByText("Sam Doe")).not.toBeInTheDocument();
  });

  it("'Unknown' is an option of the qualify Select", async () => {
    renderTab();
    fireEvent.click(screen.getByRole("button", { name: /add stakeholder/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.mouseDown(within(dialog).getAllByRole("combobox")[0]);
    expect(await screen.findByRole("option", { name: "Unknown" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Champion" })).toBeInTheDocument();
  });

  it("the qualify Select's influence options come from the choices endpoint", async () => {
    renderTab();
    fireEvent.click(screen.getByRole("button", { name: /add stakeholder/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.mouseDown(within(dialog).getAllByRole("combobox")[1]);
    expect(await screen.findByRole("option", { name: "High (endpoint)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Low (endpoint)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "—" })).toBeInTheDocument();
  });

  it("coverage alert unchanged: critical roles only, labels from the choices", () => {
    renderTab();
    expect(screen.getByText("Economic Buyer, Decision Maker")).toBeInTheDocument();
  });
});
