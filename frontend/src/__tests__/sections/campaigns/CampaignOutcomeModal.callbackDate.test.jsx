// frontend/src/__tests__/sections/campaigns/CampaignOutcomeModal.callbackDate.test.jsx
//
// The callback date the rep picks is a calendar day, so the submitted payload
// must carry that exact day. The previous code formatted it with toISOString(),
// which converts to UTC first and ships the day before for any timezone east of
// UTC. This test pins the runtime to a fixed UTC+2 zone and proves a date picked
// on the 26th leaves the modal as "2026-07-26", not "2026-07-25".

// Fixed UTC+2 the whole year (POSIX sign is inverted: Etc/GMT-2 == UTC+02:00).
// Must be set before any date is computed.
process.env.TZ = "Etc/GMT-2";

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import dayjs from "dayjs";

// ==============================|| MOCKS ||============================== //

vi.mock("api/campaigns/campaigns", () => ({
  useGetCompletedActivities: () => ({
    activities: [],
    completedActivitiesLoading: false,
  }),
  completePlaylistActivity: vi.fn(() => Promise.resolve({ success: true })),
  cancelPlannedActivities: vi.fn(() => Promise.resolve({ success: true })),
  recordCallNoAnswer: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displayErrorSnackbar: vi.fn(),
  displaySuccessSnackbar: vi.fn(),
}));

// The nested ActivityModal is never exercised on the callback path; stub it to
// keep the render light and free of its dependency chain.
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: () => null,
}));

// The x-date-pickers barrel pulls a directory import of @mui/material/styles that
// vitest's ESM resolver can't follow; stub the provider/adapter to no-ops.
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => children,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

// Driving the real MUI calendar in jsdom is impractical; stub the DatePicker with
// a button that emits exactly what AdapterDayjs emits — a dayjs at LOCAL midnight
// of the picked calendar day (here the 26th).
vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: ({ onChange }) => (
    <button
      type="button"
      data-testid="pick-callback-26"
      onClick={() => onChange(dayjs("2026-07-26"))}
    >
      pick 26
    </button>
  ),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import CampaignOutcomeModal from "sections/campaigns/CampaignOutcomeModal";
import { completePlaylistActivity } from "api/campaigns/campaigns";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const modeBActivity = {
  id: "act-1",
  title: "Callback — Acme",
  activity_type: "CALL",
  contacts: [],
  campaign_contact_id: "cc-1",
};

// ==============================|| TESTS ||============================== //

describe("CampaignOutcomeModal — callback date is sent in local time", () => {
  it("a date picked on the 26th in UTC+2 ships as 2026-07-26, not the UTC-shifted 25th", async () => {
    render(
      <CampaignOutcomeModal
        open
        activity={modeBActivity}
        campaignId="camp-1"
        onClose={() => {}}
      />,
    );

    // Sanity: the pre-fix path (toISOString) would have shipped the previous day
    // under UTC+2 — this is the exact regression the fix guards against.
    expect(dayjs("2026-07-26").toISOString().split("T")[0]).toBe("2026-07-25");

    // Step GROUP: choose the Callback outcome (auto-advances to the detail step).
    fireEvent.click(screen.getByText("Callback"));
    // Step DETAIL: pick the 26th, then submit.
    fireEvent.click(screen.getByTestId("pick-callback-26"));
    fireEvent.click(screen.getByRole("button", { name: "Complete" }));

    await waitFor(() => expect(completePlaylistActivity).toHaveBeenCalledTimes(1));

    const [, , payload] = completePlaylistActivity.mock.calls[0];
    expect(payload.callback_date).toBe("2026-07-26");
    expect(payload.callback_date).not.toBe("2026-07-25");
  });
});

// ==============================|| « SOURCE / NOTES » 1.5 — NO NOTE AT CLOSURE ||============================== //
// PO: the activity's notes are filled throughout its lifecycle (Source band),
// never at closure — the campaign outcome steps carry no note field, and
// neither the completion nor the no-answer call sends one.

import { recordCallNoAnswer } from "api/campaigns/campaigns";

describe("CampaignOutcomeModal — no note at closure", () => {
  it("the detail step has no note field, and the completion sends none", async () => {
    render(
      <CampaignOutcomeModal open activity={modeBActivity} campaignId="camp-1" onClose={() => {}} />,
    );
    fireEvent.click(screen.getByText("Callback"));
    expect(screen.queryByLabelText(/notes/i)).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
    fireEvent.click(screen.getByTestId("pick-callback-26"));
    fireEvent.click(screen.getByRole("button", { name: "Complete" }));
    await waitFor(() => expect(completePlaylistActivity).toHaveBeenCalledTimes(1));
    const [, , payload] = completePlaylistActivity.mock.calls[0];
    expect(payload).not.toHaveProperty("outcome_notes");
  });

  it("a no-answer on a call records the attempt without a note", async () => {
    render(
      <CampaignOutcomeModal open activity={modeBActivity} campaignId="camp-1" onClose={() => {}} />,
    );
    fireEvent.click(screen.getByText("No Answer"));
    expect(screen.queryByLabelText(/notes/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Complete" }));
    await waitFor(() => expect(recordCallNoAnswer).toHaveBeenCalledTimes(1));
    expect(recordCallNoAnswer.mock.calls[0]).toEqual(["act-1"]);
  });
});

// ==============================|| « SOURCE / NOTES » 1.5b — AN EMPTY DETAIL STEP IS SKIPPED ||============================== //
// PO: with no note at closure, the « Successful » group's « Add details » step
// has nothing left — it is SKIPPED (forward and Back). The groups that still
// carry something (Callback date, No Answer notice, the Fail options) keep it.

describe("CampaignOutcomeModal — the empty « Add details » step is skipped", () => {
  const renderModal = () =>
    render(<CampaignOutcomeModal open activity={modeBActivity} campaignId="camp-1" onClose={() => {}} />);

  it("Successful goes straight to the next-step prompt, then completes with the right payload", async () => {
    renderModal();
    fireEvent.click(screen.getByText("Successful"));
    expect(screen.queryByText("Add details")).toBeNull();
    expect(screen.getByText("Create a next step?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(screen.getByText("Cancel other activities?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm & Complete" }));
    await waitFor(() => expect(completePlaylistActivity).toHaveBeenCalledTimes(1));
    const [activityId, campaignId, payload] = completePlaylistActivity.mock.calls[0];
    expect([activityId, campaignId, payload]).toEqual(["act-1", "camp-1", { outcome: "SUCCESSFUL" }]);
  });

  it("Back from the scope step never lands on the empty « Add details » step", () => {
    renderModal();
    fireEvent.click(screen.getByText("Successful"));
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.queryByText("Add details")).toBeNull();
    expect(screen.getByText("What was the outcome?")).toBeInTheDocument();
  });

  it.each(["Callback", "No Answer", "Not Interested / Wrong Contact"])(
    "%s keeps its « Add details » step",
    (label) => {
      renderModal();
      fireEvent.click(screen.getByText(label));
      expect(screen.getByText("Add details")).toBeInTheDocument();
    },
  );
});
