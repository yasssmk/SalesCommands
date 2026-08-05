// frontend/src/__tests__/sections/accounts/contacts/AccountContactsTab.optout.test.jsx
//
// The contacts list (AccountContactsTab) has an "Opt-out" column that reflects
// each contact's opted_out state: opted_out=true renders an "Opted out" chip,
// opted_out=false renders the empty "—" cell.
//
// Real render: the shared ReusableTable is NOT mocked — only the data hook is.
// Each fixture row sets has_buying_authority OPPOSITE to opted_out, so a column
// wired to the wrong boolean field would put the chip on the wrong row and fail.

import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  cleanup,
  within,
} from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

const FIXTURE = [
  {
    id: "c1",
    full_name: "Alice Opted",
    first_name: "Alice",
    last_name: "Opted",
    email: "alice@ex.io",
    phone_number: "+14155550001",
    department_name: "IT",
    influence_level: "UNKNOWN",
    opted_out: true,
    has_buying_authority: false, // opposite of opted_out -> catches a mis-wire
  },
  {
    id: "c2",
    full_name: "Bob Active",
    first_name: "Bob",
    last_name: "Active",
    email: "bob@ex.io",
    phone_number: "+14155550002",
    department_name: "Sales",
    influence_level: "UNKNOWN",
    opted_out: false,
    has_buying_authority: true, // opposite of opted_out -> catches a mis-wire
  },
];

vi.mock("api/businessData/contacts", () => ({
  useGetContacts: () => ({
    contacts: FIXTURE,
    contactsCount: FIXTURE.length,
    contactsLoading: false,
    contactsError: null,
  }),
  useGetContact: vi.fn(() => ({ contact: null, contactLoading: false })),
  useGetContactChoices: vi.fn(() => ({
    influenceLevels: [],
    standardDepartments: [],
    choicesLoading: false,
  })),
  updateContact: vi.fn(),
  createContact: vi.fn(),
}));

vi.mock("hooks/useLocalStorage", () => ({ default: () => [10, vi.fn()] }));

import AccountContactsTab from "sections/accounts/contacts/AccountContactsTab";

const base = Palette("light", "default");
const theme = createTheme({ palette: base.palette, customShadows: CustomShadows(base) });
theme.components = componentsOverride(theme);

function renderTab() {
  return render(
    <ThemeProvider theme={theme}>
      <AccountContactsTab accountId="acc-1" account={{ id: "acc-1", company_name: "Acme" }} />
    </ThemeProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AccountContactsTab — opt-out column", () => {
  it("renders an Opt-out header", () => {
    renderTab();
    expect(screen.getByText("Opt-out")).toBeInTheDocument();
  });

  it("shows the 'Opted out' chip only on the opted-out contact's row", () => {
    renderTab();

    const rowOpted = screen.getByText("Alice Opted").closest("tr");
    const rowActive = screen.getByText("Bob Active").closest("tr");

    // opted_out=true -> chip present in that row.
    expect(within(rowOpted).getByText("Opted out")).toBeInTheDocument();

    // opted_out=false -> no chip; the empty "—" cell is shown instead.
    expect(within(rowActive).queryByText("Opted out")).toBeNull();
    expect(within(rowActive).getAllByText("—").length).toBeGreaterThan(0);
  });
});
