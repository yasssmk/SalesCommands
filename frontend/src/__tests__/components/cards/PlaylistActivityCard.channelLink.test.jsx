// frontend/src/__tests__/components/cards/PlaylistActivityCard.channelLink.test.jsx
//
// Channel coordinate as a click-to-act link on the playlist card: the single
// coordinate matching the activity's channel is rendered clickable —
//   CALL     -> tel:<phone_number>
//   EMAIL    -> mailto:<email>
//   LINKEDIN -> external LinkedIn link (new tab)
// Only the channel's own coordinate is shown; an empty field renders nothing
// (the gap is intentional — it signals the data no longer exists). The click
// must not bubble to the card's own navigation (stopPropagation).
//
// Real render, next/navigation mocked globally (vitest.setup.js).

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { useRouter } from "next/navigation";

import PlaylistActivityCard from "components/cards/PlaylistActivityCard";

afterEach(cleanup);

// Stable push spy so the stopPropagation test can assert the card did not route.
const push = vi.fn();
beforeEach(() => {
  push.mockClear();
  vi.mocked(useRouter).mockReturnValue({
    push,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  });
});

function mk(overrides = {}) {
  return {
    id: "a1",
    title: "Follow up",
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
    account: { id: "acc1", company_name: "Acme" },
    contacts: [],
    ...overrides,
  };
}

const contact = (extra = {}) => ({
  first_name: "Jane",
  last_name: "Doe",
  email: "",
  phone_number: "",
  linkedin: "",
  ...extra,
});

describe("PlaylistActivityCard — channel coordinate link", () => {
  it("CALL renders the phone_number as a tel: link", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "CALL",
          contacts: [contact({ phone_number: "+14155550123" })],
        })}
      />,
    );
    const link = container.querySelector('a[href="tel:+14155550123"]');
    expect(link).not.toBeNull();
  });

  it("EMAIL renders the email as a mailto: link", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "EMAIL",
          contacts: [contact({ email: "jane@example.com" })],
        })}
      />,
    );
    const link = container.querySelector('a[href="mailto:jane@example.com"]');
    expect(link).not.toBeNull();
  });

  it("LINKEDIN renders an external link (new tab)", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "LINKEDIN",
          contacts: [contact({ linkedin: "https://linkedin.com/in/jane-doe" })],
        })}
      />,
    );
    const link = container.querySelector(
      'a[href="https://linkedin.com/in/jane-doe"]',
    );
    expect(link).not.toBeNull();
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("CALL with no phone_number renders NO tel: link (empty is intentional)", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "CALL",
          contacts: [contact({ phone_number: "" })],
        })}
      />,
    );
    expect(container.querySelector('a[href^="tel:"]')).toBeNull();
  });

  it("shows only the channel coordinate — an EMAIL card exposes no tel: link even if the phone exists", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "EMAIL",
          contacts: [
            contact({ email: "jane@example.com", phone_number: "+14155550123" }),
          ],
        })}
      />,
    );
    expect(container.querySelector('a[href="mailto:jane@example.com"]')).not.toBeNull();
    expect(container.querySelector('a[href^="tel:"]')).toBeNull();
  });

  it("clicking the coordinate does not navigate to the activity detail (stopPropagation)", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "CALL",
          contacts: [contact({ phone_number: "+14155550123" })],
        })}
      />,
    );
    const link = container.querySelector('a[href="tel:+14155550123"]');
    fireEvent.click(link);
    expect(push).not.toHaveBeenCalled();
  });
});

describe("PlaylistActivityCard — absent coordinate renders nothing, no fallback", () => {
  // The payload sends '' for an absent coordinate (A-1); '' must be treated as
  // absent, identically on the three channels. The empty is intentional — it
  // tells the rep the data no longer exists — and never falls back to another
  // coordinate. The card renders exactly one <a> (the channel link) when a
  // coordinate is present, so its absence means no <a> at all.

  it("EMAIL with no email renders NO mailto: link", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "EMAIL",
          contacts: [contact({ email: "" })],
        })}
      />,
    );
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull();
    expect(container.querySelector("a")).toBeNull();
  });

  it("LINKEDIN with no linkedin renders NO external link", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "LINKEDIN",
          contacts: [contact({ linkedin: "" })],
        })}
      />,
    );
    expect(container.querySelector('a[target="_blank"]')).toBeNull();
    expect(container.querySelector("a")).toBeNull();
  });

  it("CALL with no phone_number renders NO tel: link (A-2 regression guard)", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "CALL",
          contacts: [contact({ phone_number: "" })],
        })}
      />,
    );
    expect(container.querySelector('a[href^="tel:"]')).toBeNull();
  });

  it("NO FALLBACK: CALL without phone but WITH email and linkedin renders no link at all", () => {
    const { container } = render(
      <PlaylistActivityCard
        activity={mk({
          activity_type: "CALL",
          contacts: [
            contact({
              phone_number: "",
              email: "jane@example.com",
              linkedin: "https://linkedin.com/in/jane-doe",
            }),
          ],
        })}
      />,
    );
    // The channel is CALL and its coordinate is empty -> nothing clickable.
    // The present email/linkedin must NOT be borrowed as a fallback.
    expect(container.querySelector('a[href^="tel:"]')).toBeNull();
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull();
    expect(container.querySelector('a[target="_blank"]')).toBeNull();
    expect(container.querySelector("a")).toBeNull();
  });
});
