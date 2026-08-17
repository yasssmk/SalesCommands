// frontend/src/__tests__/sections/campaigns/AddToCampaignModal.feedback.test.jsx
//
// The wizard routes the enroll_target response through notifyEnrollmentOutcome
// (not mocked): green when contacts_enrolled > 0, orange otherwise, with the
// cause-specific text. Red stays only for result.success === false. Driven in
// ACCOUNT mode, so strict is false (plural / account wording).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

const h = vi.hoisted(() => ({ enrollTarget: vi.fn() }));

vi.mock("api/campaigns/campaigns", () => ({
  useGetTargetedCampaign: () => ({ targetedCampaign: { id: "tc-1" }, targetedLoading: false }),
  useGetCampaignContacts: () => ({ campaignContacts: [] }),
  enrollTarget: (...a) => h.enrollTarget(...a),
}));
vi.mock("api/businessData/contacts", () => ({
  useGetContacts: () => ({
    contacts: [{ id: "ct-1", first_name: "A", last_name: "B", email: "a@b.io",
                 account: { id: "acc-1" } }],
    contactsLoading: false,
  }),
}));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionCyclesByAccount: () => ({ cycles: [], cyclesLoading: false }),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
}));

import AddToCampaignModal from "sections/campaigns/AddToCampaignModal";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

const base = Palette("light", "default");
const theme = createTheme({ palette: base.palette, customShadows: CustomShadows(base) });
theme.components = componentsOverride(theme);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function submitOneContact() {
  render(
    <ThemeProvider theme={theme}>
      <AddToCampaignModal open accountId="acc-1" accountName="Acme" onClose={vi.fn()} onSuccess={vi.fn()} />
    </ThemeProvider>,
  );
  // ACCOUNT mode was removed; CONTACT is the default. Select the single contact,
  // then step 1 → Next, step 2 → Add to Campaign.
  fireEvent.click(screen.getByText("A B"));
  fireEvent.click(screen.getByRole("button", { name: /^Next$/ }));
  fireEvent.click(screen.getByRole("button", { name: /Add to Campaign/i }));
}

const body = (over) => ({
  success: true,
  data: {
    data: {
      contacts_enrolled: 0,
      no_channel_count: 0,
      opted_out_count: 0,
      already_active_count: 0,
      account_empty: false,
      strict: false,
      ...over,
    },
  },
});

describe("AddToCampaignModal — enrollment feedback", () => {
  it("enrolled>0, nothing skipped → green 'Contact(s) enrolled'", async () => {
    h.enrollTarget.mockResolvedValue(body({ contacts_enrolled: 1 }));
    submitOneContact();
    await waitFor(() => expect(displaySuccessSnackbar).toHaveBeenCalledWith("Contact(s) enrolled"));
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
  });

  it("enrolled>0 with some skipped → green 'Enrolled. N contacts skipped'", async () => {
    h.enrollTarget.mockResolvedValue(body({ contacts_enrolled: 2, no_channel_count: 1, opted_out_count: 1 }));
    submitOneContact();
    await waitFor(() => expect(displaySuccessSnackbar).toHaveBeenCalledWith("Enrolled. 2 contacts skipped"));
  });

  it("enrolled=0, all no-channel → orange 'No reachable contact in this account'", async () => {
    h.enrollTarget.mockResolvedValue(body({ no_channel_count: 2 }));
    submitOneContact();
    await waitFor(() =>
      expect(displayWarningSnackbar).toHaveBeenCalledWith("No reachable contact in this account"),
    );
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
  });

  it("enrolled=0, all opted out → orange 'All contacts have opted out'", async () => {
    h.enrollTarget.mockResolvedValue(body({ opted_out_count: 3 }));
    submitOneContact();
    await waitFor(() => expect(displayWarningSnackbar).toHaveBeenCalledWith("All contacts have opted out"));
  });

  it("enrolled=0, already active → orange 'Already enrolled'", async () => {
    h.enrollTarget.mockResolvedValue(body({ already_active_count: 2 }));
    submitOneContact();
    await waitFor(() => expect(displayWarningSnackbar).toHaveBeenCalledWith("Already enrolled"));
  });

  it("enrolled=0, account empty → orange 'No contacts'", async () => {
    h.enrollTarget.mockResolvedValue(body({ account_empty: true }));
    submitOneContact();
    await waitFor(() => expect(displayWarningSnackbar).toHaveBeenCalledWith("No contacts"));
  });

  it("enrolled=0, mixed causes → orange generic 'No reachable contact in this account'", async () => {
    h.enrollTarget.mockResolvedValue(body({ no_channel_count: 1, opted_out_count: 1 }));
    submitOneContact();
    await waitFor(() =>
      expect(displayWarningSnackbar).toHaveBeenCalledWith("No reachable contact in this account"),
    );
  });

  it("success:false → red error", async () => {
    h.enrollTarget.mockResolvedValue({ success: false, error: "boom", status: 400 });
    submitOneContact();
    await waitFor(() => expect(displayErrorSnackbar).toHaveBeenCalledTimes(1));
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
  });
});
