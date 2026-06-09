// frontend/src/__tests__/nextSteps/NextStepSuggestionDrawer.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/accounts/activities", () => ({
  ACTIVITY_TYPE_LABELS: {
    CALL: "Phone Call",
    EMAIL: "Email",
    MEETING: "Meeting",
  },
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import NextStepSuggestionDrawer from "sections/activities/nextSteps/NextStepSuggestionDrawer";

// ==============================|| FIXTURES ||============================== //

const MOCK_PENDING = {
  id: "ns1",
  status: "PENDING",
  suggested_title: "Follow up on pricing",
  suggested_activity_type: "CALL",
  suggested_activity_type_display: "Phone Call",
  suggested_due_date: "2026-06-15",
  suggested_contacts: [
    { id: "c1", first_name: "Jane", last_name: "Doe" },
    { id: "c2", first_name: "Marc", last_name: "Leblanc" },
  ],
  source_quote: "We should discuss pricing next week",
  notes: "Important follow-up",
  linked_activity: null,
};

const MOCK_VALIDATED = {
  id: "ns2",
  status: "VALIDATED",
  suggested_title: "Send proposal",
  suggested_activity_type: "EMAIL",
  suggested_due_date: "2026-06-12",
  suggested_contacts: [],
  source_quote: "She asked for a proposal",
  notes: null,
  linked_activity: {
    id: "act1",
    title: "Send proposal email",
    activity_type_display: "Email",
    status_display: "Planned",
    scheduled_date: "2026-06-12",
  },
};

const MOCK_REJECTED = {
  id: "ns3",
  status: "REJECTED",
  suggested_title: "Schedule demo",
  suggested_activity_type: "MEETING",
  suggested_due_date: null,
  suggested_contacts: [],
  source_quote: null,
  notes: null,
  linked_activity: null,
};

// ==============================|| TESTS ||============================== //

afterEach(() => {
  cleanup();
});

describe("NextStepSuggestionDrawer", () => {
  it("returns null when signal is null", () => {
    const { container } = render(
      <NextStepSuggestionDrawer
        open={true}
        signal={null}
        onClose={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders PENDING signal with title, type, date, contacts", () => {
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_PENDING}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Follow up on pricing")).toBeInTheDocument();
    expect(screen.getByText("Phone Call")).toBeInTheDocument();
    expect(screen.getByText("Jane Doe · Marc Leblanc")).toBeInTheDocument();
    expect(screen.getByText(/We should discuss pricing/)).toBeInTheDocument();
    expect(screen.getByText("Important follow-up")).toBeInTheDocument();
  });

  it("shows Convert and Reject buttons for PENDING signal", () => {
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_PENDING}
        onClose={vi.fn()}
        onConvert={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /convert to activity/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });

  it("calls onConvert on Convert click", () => {
    const onConvert = vi.fn();
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_PENDING}
        onClose={vi.fn()}
        onConvert={onConvert}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /convert to activity/i }));
    expect(onConvert).toHaveBeenCalledWith(MOCK_PENDING);
  });

  it("calls onReject on Reject click", () => {
    const onReject = vi.fn();
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_PENDING}
        onClose={vi.fn()}
        onReject={onReject}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith(MOCK_PENDING);
  });

  it("renders VALIDATED signal with linked activity section", () => {
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_VALIDATED}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Send proposal")).toBeInTheDocument();
    expect(screen.getByText("LINKED ACTIVITY")).toBeInTheDocument();
    expect(screen.getByText("Send proposal email")).toBeInTheDocument();
    expect(screen.getAllByText("Email").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Planned")).toBeInTheDocument();
  });

  it("shows View Activity button for VALIDATED signal with linked activity", () => {
    const onViewActivity = vi.fn();
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_VALIDATED}
        onClose={vi.fn()}
        onViewActivity={onViewActivity}
      />,
    );

    const btn = screen.getByRole("button", { name: /view activity/i });
    fireEvent.click(btn);
    expect(onViewActivity).toHaveBeenCalledWith(MOCK_VALIDATED.linked_activity);
  });

  it("hides Convert/Reject for VALIDATED signal", () => {
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_VALIDATED}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /convert to activity/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
  });

  it("shows Edit button for REJECTED signal when not locked", () => {
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_REJECTED}
        onClose={vi.fn()}
        onEdit={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });

  it("hides all action buttons when locked", () => {
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_PENDING}
        onClose={vi.fn()}
        isLocked
      />,
    );

    expect(screen.queryByRole("button", { name: /convert/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
  });

  it("calls onClose on close button click", () => {
    const onClose = vi.fn();
    render(
      <NextStepSuggestionDrawer
        open={true}
        signal={MOCK_PENDING}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /close drawer/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
