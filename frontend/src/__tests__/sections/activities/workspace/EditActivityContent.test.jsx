// frontend/src/__tests__/sections/activities/workspace/EditActivityContent.test.jsx
//
// S2c-1 — the Activity EDIT drawer content (a shell-less node injected into the
// WorkspaceDrawer coque). Edits CONTENT fields only (no status, no cycle/step):
// title, type, scheduled date/time, due date, objective, description, owner,
// invited users, contacts. Formik + Yup; "at least one date" + "min 1 contact"
// rules; Save disabled unless valid & dirty; save via updateActivity; Cancel
// closes the coque.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

// @mui/x-date-pickers has an ESM directory import vitest can't resolve — stub
// the pickers (the payload is built from Formik values, not the picker inputs).
vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: (props) => <input aria-label={props.label} disabled={props.disabled} />,
}));
vi.mock("@mui/x-date-pickers/TimePicker", () => ({
  TimePicker: (props) => <input aria-label={props.label} disabled={props.disabled} />,
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

// Async pickers hit live API hooks — stub them; distinguish owner vs invited by `multiple`.
// The stubs also expose a "pick" button that fires onChange the way MUI
// Autocomplete does — (event, newValue) — so tests can prove the handler reads
// the 2nd argument (the value), not the 1st (the event).
vi.mock("components/AsyncSelection/AsyncUserSelect", () => ({
  default: ({ value, onChange, multiple }) => (
    <div>
      <div data-testid={multiple ? "invited-select" : "owner-select"} data-value={JSON.stringify(value)} />
      <button
        type="button"
        data-testid={multiple ? "pick-invited" : "pick-owner"}
        onClick={() => onChange({ synthetic: true }, multiple ? [{ id: "u9" }] : { id: "u9" })}
      />
    </div>
  ),
}));
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: ({ value, onChange }) => (
    <div>
      <div data-testid="contacts-select" data-value={JSON.stringify(value)} />
      <button
        type="button"
        data-testid="pick-contacts"
        onClick={() => onChange({ synthetic: true }, [{ id: "c9" }, { id: "c1" }])}
      />
    </div>
  ),
}));

// Spies used inside vi.mock factories must be hoisted (vi.mock is hoisted).
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
  owner_detail: { id: "u1", first_name: "Ann", last_name: "Owner", email: "ann@x.com" },
  invited_users_detail: [{ id: "u2", first_name: "Ivan", last_name: "Invit", email: "ivan@x.com" }],
  contacts_detail: [{ id: "c1", full_name: "Cara Contact", first_name: "Cara", last_name: "Contact" }],
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

describe("EditActivityContent — content fields, prefilled", () => {
  it("renders a section title and the content fields, prefilled from the activity", () => {
    renderEdit();
    expect(screen.getByText(/Edit activity/i)).toBeInTheDocument();
    // text fields prefilled
    expect(screen.getByDisplayValue("Discovery call")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Qualify budget")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Intro call")).toBeInTheDocument();
    // type select shows the human label (DEMO-capable map)
    expect(screen.getByText("Phone Call")).toBeInTheDocument();
    // async selects prefilled with the *_detail objects
    expect(screen.getByTestId("owner-select").getAttribute("data-value")).toContain("u1");
    expect(screen.getByTestId("invited-select").getAttribute("data-value")).toContain("u2");
    expect(screen.getByTestId("contacts-select").getAttribute("data-value")).toContain("c1");
  });

  it("does NOT render a status or a cycle/step field", () => {
    renderEdit();
    expect(screen.queryByText(/^Status$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Pipeline step/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Decision cycle/i)).not.toBeInTheDocument();
  });
});

describe("EditActivityContent — validation gates the Save button", () => {
  it("Save is disabled until the form is valid AND dirty", async () => {
    renderEdit();
    const save = screen.getByRole("button", { name: /save/i });
    expect(save).toBeDisabled(); // valid but pristine
    fireEvent.change(screen.getByDisplayValue("Discovery call"), { target: { value: "Discovery call!" } });
    await waitFor(() => expect(save).not.toBeDisabled());
  });

  it("keeps Save disabled when BOTH dates are empty (at-least-one-date rule)", async () => {
    renderEdit({ ...ACTIVITY, scheduled_date: null, scheduled_time: null, due_date: null });
    const save = screen.getByRole("button", { name: /save/i });
    fireEvent.change(screen.getByDisplayValue("Discovery call"), { target: { value: "Changed" } });
    // still invalid → still disabled
    await waitFor(() => expect(screen.getByDisplayValue("Changed")).toBeInTheDocument());
    expect(save).toBeDisabled();
  });

  it("keeps Save disabled when contacts is empty (min 1 contact rule)", async () => {
    renderEdit({ ...ACTIVITY, contacts_detail: [] });
    const save = screen.getByRole("button", { name: /save/i });
    fireEvent.change(screen.getByDisplayValue("Discovery call"), { target: { value: "Changed" } });
    await waitFor(() => expect(screen.getByDisplayValue("Changed")).toBeInTheDocument());
    expect(save).toBeDisabled();
  });
});

describe("EditActivityContent — save + cancel", () => {
  it("submits the mapped payload via updateActivity, then closes the coque", async () => {
    renderEdit();
    fireEvent.change(screen.getByDisplayValue("Discovery call"), { target: { value: "New title" } });
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
    expect(payload.owner_id).toBe("u1");
    expect(payload.invited_user_ids).toEqual(["u2"]);
    expect(payload.contact_ids).toEqual(["c1"]);
    await waitFor(() => expect(closeDrawer).toHaveBeenCalled());
    expect(displaySuccessSnackbar).toHaveBeenCalled();
  });

  it("Cancel closes the coque without saving", () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(closeDrawer).toHaveBeenCalled();
    expect(updateActivity).not.toHaveBeenCalled();
  });
});

describe("EditActivityContent — onChange reads the value (2nd arg), never the event", () => {
  it("selecting contacts stores the ARRAY value (not the event) and saves those ids", async () => {
    renderEdit();
    // simulate MUI Autocomplete multiple onChange: (event, newValueArray)
    fireEvent.click(screen.getByTestId("pick-contacts"));
    await waitFor(() => {
      const dv = screen.getByTestId("contacts-select").getAttribute("data-value");
      expect(JSON.parse(dv)).toBeInstanceOf(Array); // the value, not the {synthetic} event
      expect(dv).toContain("c9");
    });
    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);
    await waitFor(() => expect(updateActivity).toHaveBeenCalled());
    expect(updateActivity.mock.calls[0][1].contact_ids).toEqual(["c9", "c1"]);
  });

  it("selecting owner stores the value object (2nd arg) → owner_id in the payload", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("pick-owner"));
    await waitFor(() =>
      expect(screen.getByTestId("owner-select").getAttribute("data-value")).toContain("u9"),
    );
    const save = screen.getByRole("button", { name: /save/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);
    await waitFor(() => expect(updateActivity).toHaveBeenCalled());
    expect(updateActivity.mock.calls[0][1].owner_id).toBe("u9");
  });
});
