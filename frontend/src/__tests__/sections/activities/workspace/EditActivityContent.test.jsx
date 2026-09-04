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

// Async selects hit live API hooks — stub them. Each exposes a "pick" button that
// fires onChange the way MUI Autocomplete does: (event, value) — proving the
// handler reads the 2nd argument. The returned id is keyed off the passed
// data-testid so owner vs invited vs contact payloads stay distinct.
vi.mock("components/AsyncSelection/AsyncUserSelect", () => ({
  default: (props) => {
    const tid = props["data-testid"];
    const newId = tid === "owner-select" ? "owner9" : "inv9";
    return (
      <div>
        <button
          type="button"
          data-testid={tid}
          data-exclude={JSON.stringify(props.excludeIds || [])}
          onClick={() => props.onChange({}, { id: newId, full_name: "Picked User" })}
        >
          pick
        </button>
        {/* returns an ALREADY-present user (u2) to exercise the dedup guard */}
        <button type="button" data-testid={`${tid}-dup`} onClick={() => props.onChange({}, { id: "u2", full_name: "Ivan Invit" })}>
          pick-dup
        </button>
      </div>
    );
  },
}));
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: (props) => {
    const tid = props["data-testid"];
    return (
      <div>
        <button
          type="button"
          data-testid={tid}
          data-exclude={JSON.stringify(props.excludeIds || [])}
          onClick={() => props.onChange({}, { id: "c9", full_name: "Picked Contact" })}
        >
          pick
        </button>
        {/* returns an ALREADY-present contact (c1) to exercise the dedup guard */}
        <button type="button" data-testid={`${tid}-dup`} onClick={() => props.onChange({}, { id: "c1", full_name: "Cara Contact" })}>
          pick-dup
        </button>
      </div>
    );
  },
}));

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
  it("renders ONE content box and does NOT render its own title (the coque owns it now)", () => {
    renderEdit();
    expect(screen.getByTestId("drawer-content-box")).toBeInTheDocument();
    // Option A: the "Edit activity" title is rendered by the coque header, not
    // by the content — so the content alone shows no drawer-title.
    expect(screen.queryByTestId("drawer-title")).not.toBeInTheDocument();
    expect(screen.queryByText("Edit activity")).not.toBeInTheDocument();
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

  it("renders the editable People section (owner / invited / contacts), no placeholder", () => {
    renderEdit();
    expect(screen.queryByTestId("people-placeholder")).not.toBeInTheDocument();
    expect(screen.getByTestId("people-section")).toBeInTheDocument();
    expect(screen.getByText("Ann Owner")).toBeInTheDocument();
    expect(screen.getByText("Ivan Invit")).toBeInTheDocument();
    expect(screen.getByText("Cara Contact")).toBeInTheDocument();
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
    // People is now part of the PATCH (SE-c) — seeded from the activity
    expect(payload.owner_id).toBe("u1");
    expect(payload.invited_user_ids).toEqual(["u2"]);
    expect(payload.contact_ids).toEqual(["c1"]);
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

describe("EditActivityContent — date section ✓/✗ (local read/edit, no PATCH)", () => {
  it("edit mode shows ✓ and ✗; ✓ returns to READ keeping the draft, no updateActivity", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-date"));
    // in edit: confirm + cancel controls present
    expect(screen.getByTestId("date-confirm")).toBeInTheDocument();
    expect(screen.getByTestId("date-cancel")).toBeInTheDocument();
    // change the scheduled date via the stubbed picker (label "Scheduled date")
    fireEvent.click(screen.getByTestId("pick-Scheduled date"));
    // validate the section
    fireEvent.click(screen.getByTestId("date-confirm"));
    // back to READ: pickers gone, new date shown, NO patch
    await waitFor(() => expect(screen.queryByTestId("pick-Scheduled date")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-date")).toBeInTheDocument();
    expect(screen.getByText(/Oct 1, 2026/)).toBeInTheDocument();
    expect(updateActivity).not.toHaveBeenCalled();
  });

  it("✗ returns to READ restoring the date/time/mode from before editing", async () => {
    renderEdit(); // scheduled 2026-09-10 14:30
    fireEvent.doubleClick(screen.getByTestId("inline-read-date"));
    // switch to Due Date and pick a due date
    fireEvent.click(screen.getByRole("button", { name: /due date/i }));
    fireEvent.click(screen.getByTestId("pick-Due date"));
    // discard the in-flight edit
    fireEvent.click(screen.getByTestId("date-cancel"));
    await waitFor(() => expect(screen.queryByTestId("pick-Due date")).not.toBeInTheDocument());
    // restored: scheduled mode + original date + time, NOT the due date
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByText(/Sep 10, 2026 · 2:30 PM/)).toBeInTheDocument();
    expect(screen.queryByText(/Oct 1, 2026/)).not.toBeInTheDocument();
    expect(updateActivity).not.toHaveBeenCalled();
  });

  it("✓ keeps the draft so the GLOBAL Save then PATCHes the confirmed date", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-date"));
    fireEvent.click(screen.getByTestId("pick-Scheduled date"));
    fireEvent.click(screen.getByTestId("date-confirm"));
    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);
    await waitFor(() => expect(updateActivity).toHaveBeenCalledTimes(1));
    expect(updateActivity.mock.calls[0][1].scheduled_date).toBe("2026-10-01");
  });
});

describe("EditActivityContent — People (draft + global save, no per-row PATCH)", () => {
  it("owner filled shows a remove ✕; removing empties the slot and shows + Add owner, Save blocked", async () => {
    renderEdit();
    expect(screen.getByTestId("remove-owner")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("remove-owner"));
    // slot empty → add affordance appears, no PATCH
    expect(screen.getByTestId("add-owner")).toBeInTheDocument();
    expect(screen.queryByText("Ann Owner")).not.toBeInTheDocument();
    expect(updateActivity).not.toHaveBeenCalled();
    // owner required → Save disabled even though the form is otherwise valid+dirty
    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).toBeDisabled());
  });

  it("+ Add owner reveals AsyncUserSelect and its 2nd-arg value fills the slot", () => {
    renderEdit({ ...ACTIVITY, owner_detail: null });
    expect(screen.getByTestId("add-owner")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("add-owner"));
    fireEvent.click(screen.getByTestId("owner-select")); // fires onChange({}, {id:"owner9"})
    expect(screen.getByTestId("remove-owner")).toBeInTheDocument();
    expect(updateActivity).not.toHaveBeenCalled();
  });

  it("invited: add via AsyncUserSelect and remove a row (draft only)", () => {
    renderEdit();
    // remove the seeded invited
    fireEvent.click(screen.getByTestId("remove-invited-u2"));
    expect(screen.queryByText("Ivan Invit")).not.toBeInTheDocument();
    // add a teammate
    fireEvent.click(screen.getByTestId("add-invited"));
    fireEvent.click(screen.getByTestId("invited-select")); // {id:"inv9"}
    expect(screen.getByTestId("remove-invited-inv9")).toBeInTheDocument();
    expect(updateActivity).not.toHaveBeenCalled();
  });

  it("contacts min 1: removing the only contact blocks Save; adding one restores it", async () => {
    renderEdit();
    const save = screen.getByRole("button", { name: /save/i });
    fireEvent.click(screen.getByTestId("remove-contact-c1"));
    await waitFor(() => expect(save).toBeDisabled());
    fireEvent.click(screen.getByTestId("add-contact"));
    fireEvent.click(screen.getByTestId("contact-select")); // {id:"c9"}
    expect(screen.getByTestId("remove-contact-c9")).toBeInTheDocument();
    expect(updateActivity).not.toHaveBeenCalled();
  });

  it("global Save sends owner_id / invited_user_ids / contact_ids from the People draft", async () => {
    renderEdit();
    // add a teammate so the invited list changes → also makes the form dirty
    fireEvent.click(screen.getByTestId("add-invited"));
    fireEvent.click(screen.getByTestId("invited-select"));
    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);
    await waitFor(() => expect(updateActivity).toHaveBeenCalledTimes(1));
    const payload = updateActivity.mock.calls[0][1];
    expect(payload.owner_id).toBe("u1");
    expect(payload.invited_user_ids).toEqual(["u2", "inv9"]);
    expect(payload.contact_ids).toEqual(["c1"]);
  });
});

describe("EditActivityContent — no duplicate user/contact (exclusion + dedup)", () => {
  it("adding an already-present invited does NOT create a duplicate row", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("add-invited"));
    fireEvent.click(screen.getByTestId("invited-select-dup")); // picks u2 (already invited)
    expect(screen.getAllByText("Ivan Invit")).toHaveLength(1);
    expect(screen.getByTestId("remove-invited-u2")).toBeInTheDocument();
    expect(updateActivity).not.toHaveBeenCalled();
  });

  it("adding an already-present contact does NOT create a duplicate row", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("add-contact"));
    fireEvent.click(screen.getByTestId("contact-select-dup")); // picks c1 (already a contact)
    expect(screen.getAllByText("Cara Contact")).toHaveLength(1);
    expect(updateActivity).not.toHaveBeenCalled();
  });

  it("the contact selector excludes the already-selected contact ids", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("add-contact"));
    const excl = JSON.parse(screen.getByTestId("contact-select").getAttribute("data-exclude"));
    expect(excl).toContain("c1");
  });

  it("the invited selector excludes the current invited AND the owner", () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("add-invited"));
    const excl = JSON.parse(screen.getByTestId("invited-select").getAttribute("data-exclude"));
    expect(excl).toContain("u2"); // already invited
    expect(excl).toContain("u1"); // the owner
  });

  it("the owner selector excludes the current invited users", () => {
    renderEdit({ ...ACTIVITY, owner_detail: null });
    fireEvent.click(screen.getByTestId("add-owner"));
    const excl = JSON.parse(screen.getByTestId("owner-select").getAttribute("data-exclude"));
    expect(excl).toContain("u2");
  });
});

describe("EditActivityContent — campaign activity locks date/people (COND-1)", () => {
  const CAMPAIGN = { ...ACTIVITY, campaign_detail: { id: "camp-1", name: "Q2" } };

  it("date is read-only on a campaign activity (double-click does not open edit)", () => {
    renderEdit(CAMPAIGN);
    fireEvent.doubleClick(screen.getByTestId("inline-read-date"));
    expect(screen.queryByTestId("date-confirm")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /due date/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Sep 10, 2026/)).toBeInTheDocument(); // value still shown
  });

  it("people are read-only on a campaign activity (no remove/add) but still shown", () => {
    renderEdit(CAMPAIGN);
    expect(screen.queryByTestId("remove-owner")).not.toBeInTheDocument();
    expect(screen.queryByTestId("add-owner")).not.toBeInTheDocument();
    expect(screen.queryByTestId("add-invited")).not.toBeInTheDocument();
    expect(screen.queryByTestId("add-contact")).not.toBeInTheDocument();
    expect(screen.queryByTestId("remove-contact-c1")).not.toBeInTheDocument();
    expect(screen.getByText("Ann Owner")).toBeInTheDocument();
    expect(screen.getByText("Cara Contact")).toBeInTheDocument();
  });

  it("title / type / objective / description stay editable on a campaign activity", () => {
    renderEdit(CAMPAIGN);
    fireEvent.doubleClick(screen.getByTestId("inline-read-title"));
    expect(screen.getByTestId("inline-input-title")).toBeInTheDocument();
  });

  it("Save payload excludes the campaign-locked fields (date/owner/invited/contacts)", async () => {
    renderEdit(CAMPAIGN);
    fireEvent.doubleClick(screen.getByTestId("inline-read-title"));
    fireEvent.change(screen.getByTestId("inline-input-title"), { target: { value: "New" } });
    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);
    await waitFor(() => expect(updateActivity).toHaveBeenCalled());
    const payload = updateActivity.mock.calls[0][1];
    expect(payload.title).toBe("New");
    expect(payload).toHaveProperty("activity_type");
    expect(payload).not.toHaveProperty("scheduled_date");
    expect(payload).not.toHaveProperty("scheduled_time");
    expect(payload).not.toHaveProperty("due_date");
    expect(payload).not.toHaveProperty("owner_id");
    expect(payload).not.toHaveProperty("invited_user_ids");
    expect(payload).not.toHaveProperty("contact_ids");
  });
});
