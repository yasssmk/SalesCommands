// frontend/src/__tests__/sections/activities/workspace/EditActivityContent.test.jsx
//
// SE-b — the Activity EDIT drawer rebuilt on the shared DrawerContentLayout +
// InlineEditableValue. ONE content box; field groups separated by internal
// hairline filets; NO literal group titles, NO textual "Edit" — a field edits on
// DOUBLE-CLICK. A single global Save PATCHes via updateActivity; Cancel closes.
// The Date group toggles scheduled|due exclusively (switching clears the other).
// People is a read-only placeholder here (made editable in SE-c).

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

// x-date-pickers has an ESM directory import vitest can't resolve — stub them.
// Each picker exposes a "pick" button that fires its onChange with a dayjs value.
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
vi.mock("@mui/x-date-pickers/TimePicker", () => ({
  TimePicker: (props) => <input aria-label={props.label} disabled={props.disabled} />,
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

const { closeDrawer, updateActivity, displaySuccessSnackbar, displayErrorSnackbar } = vi.hoisted(() => ({
  closeDrawer: vi.fn(),
  updateActivity: vi.fn(() => Promise.resolve({ success: true, data: {} })),
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ isOpen: true, content: null, openDrawer: vi.fn(), closeDrawer }),
}));
vi.mock("api/accounts/activities", async (orig) => ({
  ...(await orig()),
  updateActivity: (...a) => updateActivity(...a),
}));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar, displayErrorSnackbar }));

import ThemeCustomization from "themes/index";
import EditActivityContent from "sections/activities/workspace/EditActivityContent";

const ACTIVITY = {
  id: "act-1",
  title: "Discovery call",
  activity_type: "CALL",
  scheduled_date: "2026-09-10",
  scheduled_time: "14:30:00",
  due_date: null,
  call_to_action: "Qualify budget",
  description: "Intro call",
  account: "acc-1",
  account_detail: { id: "acc-1", company_name: "ACME" },
  owner_detail: { id: "u1", first_name: "Ann", last_name: "Owner", full_name: "Ann Owner" },
  invited_users_detail: [{ id: "u2", full_name: "Ivan Invit" }],
  contacts_detail: [{ id: "c1", full_name: "Cara Contact" }],
};

function renderEdit(activity = ACTIVITY) {
  return render(
    <ThemeCustomization>
      <EditActivityContent activity={activity} />
    </ThemeCustomization>,
  );
}

beforeEach(() => {
  updateActivity.mockClear();
  closeDrawer.mockClear();
  displaySuccessSnackbar.mockClear();
});

describe("EditActivityContent — SE-b structure", () => {
  it("renders the DrawerContentLayout title + ONE content box", () => {
    renderEdit();
    expect(screen.getByText("Edit activity")).toHaveClass("MuiTypography-h3");
    expect(screen.getByTestId("drawer-content-box")).toBeInTheDocument();
  });

  it("has NO literal group titles and NO textual 'Edit'", () => {
    renderEdit();
    expect(screen.queryByText(/Title & type/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Objective & description/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^edit$/i })).not.toBeInTheDocument();
  });

  it("separates the groups with internal hairline filets", () => {
    renderEdit();
    expect(screen.getAllByTestId("group-filet").length).toBeGreaterThanOrEqual(3);
  });

  it("keeps People as a read-only placeholder (owner shown, not editable here)", () => {
    renderEdit();
    expect(screen.getByTestId("people-placeholder")).toBeInTheDocument();
    expect(screen.getByText("Ann Owner")).toBeInTheDocument();
  });
});

describe("EditActivityContent — double-click edit + global save", () => {
  it("edits the title on double-click and saves via updateActivity (global Save)", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-title"));
    fireEvent.change(screen.getByTestId("inline-input-title"), { target: { value: "New title" } });

    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);

    await waitFor(() => expect(updateActivity).toHaveBeenCalledTimes(1));
    const [id, payload] = updateActivity.mock.calls[0];
    expect(id).toBe("act-1");
    expect(payload.title).toBe("New title");
    expect(payload.activity_type).toBe("CALL");
    expect(payload.scheduled_date).toBe("2026-09-10");
    expect(payload.scheduled_time).toBe("14:30:00");
    expect(payload.due_date).toBeNull();
    expect(payload.call_to_action).toBe("Qualify budget");
    // People is NOT edited here → not part of this PATCH
    expect(payload).not.toHaveProperty("owner_id");
    expect(payload).not.toHaveProperty("contact_ids");
    await waitFor(() => expect(closeDrawer).toHaveBeenCalled());
    expect(displaySuccessSnackbar).toHaveBeenCalled();
  });

  it("Cancel closes the drawer without saving", () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(closeDrawer).toHaveBeenCalled();
    expect(updateActivity).not.toHaveBeenCalled();
  });

  it("disables Save when the title is cleared (title required)", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-title"));
    fireEvent.change(screen.getByTestId("inline-input-title"), { target: { value: "" } });
    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).toBeDisabled());
  });
});

describe("EditActivityContent — date toggle exclusivity (cloned mechanics)", () => {
  it("switching to Due Date clears the scheduled date+time (exclusive)", async () => {
    renderEdit();
    // enter date edit
    fireEvent.doubleClick(screen.getByTestId("inline-read-date"));
    // toggle to Due Date
    fireEvent.click(screen.getByRole("button", { name: /due date/i }));
    // set a due date via the stubbed picker
    fireEvent.click(screen.getByTestId("pick-Due date"));

    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);
    await waitFor(() => expect(updateActivity).toHaveBeenCalled());
    const payload = updateActivity.mock.calls[0][1];
    expect(payload.due_date).toBe("2026-10-01");
    expect(payload.scheduled_date).toBeNull();
    expect(payload.scheduled_time).toBeNull();
  });
});
