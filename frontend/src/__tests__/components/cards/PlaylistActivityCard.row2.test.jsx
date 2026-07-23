// frontend/src/__tests__/components/cards/PlaylistActivityCard.row2.test.jsx
//
// Row 2 of the playlist activity card: "ACCOUNT — CONTACT". The contact name
// comes from contacts[0] (first_name + last_name — there is no flat
// contact_name field). A campaign activity has exactly one contact, but
// Activity.contacts is an M2M and this card is shared, so several contacts show
// a defensive "+N" rather than a silent truncation. With no contacts the
// account name stands alone, with no dangling separator.
//
// Real render, no shared-component mocks. Mirrors the existing
// PlaylistActivityCard.test.jsx mk() factory (with the ...overrides spread);
// the title here carries no em dash so it can't collide with the separator.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import PlaylistActivityCard from "components/cards/PlaylistActivityCard";

afterEach(cleanup);

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

describe("PlaylistActivityCard — Row 2 (account — contact)", () => {
  it("renders ACCOUNT — CONTACT on one row", () => {
    render(
      <PlaylistActivityCard
        activity={mk({ contacts: [{ first_name: "Jane", last_name: "Doe" }] })}
      />,
    );

    const account = screen.getByText("Acme");
    const contactLine = screen.getByText(/Jane Doe/);
    expect(contactLine).toHaveTextContent("— Jane Doe");
    // Same row (siblings under the Row 2 Stack).
    expect(account.parentElement).toBe(contactLine.parentElement);
  });

  it("shows a defensive +N when the activity carries several contacts", () => {
    render(
      <PlaylistActivityCard
        activity={mk({
          contacts: [
            { first_name: "Jane", last_name: "Doe" },
            { first_name: "John", last_name: "Smith" },
          ],
        })}
      />,
    );

    const contactLine = screen.getByText(/Jane Doe/);
    // First contact named, the rest collapsed into "+1" (length − 1).
    expect(contactLine).toHaveTextContent("— Jane Doe +1");
    // The extra contact is not spelled out.
    expect(screen.queryByText(/John Smith/)).toBeNull();
  });

  it("shows the account alone (no dangling separator) when there are no contacts", () => {
    render(<PlaylistActivityCard activity={mk({ contacts: [] })} />);

    const account = screen.getByText("Acme");
    // The Row 2 Stack holds only the account — no separator, no contact line.
    expect(account.parentElement.children.length).toBe(1);
    expect(screen.queryByText(/—/)).toBeNull();
  });
});
