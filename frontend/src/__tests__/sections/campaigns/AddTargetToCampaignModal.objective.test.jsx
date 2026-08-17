// frontend/src/__tests__/sections/campaigns/AddTargetToCampaignModal.objective.test.jsx
//
// S13 sub-step 6c — the single-contact enroll modal captures a per-enroll
// "Activity Objective" and forwards it in the enrollTarget CONTACT payload.
// Real render; enrollTarget + AsyncContactSelect mocked (project convention).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" }, variable: "" }),
}));

const { enrollTarget } = vi.hoisted(() => ({
  enrollTarget: vi.fn(async () => ({ success: true, data: {} })),
}));
vi.mock("api/campaigns/campaigns", () => ({ enrollTarget }));

vi.mock("utils/enrollmentFeedback", () => ({
  notifyEnrollmentOutcome: () => ({ kind: "success" }),
}));
vi.mock("utils/displayError", () => ({ displayErrorSnackbar: vi.fn() }));

// AsyncContactSelect → a button that selects a fake contact when clicked.
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: ({ onChange }) => (
    <button
      type="button"
      data-testid="pick-contact"
      onClick={() => onChange(null, { id: "c1", account: { id: "acc1" } })}
    >
      pick
    </button>
  ),
}));

import AddTargetToCampaignModal from "sections/campaigns/workspace/AddTargetToCampaignModal";

afterEach(() => {
  enrollTarget.mockClear();
  cleanup();
});

describe("AddTargetToCampaignModal — Activity Objective", () => {
  it("renders the Activity Objective input", () => {
    render(
      <AddTargetToCampaignModal open campaignId="camp1" enrolledContactIds={[]} onClose={() => {}} />,
    );
    expect(screen.getByText("Activity Objective")).toBeInTheDocument();
  });

  it("forwards the typed objective in the enrollTarget payload", async () => {
    render(
      <AddTargetToCampaignModal open campaignId="camp1" enrolledContactIds={[]} onClose={() => {}} />,
    );

    fireEvent.click(screen.getByTestId("pick-contact"));
    fireEvent.change(screen.getByPlaceholderText("e.g. Chase the signed quote"), {
      target: { value: "Re-open conversation" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Add Target/i }));

    await waitFor(() => expect(enrollTarget).toHaveBeenCalled());
    expect(enrollTarget).toHaveBeenCalledWith(
      "camp1",
      expect.objectContaining({
        type: "CONTACT",
        contact_ids: ["c1"],
        objective: "Re-open conversation",
      }),
    );
  });
});
