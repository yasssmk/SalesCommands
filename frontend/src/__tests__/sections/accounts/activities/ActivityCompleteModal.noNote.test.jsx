// frontend/src/__tests__/sections/accounts/activities/ActivityCompleteModal.noNote.test.jsx
//
// Sprint « Source / Notes » 1.5 — the legacy completion modal (DC / Account /
// Territory surfaces, TD-225) takes NO note at closure (PO): the activity's
// notes are filled throughout its lifecycle in the Source band. The modal
// shows the outcome only and posts { outcome }.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup, within } from "@testing-library/react";

const { completeActivity } = vi.hoisted(() => ({
  completeActivity: vi.fn(() => Promise.resolve({ success: true, data: {} })),
}));

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("components/MainCard", () => ({
  default: ({ children }) => <div data-testid="main-card">{children}</div>,
}));
vi.mock("api/accounts/activities", async (orig) => ({
  ...(await orig()),
  completeActivity: (...a) => completeActivity(...a),
}));
vi.mock("utils/displayError", () => ({
  displayErrorSnackbar: vi.fn(),
  displaySuccessSnackbar: vi.fn(),
}));

import ActivityCompleteModal from "sections/accounts/activities/ActivityCompleteModal";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

afterEach(() => {
  cleanup();
  completeActivity.mockClear();
});

const ACTIVITY = { id: "act-1", title: "Discovery call" };

function renderModal() {
  return render(
    <AphoriqTheme>
      <ActivityCompleteModal open onClose={() => {}} activity={ACTIVITY} />
    </AphoriqTheme>,
  );
}

describe("ActivityCompleteModal — no note at closure", () => {
  it("shows the outcome only — no notes field", () => {
    renderModal();
    expect(screen.getByText("Outcome")).toBeInTheDocument();
    expect(screen.queryByText("Notes")).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("posts the outcome without any note key", async () => {
    renderModal();
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(within(screen.getByRole("listbox")).getByText("Successful"));
    fireEvent.click(screen.getByRole("button", { name: /Complete$/ }));
    await waitFor(() => expect(completeActivity).toHaveBeenCalledTimes(1));
    expect(completeActivity.mock.calls[0]).toEqual(["act-1", { outcome: "SUCCESSFUL" }]);
  });
});
