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
    ON_HOLD: "On hold",
  },
  ACTIVITY_STATUS_COLORS: {
    PLANNED: "default",
    ON_HOLD: "warning",
  },
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import UpcomingActivitiesSection from "sections/activities/nextSteps/UpcomingActivitiesSection";

// ==============================|| FIXTURES ||============================== //

// 5.2 — the section shows the ONE next planned step chosen by the server
// (activity.next_planned_step); sequence_context.next_activities is not listed.
const mockActivity = {
  id: "act-1",
  decision_cycle: "dc-1",
  campaign_detail: null,
  sequence_context: {
    next_activities: [
      {
        id: "act-3",
        title: "Send proposal",
        activity_type: "EMAIL",
        status: "ON_HOLD",
        is_overdue: false,
        scheduled_date: "2026-06-15",
        due_date: null,
        decision_step_name: null,
      },
    ],
  },
  next_planned_step: {
    source: "DECISION_CYCLE",
    decision_cycle: { id: "dc-1", name: "Deal Acme" },
    activity: {
      id: "act-2",
      title: "Follow-up call",
      activity_type: "CALL",
      status: "PLANNED",
      is_overdue: false,
      scheduled_date: "2026-06-20",
      due_date: null,
      decision_step_name: "Discovery",
    },
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
  next_planned_step: null,
};

// ==============================|| TESTS ||============================== //

afterEach(() => {
  vi.clearAllMocks();
  cleanup();
});

describe("UpcomingActivitiesSection", () => {
  it("renders only the next planned step (no client re-sort of the sequence)", () => {
    render(
      <UpcomingActivitiesSection
        activity={mockActivity}
        onCreateActivity={vi.fn()}
      />,
    );

    expect(screen.getByText("Follow-up call")).toBeInTheDocument();
    expect(screen.queryByText("Send proposal")).not.toBeInTheDocument();
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

  it("shows empty state when no next step is planned", () => {
    render(
      <UpcomingActivitiesSection
        activity={emptySequenceActivity}
        onCreateActivity={vi.fn()}
      />,
    );

    expect(screen.getByText("No next step planned yet.")).toBeInTheDocument();
    expect(screen.getByText("Create a follow-up to continue.")).toBeInTheDocument();
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
