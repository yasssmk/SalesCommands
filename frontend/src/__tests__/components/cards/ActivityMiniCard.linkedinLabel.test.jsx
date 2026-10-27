// frontend/src/__tests__/components/cards/ActivityMiniCard.linkedinLabel.test.jsx
//
// The LINKEDIN activity type on ActivityMiniCard. Since 5.9b (PO) the card shows
// the type ICON (getActivityTypeIcon), no type chip / label any more: a LINKEDIN
// activity carries the LinkedIn icon and never the old "LinkedIn Message".
//
// The real api/accounts/activities module is used here (not mocked) so the test
// reads the actual label constant.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import AphoriqTheme from "../../_utils/aphoriqTheme";
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

describe("ActivityMiniCard — LINKEDIN type", () => {
  it("renders the LINKEDIN type as the LinkedIn icon, no 'LinkedIn Message'", () => {
    const { container } = render(
      <AphoriqTheme><ActivityMiniCard activity={mk()} onNavigate={vi.fn()} /></AphoriqTheme>,
    );
    expect(container.querySelector(".anticon-linkedin")).not.toBeNull();
    expect(screen.queryByText("LinkedIn Message")).not.toBeInTheDocument();
  });
});
