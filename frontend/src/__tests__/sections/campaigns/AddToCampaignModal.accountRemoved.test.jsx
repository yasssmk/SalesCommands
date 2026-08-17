// frontend/src/__tests__/sections/campaigns/AddToCampaignModal.accountRemoved.test.jsx
//
// S13 sub-step 6c — the whole-account (ACCOUNT) enroll mode is removed from the
// modal (backend rejects it). DEPARTMENT and CONTACT modes remain. Real render;
// api SWR hooks mocked (project convention).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" }, variable: "" }),
}));

const { enrollTarget } = vi.hoisted(() => ({
  enrollTarget: vi.fn(async () => ({ success: true, data: {} })),
}));
vi.mock("api/campaigns/campaigns", () => ({
  enrollTarget,
  useGetTargetedCampaign: () => ({ targetedCampaign: { id: "t1" }, targetedLoading: false }),
  useGetCampaignContacts: () => ({ campaignContacts: [] }),
}));
vi.mock("api/businessData/contacts", () => ({
  useGetContacts: () => ({
    contacts: [
      { id: "c1", first_name: "Jane", last_name: "Doe", department_name: "IT" },
    ],
    contactsLoading: false,
  }),
}));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionCyclesByAccount: () => ({ cycles: [], cyclesLoading: false }),
}));
vi.mock("utils/enrollmentFeedback", () => ({ notifyEnrollmentOutcome: () => ({}) }));
vi.mock("utils/displayError", () => ({ displayErrorSnackbar: vi.fn() }));

import AddToCampaignModal from "sections/campaigns/AddToCampaignModal";

afterEach(cleanup);

describe("AddToCampaignModal — ACCOUNT mode removed", () => {
  it("does NOT render the 'Entire account' option, keeps DEPARTMENT + CONTACT", () => {
    render(
      <AddToCampaignModal open accountId="acc1" accountName="Acme" onClose={() => {}} />,
    );

    expect(screen.queryByText("Entire account")).toBeNull();
    expect(screen.getByText("A specific department")).toBeInTheDocument();
    expect(screen.getByText("Specific contacts")).toBeInTheDocument();
  });
});
