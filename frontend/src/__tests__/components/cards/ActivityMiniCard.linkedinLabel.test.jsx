// frontend/src/__tests__/components/cards/ActivityMiniCard.linkedinLabel.test.jsx
//
// The LINKEDIN activity type shows the shortened label "LinkedIn" (not the old
// "LinkedIn Message") wherever ACTIVITY_TYPE_LABELS is displayed. ActivityMiniCard
// is a real consumer (renders ACTIVITY_TYPE_LABELS[activity_type] as a chip), so
// this guards the front label at the consumer, aligned with the backend
// activity_type_display.
//
// The real api/accounts/activities module is used here (not mocked) so the test
// reads the actual label constant.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import ActivityMiniCard from "components/cards/activities/ActivityMiniCard";

afterEach(cleanup);

function mk(overrides = {}) {
  return {
    id: "a1",
    title: "Connect on LinkedIn",
    activity_type: "LINKEDIN",
    status: "PLANNED",
    is_overdue: false,
    ...overrides,
  };
}

describe("ActivityMiniCard — LINKEDIN label", () => {
  it("renders the LINKEDIN type as 'LinkedIn'", () => {
    render(<ActivityMiniCard activity={mk()} onNavigate={vi.fn()} />);
    expect(screen.getByText("LinkedIn")).toBeInTheDocument();
    expect(screen.queryByText("LinkedIn Message")).not.toBeInTheDocument();
  });
});
