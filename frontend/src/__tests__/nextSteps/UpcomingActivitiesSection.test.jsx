// frontend/src/__tests__/nextSteps/UpcomingActivitiesSection.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

const mockRouterPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockRouterPush }),
}));

vi.mock("api/accounts/activities", () => ({
  ACTIVITY_TYPE_LABELS: {
    CALL: "Phone Call",
    EMAIL: "Email",
    MEETING: "Meeting",
    TASK: "Task",
  },
  ACTIVITY_STATUS_LABELS: {
    PLANNED: "Planned",
    IN_PROGRESS: "In Progress",
  },
  ACTIVITY_STATUS_COLORS: {
    PLANNED: "default",
    IN_PROGRESS: "primary",
  },
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import UpcomingActivitiesSection from "sections/activities/nextSteps/UpcomingActivitiesSection";

// ==============================|| FIXTURES ||============================== //

const mockActivity = {
  id: "act-1",
  decision_cycle: "dc-1",
  campaign_detail: null,
  sequence_context: {
    next_activities: [
      {
        id: "act-2",
        title: "Follow-up call",
        activity_type: "CALL",
        status: "PLANNED",
        is_overdue: false,
        scheduled_date: "2026-06-20",
        due_date: null,
        decision_step_name: "Discovery",
      },
      {
        id: "act-3",
        title: "Send proposal",
        activity_type: "EMAIL",
        status: "IN_PROGRESS",
        is_overdue: false,
        scheduled_date: "2026-06-15",
        due_date: null,
        decision_step_name: null,
      },
    ],
  },
};

const noSequenceActivity = {
  id: "act-x",
  decision_cycle: null,
  campaign_detail: null,
  sequence_context: null,
};

const emptySequenceActivity = {
  id: "act-y",
  decision_cycle: "dc-2",
  campaign_detail: null,
  sequence_context: {
    next_activities: [],
  },
};

// ==============================|| TESTS ||============================== //

afterEach(() => {
  vi.clearAllMocks();
  cleanup();
});

describe("UpcomingActivitiesSection", () => {
  it("renders activity cards sorted by date", () => {
    render(
      <UpcomingActivitiesSection
        activity={mockActivity}
        onCreateActivity={vi.fn()}
      />,
    );

    const cards = screen.getAllByText(/Follow-up call|Send proposal/);
    expect(cards).toHaveLength(2);
    expect(screen.getByText("Send proposal")).toBeInTheDocument();
    expect(screen.getByText("Follow-up call")).toBeInTheDocument();
  });

  it("shows quick-create buttons when not locked", () => {
    render(
      <UpcomingActivitiesSection
        activity={mockActivity}
        onCreateActivity={vi.fn()}
      />,
    );

    const buttons = screen.getAllByRole("button");
    const buttonLabels = buttons.map((b) => b.textContent);
    expect(buttonLabels).toContain("Meeting");
    expect(buttonLabels).toContain("Call");
    expect(buttonLabels).toContain("Email");
    expect(buttonLabels).toContain("Task");
  });

  it("hides quick-create buttons when locked", () => {
    render(
      <UpcomingActivitiesSection
        activity={mockActivity}
        onCreateActivity={vi.fn()}
        isLocked
      />,
    );

    expect(screen.queryByText("Meeting")).not.toBeInTheDocument();
  });

  it("calls onCreateActivity with type on quick-create click", () => {
    const onCreateActivity = vi.fn();
    render(
      <UpcomingActivitiesSection
        activity={mockActivity}
        onCreateActivity={onCreateActivity}
      />,
    );

    fireEvent.click(screen.getByText("Meeting"));
    expect(onCreateActivity).toHaveBeenCalledWith("MEETING");
  });

  it("navigates on card click", () => {
    render(
      <UpcomingActivitiesSection
        activity={mockActivity}
        onCreateActivity={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Follow-up call"));
    expect(mockRouterPush).toHaveBeenCalledWith("/activities/act-2");
  });

  it("shows empty state when no sequence", () => {
    render(
      <UpcomingActivitiesSection
        activity={noSequenceActivity}
        onCreateActivity={vi.fn()}
      />,
    );

    expect(screen.getByText("No sequence linked.")).toBeInTheDocument();
  });

  it("shows empty state when sequence has no next activities", () => {
    render(
      <UpcomingActivitiesSection
        activity={emptySequenceActivity}
        onCreateActivity={vi.fn()}
      />,
    );

    expect(
      screen.getByText("No activities scheduled after this one. Create a follow-up to continue."),
    ).toBeInTheDocument();
  });

  it("shows step name chip when present", () => {
    render(
      <UpcomingActivitiesSection
        activity={mockActivity}
        onCreateActivity={vi.fn()}
      />,
    );

    expect(screen.getByText("Discovery")).toBeInTheDocument();
  });
});
