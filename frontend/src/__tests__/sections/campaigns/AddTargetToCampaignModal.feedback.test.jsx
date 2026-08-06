// frontend/src/__tests__/sections/campaigns/AddTargetToCampaignModal.feedback.test.jsx
//
// The Add Target modal (single contact) routes the enroll_target response
// through notifyEnrollmentOutcome. Since it targets one contact, the server
// derives strict → singular messages. An unreachable contact now returns
// 201/contacts_enrolled=0 (no 4xx anymore) and must be named by its cause, NOT
// mislabelled "already active".

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

const h = vi.hoisted(() => ({ enrollTarget: vi.fn() }));

vi.mock("api/campaigns/campaigns", () => ({
  enrollTarget: (...a) => h.enrollTarget(...a),
  useGetCampaignContacts: () => ({ campaignContacts: [] }),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
}));

// Stub the async contact picker: one click selects a contact.
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: ({ onChange }) => (
    <button
      type="button"
      onClick={() => onChange(null, { id: "ct-1", account: { id: "acc-1" } })}
    >
      pick-contact
    </button>
  ),
}));

import AddTargetToCampaignModal from "sections/campaigns/workspace/AddTargetToCampaignModal";
import {
  displaySuccessSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

const base = Palette("light", "default");
const theme = createTheme({ palette: base.palette, customShadows: CustomShadows(base) });
theme.components = componentsOverride(theme);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function openAndSubmit() {
  render(
    <ThemeProvider theme={theme}>
      <AddTargetToCampaignModal campaignId="camp-1" open onClose={vi.fn()} onSuccess={vi.fn()} />
    </ThemeProvider>,
  );
  fireEvent.click(screen.getByText("pick-contact")); // select a contact
  const buttons = screen.getAllByRole("button").filter((b) => /Add Target/i.test(b.textContent));
  fireEvent.click(buttons[buttons.length - 1]); // the submit button (last)
}

// Single-contact modal → server derives strict = true.
const body = (over) => ({
  success: true,
  data: {
    data: {
      contacts_enrolled: 0,
      no_channel_count: 0,
      opted_out_count: 0,
      already_active_count: 0,
      account_empty: false,
      strict: true,
      ...over,
    },
  },
});

describe("AddTargetToCampaignModal — enrollment feedback", () => {
  it("unreachable contact → orange 'This contact is not reachable' (not 'already active')", async () => {
    h.enrollTarget.mockResolvedValue(body({ no_channel_count: 1 }));
    openAndSubmit();
    await waitFor(() =>
      expect(displayWarningSnackbar).toHaveBeenCalledWith(
        "This contact is not reachable",
      ),
    );
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
  });

  it("opted-out contact → orange 'This contact has opted out'", async () => {
    h.enrollTarget.mockResolvedValue(body({ opted_out_count: 1 }));
    openAndSubmit();
    await waitFor(() =>
      expect(displayWarningSnackbar).toHaveBeenCalledWith("This contact has opted out"),
    );
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
  });

  it("already active → orange 'Already enrolled'", async () => {
    h.enrollTarget.mockResolvedValue(body({ already_active_count: 1 }));
    openAndSubmit();
    await waitFor(() => expect(displayWarningSnackbar).toHaveBeenCalledWith("Already enrolled"));
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
  });

  it("contacts_enrolled>0 → green 'Contact(s) enrolled'", async () => {
    h.enrollTarget.mockResolvedValue(body({ contacts_enrolled: 1 }));
    openAndSubmit();
    await waitFor(() => expect(displaySuccessSnackbar).toHaveBeenCalledWith("Contact(s) enrolled"));
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
  });
});
