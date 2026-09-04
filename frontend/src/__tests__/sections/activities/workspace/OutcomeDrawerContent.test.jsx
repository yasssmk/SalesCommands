// frontend/src/__tests__/sections/activities/workspace/OutcomeDrawerContent.test.jsx
//
// O-2a — the OUTCOME drawer content: complete an activity with an outcome (+ an
// optional note), and — for CAMPAIGN activities only — a required callback date
// when CALLBACK_REQUESTED is chosen. Save posts /complete/ via completeActivity
// (backend branches on campaign_id); a campaign completion also revalidates the
// playlist. Draft in local state; nothing persists before Save.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import dayjs from "dayjs";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

// x-date-pickers — stub; expose a "pick" button firing onChange with a dayjs date.
vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: (props) => (
    <div>
      <input aria-label={props.label} />
      <button type="button" data-testid={`pick-${props.label}`} onClick={() => props.onChange(dayjs("2026-10-01"))}>
        pick {props.label}
      </button>
    </div>
  ),
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({ LocalizationProvider: ({ children }) => <>{children}</> }));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

const { closeDrawer, completeActivity, revalidateCampaignPlaylist, displaySuccessSnackbar, displayErrorSnackbar } =
  vi.hoisted(() => ({
    closeDrawer: vi.fn(),
    completeActivity: vi.fn(() => Promise.resolve({ success: true, data: {} })),
    revalidateCampaignPlaylist: vi.fn(),
    displaySuccessSnackbar: vi.fn(),
    displayErrorSnackbar: vi.fn(),
  }));

vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ isOpen: true, content: null, openDrawer: vi.fn(), closeDrawer }),
}));
vi.mock("api/accounts/activities", async (orig) => ({
  ...(await orig()),
  completeActivity: (...a) => completeActivity(...a),
}));
vi.mock("api/campaigns/campaigns", async (orig) => ({
  ...(await orig()),
  revalidateCampaignPlaylist: (...a) => revalidateCampaignPlaylist(...a),
}));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar, displayErrorSnackbar }));

import ThemeCustomization from "themes/index";
import OutcomeDrawerContent from "sections/activities/workspace/OutcomeDrawerContent";

const CAMPAIGN_ACT = {
  id: "act-c",
  activity_type: "CALL",
  campaign_detail: { id: "camp-1", name: "Q2 Outbound" },
};
const DEAL_ACT = {
  id: "act-d",
  activity_type: "CALL",
  campaign_detail: null,
  decision_cycle_detail: { id: "dc-1" },
};

function renderDrawer(activity) {
  return render(
    <ThemeCustomization>
      <OutcomeDrawerContent activity={activity} />
    </ThemeCustomization>,
  );
}

beforeEach(() => {
  closeDrawer.mockClear();
  completeActivity.mockClear();
  revalidateCampaignPlaylist.mockClear();
  displaySuccessSnackbar.mockClear();
  displayErrorSnackbar.mockClear();
});

describe("OutcomeDrawerContent — outcome required", () => {
  it("Save (Complete) is disabled until an outcome is picked", async () => {
    renderDrawer(DEAL_ACT);
    const save = screen.getByRole("button", { name: /^complete$/i });
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByTestId("outcome-pill-SUCCESSFUL"));
    await waitFor(() => expect(save).not.toBeDisabled());
  });
});

describe("OutcomeDrawerContent — campaign: callback outcome + required date", () => {
  it("offers CALLBACK_REQUESTED and reveals a required callback DatePicker", async () => {
    renderDrawer(CAMPAIGN_ACT);
    expect(screen.getByTestId("outcome-pill-CALLBACK_REQUESTED")).toBeInTheDocument();
    const save = screen.getByRole("button", { name: /^complete$/i });
    // choose callback → date required → still disabled without date
    fireEvent.click(screen.getByTestId("outcome-pill-CALLBACK_REQUESTED"));
    expect(screen.getByTestId("pick-Callback date")).toBeInTheDocument();
    await waitFor(() => expect(save).toBeDisabled());
    // pick a date → enabled
    fireEvent.click(screen.getByTestId("pick-Callback date"));
    await waitFor(() => expect(save).not.toBeDisabled());
  });

  it("Save posts completeActivity with callback_date and revalidates the playlist", async () => {
    renderDrawer(CAMPAIGN_ACT);
    fireEvent.click(screen.getByTestId("outcome-pill-CALLBACK_REQUESTED"));
    fireEvent.click(screen.getByTestId("pick-Callback date"));
    const save = screen.getByRole("button", { name: /^complete$/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);
    await waitFor(() => expect(completeActivity).toHaveBeenCalledTimes(1));
    const [id, payload] = completeActivity.mock.calls[0];
    expect(id).toBe("act-c");
    expect(payload.outcome).toBe("CALLBACK_REQUESTED");
    expect(payload.callback_date).toBe("2026-10-01");
    expect(revalidateCampaignPlaylist).toHaveBeenCalledWith("camp-1");
    await waitFor(() => expect(closeDrawer).toHaveBeenCalled());
    expect(displaySuccessSnackbar).toHaveBeenCalled();
  });
});

describe("OutcomeDrawerContent — deal: no callback", () => {
  it("does NOT offer CALLBACK_REQUESTED nor a callback DatePicker", () => {
    renderDrawer(DEAL_ACT);
    expect(screen.queryByTestId("outcome-pill-CALLBACK_REQUESTED")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pick-Callback date")).not.toBeInTheDocument();
  });

  it("Save posts completeActivity without callback_date and does NOT revalidate playlist", async () => {
    renderDrawer(DEAL_ACT);
    fireEvent.click(screen.getByTestId("outcome-pill-SUCCESSFUL"));
    const save = screen.getByRole("button", { name: /^complete$/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);
    await waitFor(() => expect(completeActivity).toHaveBeenCalledTimes(1));
    const [id, payload] = completeActivity.mock.calls[0];
    expect(id).toBe("act-d");
    expect(payload.outcome).toBe("SUCCESSFUL");
    expect(payload).not.toHaveProperty("callback_date");
    expect(revalidateCampaignPlaylist).not.toHaveBeenCalled();
    await waitFor(() => expect(closeDrawer).toHaveBeenCalled());
  });

  it("Cancel closes the drawer without completing", () => {
    renderDrawer(DEAL_ACT);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(closeDrawer).toHaveBeenCalled();
    expect(completeActivity).not.toHaveBeenCalled();
  });
});
