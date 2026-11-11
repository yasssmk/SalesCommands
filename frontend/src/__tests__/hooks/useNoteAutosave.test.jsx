// frontend/src/__tests__/hooks/useNoteAutosave.test.jsx
//
// Sprint « Source / Notes » — notes panel, N2: the note's autosave hook.
// Delay, immediate flush, serialized saves, statuses + savedAt, local cache
// update without revalidation, CANCELLED → orange (no retry), network → red
// once + a new attempt, keepalive on unmount and beforeunload, and the note
// NEVER registers in the unsaved-changes guard (PO).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

const { saveActivityNotes, saveActivityNotesKeepalive, displayErrorSnackbar, displayWarningSnackbar, registerUnsaved } =
  vi.hoisted(() => ({
    saveActivityNotes: vi.fn(),
    saveActivityNotesKeepalive: vi.fn(() => true),
    displayErrorSnackbar: vi.fn(),
    displayWarningSnackbar: vi.fn(),
    registerUnsaved: vi.fn(),
  }));

vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  saveActivityNotes,
  saveActivityNotesKeepalive,
}));
vi.mock("utils/displayError", () => ({ displayErrorSnackbar, displayWarningSnackbar }));
// The coque's registry: whatever registers an unsaved source goes through it.
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ registerUnsaved, releaseUnsaved: vi.fn() }),
}));

import useNoteAutosave, {
  clearLocalNoteWrites,
  resolveServerNote,
  NOTES_AUTOSAVE_DELAY_MS,
  NOTES_AUTOSAVE_RETRY_MS,
  NOTE_AUTOSAVE_STATUS,
} from "hooks/useNoteAutosave";
import { SOURCE_LOCKED_MESSAGE } from "utils/activitySignalsLock";

// ==============================|| HELPERS ||============================== //

const ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479";
const OTHER_ID = "0b6a3f2e-6c1d-4f5a-9e2b-7d8c9a0b1c2d";
const UPDATED_AT = "2026-11-11T10:15:00Z";

const ok = (notes) => ({ success: true, data: { outcome_notes: notes, updated_at: UPDATED_AT } });

function deferred() {
  let resolve;
  const promise = new Promise((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

function setup(props = {}) {
  const mutateActivity = vi.fn();
  const view = renderHook((p) => useNoteAutosave(p), {
    initialProps: { activityId: ID, initialValue: "Server note", mutateActivity, ...props },
  });
  return { ...view, mutateActivity };
}

const advance = async (ms) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  clearLocalNoteWrites();
  saveActivityNotes.mockImplementation(async (_id, notes) => ok(notes));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

// ==============================|| TESTS ||============================== //

describe("useNoteAutosave — the delay", () => {
  it("is 2 seconds (PO)", () => {
    expect(NOTES_AUTOSAVE_DELAY_MS).toBe(2000);
  });

  it("saves the LAST value once, 2 s after the last keystroke", async () => {
    const { result } = setup();
    act(() => result.current.schedule("a"));
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.PENDING);
    await advance(1500);
    act(() => result.current.schedule("ab"));
    await advance(1999);
    expect(saveActivityNotes).not.toHaveBeenCalled();
    await advance(1);
    expect(saveActivityNotes).toHaveBeenCalledTimes(1);
    expect(saveActivityNotes).toHaveBeenCalledWith(ID, "ab");
  });

  it("flush() saves at once", async () => {
    const { result } = setup();
    act(() => result.current.schedule("now"));
    await act(async () => {
      await result.current.flush();
    });
    expect(saveActivityNotes).toHaveBeenCalledWith(ID, "now");
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).toHaveBeenCalledTimes(1);
  });

  it("does not save the server's own value", async () => {
    const { result } = setup();
    act(() => result.current.schedule("Server note"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).not.toHaveBeenCalled();
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.IDLE);
  });
});

describe("useNoteAutosave — statuses and cache", () => {
  it("idle → pending → saving → saved, savedAt = the server's updated_at", async () => {
    const pending = deferred();
    saveActivityNotes.mockImplementation(() => pending.promise);
    const { result } = setup();
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.IDLE);
    expect(result.current.savedAt).toBeNull();
    act(() => result.current.schedule("x"));
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.PENDING);
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.SAVING);
    await act(async () => {
      pending.resolve(ok("x"));
    });
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.SAVED);
    expect(result.current.savedAt).toBe(UPDATED_AT);
  });

  it("updates the activity's cache locally, without revalidation", async () => {
    const { result, mutateActivity } = setup();
    act(() => result.current.schedule("cached"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(mutateActivity).toHaveBeenCalledTimes(1);
    const [updater, options] = mutateActivity.mock.calls[0];
    expect(options).toEqual({ revalidate: false });
    expect(updater({ data: { id: ID, title: "T", outcome_notes: "old" } })).toEqual({
      data: { id: ID, title: "T", outcome_notes: "cached", updated_at: UPDATED_AT },
    });
    expect(updater(undefined)).toBeUndefined();
  });

  it("serializes: a value typed during a save is saved right after it", async () => {
    const first = deferred();
    saveActivityNotes.mockImplementationOnce(() => first.promise);
    const { result } = setup();
    act(() => result.current.schedule("one"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    act(() => result.current.schedule("one two"));
    await act(async () => {
      await result.current.flush(); // in flight: no parallel save
    });
    expect(saveActivityNotes).toHaveBeenCalledTimes(1);
    await act(async () => {
      first.resolve(ok("one"));
    });
    expect(saveActivityNotes).toHaveBeenCalledTimes(2);
    expect(saveActivityNotes).toHaveBeenLastCalledWith(ID, "one two");
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.SAVED);
  });
});

describe("useNoteAutosave — errors", () => {
  it("CANCELLED (SOURCE_LOCKED) → ORANGE warning, locked, never retried", async () => {
    saveActivityNotes.mockResolvedValue({ success: false, error: SOURCE_LOCKED_MESSAGE, status: 400 });
    const { result } = setup();
    act(() => result.current.schedule("late"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(displayWarningSnackbar).toHaveBeenCalledWith(SOURCE_LOCKED_MESSAGE);
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.ERROR);
    expect(result.current.locked).toBe(true);
    await advance(NOTES_AUTOSAVE_RETRY_MS * 3);
    act(() => result.current.schedule("later"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).toHaveBeenCalledTimes(1);
  });

  it("network → RED once per failure streak, then a new attempt", async () => {
    const failure = { success: false, error: "Network Error", status: 0 };
    saveActivityNotes.mockResolvedValueOnce(failure).mockResolvedValueOnce(failure);
    const { result } = setup();
    act(() => result.current.schedule("typed"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(displayErrorSnackbar).toHaveBeenCalledTimes(1);
    expect(displayErrorSnackbar).toHaveBeenCalledWith(failure);
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.ERROR);
    await advance(NOTES_AUTOSAVE_RETRY_MS); // second failure: no second snackbar
    expect(saveActivityNotes).toHaveBeenCalledTimes(2);
    expect(displayErrorSnackbar).toHaveBeenCalledTimes(1);
    await advance(NOTES_AUTOSAVE_RETRY_MS); // succeeds
    expect(saveActivityNotes).toHaveBeenCalledTimes(3);
    expect(saveActivityNotes).toHaveBeenLastCalledWith(ID, "typed");
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.SAVED);
  });

  it("retry() tries again at once", async () => {
    saveActivityNotes.mockResolvedValueOnce({ success: false, error: "Server error", status: 500 });
    const { result } = setup();
    act(() => result.current.schedule("typed"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    await act(async () => {
      await result.current.retry();
    });
    expect(saveActivityNotes).toHaveBeenCalledTimes(2);
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.SAVED);
  });

  it("a locked activity (read-only panel) saves nothing", async () => {
    const { result } = setup({ locked: true });
    act(() => result.current.schedule("x"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).not.toHaveBeenCalled();
  });
});

describe("useNoteAutosave — keepalive when the page goes away", () => {
  it("unmount with an unsaved value → keepalive, no axios save", async () => {
    const { result, unmount } = setup();
    act(() => result.current.schedule("unsaved"));
    unmount();
    expect(saveActivityNotesKeepalive).toHaveBeenCalledTimes(1);
    expect(saveActivityNotesKeepalive).toHaveBeenCalledWith(ID, "unsaved", expect.any(Function));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).not.toHaveBeenCalled();
  });

  it("unmount with everything saved → no keepalive", async () => {
    const { result, unmount } = setup();
    act(() => result.current.schedule("saved"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    unmount();
    expect(saveActivityNotesKeepalive).not.toHaveBeenCalled();
  });

  it("beforeunload with an unsaved value → keepalive", () => {
    const { result } = setup();
    act(() => result.current.schedule("closing the tab"));
    window.dispatchEvent(new Event("beforeunload"));
    expect(saveActivityNotesKeepalive).toHaveBeenCalledWith(ID, "closing the tab", expect.any(Function));
  });

  it("another activity: the previous one's unsaved value goes to the previous id", () => {
    const { result, rerender, mutateActivity } = setup();
    act(() => result.current.schedule("for the first"));
    rerender({ activityId: OTHER_ID, initialValue: "", mutateActivity });
    expect(saveActivityNotesKeepalive).toHaveBeenCalledWith(ID, "for the first", expect.any(Function));
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.IDLE);
  });
});

describe("useNoteAutosave — N4 additions", () => {
  it("the keepalive flush updates the activity's cache locally (no answer will come)", () => {
    const { result, unmount, mutateActivity } = setup();
    act(() => result.current.schedule("flushed"));
    unmount();
    expect(mutateActivity).toHaveBeenCalledTimes(1);
    const [updater, options] = mutateActivity.mock.calls[0];
    expect(options).toEqual({ revalidate: false });
    expect(updater({ data: { id: ID, outcome_notes: "old" } })).toEqual({
      data: { id: ID, outcome_notes: "flushed" },
    });
  });

  it("after a switch to another activity, the keepalive leaves the new cache alone", () => {
    const { result, rerender, mutateActivity } = setup();
    act(() => result.current.schedule("for the first"));
    rerender({ activityId: OTHER_ID, initialValue: "", mutateActivity });
    expect(saveActivityNotesKeepalive).toHaveBeenCalledWith(ID, "for the first", expect.any(Function));
    expect(mutateActivity).not.toHaveBeenCalled();
  });

  it("follows a server note arriving late (nothing pending): equal to it → no save", async () => {
    const { result, rerender, mutateActivity } = setup({ initialValue: "" });
    rerender({ activityId: ID, initialValue: "Loaded later", mutateActivity });
    act(() => result.current.schedule("Loaded later"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).not.toHaveBeenCalled();
    act(() => result.current.schedule(""));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).toHaveBeenCalledWith(ID, "");
  });

  it("a server note arriving while a value is pending does not swallow it", async () => {
    const { result, rerender, mutateActivity } = setup();
    act(() => result.current.schedule("Mine"));
    rerender({ activityId: ID, initialValue: "Mine", mutateActivity });
    rerender({ activityId: ID, initialValue: "Theirs", mutateActivity });
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).toHaveBeenCalledWith(ID, "Mine");
  });
});

describe("useNoteAutosave — never older than the last local write (N4b)", () => {
  const T = "2026-11-11T10:15:00Z";
  const BEFORE = "2026-11-11T10:14:59Z";
  const AFTER = "2026-11-11T10:16:00Z";

  it("no local write → the server's note", () => {
    expect(resolveServerNote(ID, "Server", BEFORE)).toBe("Server");
  });

  it("a confirmed write at T: an OLDER server note is refused, a newer one accepted", async () => {
    const { result, rerender, mutateActivity } = setup();
    act(() => result.current.schedule("Mine"));
    await advance(NOTES_AUTOSAVE_DELAY_MS); // confirmed with updated_at = T
    rerender({ activityId: ID, initialValue: "Server note", serverUpdatedAt: BEFORE, mutateActivity });
    expect(result.current.note).toBe("Mine");
    rerender({ activityId: ID, initialValue: "Another session's", serverUpdatedAt: AFTER, mutateActivity });
    expect(result.current.note).toBe("Another session's");
  });

  it("an UNCONFIRMED keepalive: a remount on the stale note shows the local one", () => {
    const first = setup();
    act(() => first.result.current.schedule("Flushed"));
    first.unmount();
    const { result } = renderHook((p) => useNoteAutosave(p), {
      initialProps: { activityId: ID, initialValue: "Server note", serverUpdatedAt: AFTER, mutateActivity: vi.fn() },
    });
    expect(result.current.note).toBe("Flushed");
  });

  it("the stale note is not the saved reference: the next keystroke sends local + new", async () => {
    const first = setup();
    act(() => first.result.current.schedule("Flushed"));
    first.unmount();
    const { result } = renderHook((p) => useNoteAutosave(p), {
      initialProps: { activityId: ID, initialValue: "Server note", mutateActivity: vi.fn() },
    });
    act(() => result.current.schedule("Flushed")); // unchanged: nothing to send
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).not.toHaveBeenCalled();
    act(() => result.current.schedule("Flushed + new"));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).toHaveBeenCalledWith(ID, "Flushed + new");
  });

  it("the keepalive's answer confirms the write: then the server's clock decides", () => {
    saveActivityNotesKeepalive.mockImplementationOnce((_id, notes, onDone) => {
      onDone({ success: true, data: { outcome_notes: notes, updated_at: T } });
      return true;
    });
    const first = setup();
    act(() => first.result.current.schedule("Flushed"));
    first.unmount();
    expect(resolveServerNote(ID, "Server note", BEFORE)).toBe("Flushed");
    expect(resolveServerNote(ID, "Another session's", AFTER)).toBe("Another session's");
  });

  it("a server note at EXACTLY the confirmed time is accepted (« at least »)", () => {
    saveActivityNotesKeepalive.mockImplementationOnce((_id, notes, onDone) => {
      onDone({ success: true, data: { outcome_notes: notes, updated_at: T } });
      return true;
    });
    const first = setup();
    act(() => first.result.current.schedule("Flushed"));
    first.unmount();
    expect(resolveServerNote(ID, "Same instant, other session", T)).toBe("Same instant, other session");
  });

  it("an OLDER write's late confirmation does not override a newer write", async () => {
    let confirmFirst;
    saveActivityNotesKeepalive.mockImplementationOnce((_id, _notes, onDone) => {
      confirmFirst = onDone;
      return true;
    });
    const first = setup();
    act(() => first.result.current.schedule("A"));
    first.unmount(); // keepalive A, not answered yet
    const pending = deferred();
    saveActivityNotes.mockImplementationOnce(() => pending.promise);
    const { result } = renderHook((p) => useNoteAutosave(p), {
      initialProps: { activityId: ID, initialValue: "A", mutateActivity: vi.fn() },
    });
    act(() => result.current.schedule("A then B"));
    await advance(NOTES_AUTOSAVE_DELAY_MS); // save B in flight
    confirmFirst({ success: true, data: { outcome_notes: "A", updated_at: T } });
    expect(resolveServerNote(ID, "Old", BEFORE)).toBe("A then B");
  });

  it("a failed keepalive stays unconfirmed: the local value is kept", () => {
    saveActivityNotesKeepalive.mockImplementationOnce((_id, _notes, onDone) => {
      onDone({ success: false, status: 0 });
      return true;
    });
    const first = setup();
    act(() => first.result.current.schedule("Flushed"));
    first.unmount();
    expect(resolveServerNote(ID, "Another session's", AFTER)).toBe("Flushed");
  });
});

describe("useNoteAutosave — not an unsaved change (PO)", () => {
  it("never registers in the unsaved-changes guard", async () => {
    const { result } = setup();
    act(() => result.current.schedule("typing"));
    expect(result.current.status).toBe(NOTE_AUTOSAVE_STATUS.PENDING);
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(registerUnsaved).not.toHaveBeenCalled();
  });
});
