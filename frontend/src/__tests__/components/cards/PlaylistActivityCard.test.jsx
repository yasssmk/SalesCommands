// frontend/src/__tests__/components/cards/PlaylistActivityCard.test.jsx
//
// D4 — the "Callback pending" chip: carried by every activity of a contact
// awaiting its callback (campaign_contact_status), on the On Hold model. Guards
// the new chip and the On Hold iso.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import PlaylistActivityCard from "components/cards/PlaylistActivityCard";

afterEach(cleanup);

function mk(overrides = {}) {
  return {
    id: "a1",
    title: "Callback — Bulma",
    activity_type: "CALL",
    activity_type_display: "Call",
    status: "PLANNED",
    scheduled_date: "2026-07-24",
    sequence_position: 2,
    campaign_contact_status: null,
    is_callback_followup: false,
    is_overdue: false,
    outcome: null,
    no_answer_count: 0,
    contacts_count: 0,
    account: { id: "acc1", company_name: "Acme" },
    ...overrides,
  };
}

describe("PlaylistActivityCard — Callback pending chip", () => {
  it("shows the chip on a CALLBACK_PENDING contact's activity", () => {
    render(<PlaylistActivityCard activity={mk({ campaign_contact_status: "CALLBACK_PENDING" })} />);
    expect(screen.getByText("Callback pending")).toBeInTheDocument();
  });

  it("marks a regular (non-callback) step of the paused contact too — whole chain", () => {
    render(
      <PlaylistActivityCard
        activity={mk({
          title: "Step 3",
          is_callback_followup: false,
          sequence_position: 3,
          campaign_contact_status: "CALLBACK_PENDING",
        })}
      />,
    );
    expect(screen.getByText("Callback pending")).toBeInTheDocument();
  });

  it("shows no chip for a non-callback contact", () => {
    render(<PlaylistActivityCard activity={mk({ campaign_contact_status: "IN_PROGRESS" })} />);
    expect(screen.queryByText("Callback pending")).not.toBeInTheDocument();
  });

  it("shows no chip once the contact is resumed (IN_PROGRESS)", () => {
    render(<PlaylistActivityCard activity={mk({ campaign_contact_status: "IN_PROGRESS" })} />);
    expect(screen.queryByText("Callback pending")).not.toBeInTheDocument();
  });

  it("shows no chip when campaign_contact_status is absent (non-campaign)", () => {
    render(<PlaylistActivityCard activity={mk({ campaign_contact_status: null })} />);
    expect(screen.queryByText("Callback pending")).not.toBeInTheDocument();
  });

  it("On Hold takes precedence: paused AND callback-pending shows On Hold only", () => {
    render(
      <PlaylistActivityCard
        activity={mk({ status: "ON_HOLD", campaign_contact_status: "CALLBACK_PENDING" })}
        isGreyedOut
      />,
    );
    expect(screen.getByText("On Hold")).toBeInTheDocument();
    expect(screen.queryByText("Callback pending")).not.toBeInTheDocument();
  });

  it("On Hold alone renders without the callback chip (iso)", () => {
    render(
      <PlaylistActivityCard
        activity={mk({ status: "ON_HOLD", campaign_contact_status: "ON_HOLD" })}
        isGreyedOut
      />,
    );
    expect(screen.getByText("On Hold")).toBeInTheDocument();
    expect(screen.queryByText("Callback pending")).not.toBeInTheDocument();
  });

  it("tints a greyed (Upcoming) callback card, distinct from a plain greyed card", () => {
    // The real-world state: callback cards land in Upcoming and render greyed.
    // The tint must still win over the greyed styling (like On Hold).
    const { container: cbC } = render(
      <PlaylistActivityCard
        activity={mk({ campaign_contact_status: "CALLBACK_PENDING" })}
        isGreyedOut
      />,
    );
    const { container: plainC } = render(
      <PlaylistActivityCard
        activity={mk({ campaign_contact_status: "IN_PROGRESS" })}
        isGreyedOut
      />,
    );
    const cb = getComputedStyle(cbC.firstChild);
    const plain = getComputedStyle(plainC.firstChild);
    expect(cb.borderColor).toBeTruthy();
    expect(cb.borderColor).not.toBe(plain.borderColor);
    expect(cb.backgroundColor).not.toBe(plain.backgroundColor);
  });
});

describe("PlaylistActivityCard — completed cards (D6)", () => {
  it("shows the completion date + check icon, not the scheduled clock", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          status: "COMPLETED",
          outcome: "SUCCESSFUL",
          completed_at: "2020-01-15T12:00:00Z",
          scheduled_date: "2020-06-20T12:00:00Z",
        })}
        isGreyedOut
      />,
    );
    expect(container.querySelector('[aria-label="check-circle"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="clock-circle"]')).toBeNull();
    expect(screen.getByText("Jan 15")).toBeInTheDocument(); // completed_at
    expect(screen.queryByText("Jun 20")).not.toBeInTheDocument(); // not scheduled_date
  });

  it("check is always green (success), regardless of outcome", () => {
    const pos = render(
      <PlaylistActivityCard
        activity={mk({ status: "COMPLETED", outcome: "SUCCESSFUL", completed_at: "2020-01-15T12:00:00Z" })}
        isGreyedOut
      />,
    );
    const neg = render(
      <PlaylistActivityCard
        activity={mk({ status: "COMPLETED", outcome: "NOT_INTERESTED", completed_at: "2020-01-15T12:00:00Z" })}
        isGreyedOut
      />,
    );
    const posIcon = pos.container.querySelector('[aria-label="check-circle"]');
    const negIcon = neg.container.querySelector('[aria-label="check-circle"]');
    expect(posIcon).not.toBeNull();
    expect(negIcon).not.toBeNull();
    // Same success colour for both — a done activity is a green check, the
    // outcome is conveyed by the chip, not the check.
    expect(getComputedStyle(negIcon).color).toBe(getComputedStyle(posIcon).color);
  });

  it("leaves a PLANNED card unchanged — clock + scheduled date, no check", () => {
    const { container } = render(
      <PlaylistActivityCard activity={mk({ status: "PLANNED", scheduled_date: "2020-06-20T12:00:00Z" })} />,
    );
    expect(container.querySelector('[aria-label="clock-circle"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="check-circle"]')).toBeNull();
    expect(screen.getByText("Jun 20")).toBeInTheDocument();
  });
});
