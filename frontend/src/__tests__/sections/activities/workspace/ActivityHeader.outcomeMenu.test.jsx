// frontend/src/__tests__/sections/activities/workspace/ActivityHeader.outcomeMenu.test.jsx
//
// O-2b — the adaptive ⋮ menu: Planned → Complete (above Edit) + Cancel; Completed
// / Cancelled → Reopen (no Complete). Complete opens the OutcomeDrawerContent in
// the coque (openDrawer + title). Reopen → reopenActivity (business error on a
// closed cycle). Cancel → cancelActivity via a light confirm.

import { render, renderHook, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const openDrawer = vi.fn();
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ isOpen: false, content: null, openDrawer, closeDrawer: vi.fn() }),
}));
vi.mock("sections/activities/workspace/EditActivityContent", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/OutcomeDrawerContent", () => ({
  default: () => <div data-testid="outcome-drawer-content" />,
}));

const { reopenActivity, cancelActivity, displaySuccessSnackbar, displayErrorSnackbar } = vi.hoisted(() => ({
  reopenActivity: vi.fn(() => Promise.resolve({ success: true, data: {} })),
  cancelActivity: vi.fn(() => Promise.resolve({ success: true, data: {} })),
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
vi.mock("api/accounts/activities", async (orig) => ({
  ...(await orig()),
  reopenActivity: (...a) => reopenActivity(...a),
  cancelActivity: (...a) => cancelActivity(...a),
}));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar, displayErrorSnackbar }));

import ThemeCustomization from "themes/index";
import useActivityHeaderProps from "sections/activities/workspace/ActivityHeader";

const base = {
  id: "act-1",
  activity_type: "CALL",
  status: "PLANNED",
  title: "Discovery call",
  account_detail: { id: "acc-1", company_name: "ACME" },
};

const wrapper = ({ children }) => <ThemeCustomization>{children}</ThemeCustomization>;

function Harness({ activity }) {
  const props = useActivityHeaderProps({ activity });
  return (
    <div>
      {props.headerActions}
      {props.modals}
    </div>
  );
}

function renderHarness(activity) {
  return render(
    <ThemeCustomization>
      <Harness activity={activity} />
    </ThemeCustomization>,
  );
}

beforeEach(() => {
  openDrawer.mockClear();
  reopenActivity.mockClear();
  cancelActivity.mockClear();
  displaySuccessSnackbar.mockClear();
  displayErrorSnackbar.mockClear();
});

describe("ActivityHeader ⋮ — adaptive by status", () => {
  it("PLANNED: Complete + Edit + Cancel; no Reopen", async () => {
    renderHarness(base);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Edit")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
    expect(screen.queryByText("Reopen")).not.toBeInTheDocument();
  });

  it("COMPLETED: Reopen + Edit; no Complete / Cancel", async () => {
    renderHarness({ ...base, status: "COMPLETED" });
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Reopen")).toBeInTheDocument();
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
    expect(screen.queryByText("Cancel")).not.toBeInTheDocument();
  });

  it("CANCELLED: Reopen present", async () => {
    renderHarness({ ...base, status: "CANCELLED" });
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Reopen")).toBeInTheDocument();
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
  });

  it("Complete opens the OutcomeDrawerContent in the coque with the title", async () => {
    renderHarness(base);
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getByText("Complete"));
    expect(openDrawer).toHaveBeenCalledTimes(1);
    const [node, options] = openDrawer.mock.calls[0];
    expect(node.props.activity).toBe(base);
    expect(options).toEqual({ title: "Complete activity" });
  });

  it("Reopen calls reopenActivity (success → snackbar)", async () => {
    renderHarness({ ...base, status: "COMPLETED" });
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getByText("Reopen"));
    await waitFor(() => expect(reopenActivity).toHaveBeenCalledWith("act-1"));
    await waitFor(() => expect(displaySuccessSnackbar).toHaveBeenCalled());
  });

  it("Reopen failure (e.g. closed cycle 400) shows a business message, no crash", async () => {
    reopenActivity.mockResolvedValueOnce({ success: false, error: "Cannot reopen: cycle closed", status: 400 });
    renderHarness({ ...base, status: "COMPLETED" });
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getByText("Reopen"));
    await waitFor(() => expect(reopenActivity).toHaveBeenCalled());
    await waitFor(() => expect(displayErrorSnackbar).toHaveBeenCalled());
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
  });

  it("Cancel → confirm → cancelActivity", async () => {
    renderHarness(base);
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getByText("Cancel"));
    // a light confirmation dialog appears with a confirm action
    const confirm = await screen.findByTestId("confirm-cancel-activity");
    fireEvent.click(confirm);
    await waitFor(() => expect(cancelActivity).toHaveBeenCalledWith("act-1", expect.any(Object)));
    await waitFor(() => expect(displaySuccessSnackbar).toHaveBeenCalled());
  });
});
