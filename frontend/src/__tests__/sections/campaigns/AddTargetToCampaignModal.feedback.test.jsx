// frontend/src/__tests__/sections/campaigns/AddTargetToCampaignModal.feedback.test.jsx
//
// BUG A — the Add Target modal must NOT claim success when nothing was enrolled.
// The decision keys on the real contacts_enrolled count, not skip_reason (which the
// backend only sets when not strict; the modal always sends strict:true).
//   - contacts_enrolled === 0 (success:true) → info "already active", NOT success
//   - contacts_enrolled  >  0                → success "Contact added to campaign"

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

const h = vi.hoisted(() => ({
  enrollTarget: vi.fn(),
}));

vi.mock("api/campaigns/campaigns", () => ({
  enrollTarget: (...a) => h.enrollTarget(...a),
  // useGetCampaignContacts is used by the sibling AddToCampaignModal, not this one,
  // but keep the module shape harmless.
  useGetCampaignContacts: () => ({ campaignContacts: [] }),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
}));

// Stub the async contact picker: one click selects a reachable contact.
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
      <AddTargetToCampaignModal
        campaignId="camp-1"
        open
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    </ThemeProvider>,
  );
  fireEvent.click(screen.getByText("pick-contact")); // select a contact
  const buttons = screen.getAllByRole("button").filter((b) => /Add Target/i.test(b.textContent));
  fireEvent.click(buttons[buttons.length - 1]); // the submit button (last)
}

describe("AddTargetToCampaignModal — enrollment feedback", () => {
  it("contacts_enrolled=0 → warning 'already active', NOT a success snackbar", async () => {
    h.enrollTarget.mockResolvedValue({
      success: true,
      data: { data: { contacts_enrolled: 0, skip_reason: null } },
    });
    openAndSubmit();

    await waitFor(() => expect(displayWarningSnackbar).toHaveBeenCalledTimes(1));
    expect(displayWarningSnackbar).toHaveBeenCalledWith(
      "This contact is already active in the campaign",
    );
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
  });

  it("contacts_enrolled>0 → success 'Contact added to campaign'", async () => {
    h.enrollTarget.mockResolvedValue({
      success: true,
      data: { data: { contacts_enrolled: 1, skip_reason: null } },
    });
    openAndSubmit();

    await waitFor(() => expect(displaySuccessSnackbar).toHaveBeenCalledTimes(1));
    expect(displaySuccessSnackbar).toHaveBeenCalledWith("Contact added to campaign");
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
  });
});
