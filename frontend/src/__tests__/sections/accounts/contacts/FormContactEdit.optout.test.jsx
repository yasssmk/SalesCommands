// frontend/src/__tests__/sections/accounts/contacts/FormContactEdit.optout.test.jsx
//
// The contact edit form exposes an "Opted out" toggle (edit only). Flipping it
// and saving must include opted_out in the payload sent to updateContact.
//
// Real render of the form (only data/util modules are mocked). Toggling the
// switch from false -> true must make the submitted payload carry
// opted_out: true; if the switch were not wired, the payload would stay false.

import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

const h = vi.hoisted(() => ({ updateContact: vi.fn(() => Promise.resolve({ success: true })) }));

const CONTACT = {
  id: "c1",
  first_name: "Alice",
  last_name: "Active",
  email: "alice@ex.io",
  phone_number: "+14155550001",
  job_title: "Buyer",
  linkedin: "",
  account: { id: "acc-1", company_name: "Acme" },
  standard_department: { id: "dept-1" },
  influence_level: "UNKNOWN",
  has_buying_authority: false,
  opted_out: false,
  notes: "",
};

vi.mock("api/businessData/contacts", () => ({
  useGetContact: () => ({ contact: CONTACT, contactLoading: false }),
  useGetContactChoices: () => ({
    influenceLevels: [{ value: "UNKNOWN", label: "Unknown" }],
    standardDepartments: [{ value: "dept-1", label: "IT" }],
    choicesLoading: false,
  }),
  updateContact: (...args) => h.updateContact(...args),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
}));
vi.mock("utils/formErrorHandler", () => ({ handleFormikError: vi.fn() }));

import FormContactEdit from "sections/accounts/contacts/FormContactEdit";

const base = Palette("light", "default");
const theme = createTheme({ palette: base.palette, customShadows: CustomShadows(base) });
theme.components = componentsOverride(theme);

function renderForm() {
  return render(
    <ThemeProvider theme={theme}>
      <FormContactEdit contact={CONTACT} contactId="c1" closeModal={vi.fn()} />
    </ThemeProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FormContactEdit — opted_out toggle", () => {
  it("submits opted_out: true after toggling the switch on", async () => {
    renderForm();

    const toggle = screen.getByRole("checkbox", { name: /opted out/i });
    expect(toggle).not.toBeChecked();

    fireEvent.click(toggle);
    expect(toggle).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(h.updateContact).toHaveBeenCalledTimes(1));
    const [contactId, payload] = h.updateContact.mock.calls[0];
    expect(contactId).toBe("c1");
    expect(payload.opted_out).toBe(true);
  });

  it("keeps opted_out: false when the switch is left untouched", async () => {
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(h.updateContact).toHaveBeenCalledTimes(1));
    expect(h.updateContact.mock.calls[0][1].opted_out).toBe(false);
  });
});
