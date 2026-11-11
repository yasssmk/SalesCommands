// frontend/src/__tests__/sections/activities/workspace/ActivityNotesPanel.test.jsx
//
// Sprint « Source / Notes » — notes panel, N4: the notes panel in the REAL
// coque (WorkspaceCoque: provider + WorkspaceDrawer), reading the activity
// through the real SWR hook (useGetActivity), saving through the real
// useNoteAutosave. Only the server is faked (fetcher + the two save calls).
//   - type → pause → ONE request → « Saved · HH:mm »;
//   - closing the panel with a pending note → immediate (keepalive) flush,
//     the text is back on reopening;
//   - CANCELLED → read-only;
//   - the server refuses while typing (became CANCELLED) → ORANGE, read-only,
//     the typed text stays visible;
//   - another content opened at the top → the note keeps saving.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import { SWRConfig } from "swr";

vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));

const { server, saveActivityNotes, saveActivityNotesKeepalive, displayErrorSnackbar, displayWarningSnackbar } =
  vi.hoisted(() => {
    const server = { activity: null };
    return {
      server,
      saveActivityNotes: vi.fn(),
      saveActivityNotesKeepalive: vi.fn((id, notes) => {
        server.activity = { ...server.activity, outcome_notes: notes };
        return true;
      }),
      displayErrorSnackbar: vi.fn(),
      displayWarningSnackbar: vi.fn(),
    };
  });

vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  saveActivityNotes,
  saveActivityNotesKeepalive,
}));
vi.mock("utils/displayError", () => ({
  displayErrorSnackbar,
  displayWarningSnackbar,
  displaySuccessSnackbar: vi.fn(),
}));

import WorkspaceCoque from "../../../_utils/workspaceCoque";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import ActivityNotesPanel, { formatNotesSavedAt } from "sections/activities/workspace/ActivityNotesPanel";
import { NOTES_AUTOSAVE_DELAY_MS, clearLocalNoteWrites } from "hooks/useNoteAutosave";
import { SOURCE_LOCKED_MESSAGE } from "utils/activitySignalsLock";

// ==============================|| HARNESS ||============================== //

const ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479";
const NOW = new Date(2026, 10, 11, 10, 15, 0);

const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  if (url === `/module-activities/${ID}/`) return Promise.resolve({ data: { ...server.activity } });
  return Promise.resolve({ data: null });
};

function Trigger() {
  const { openDrawer, openNotesPanel, closeNotesPanel } = useWorkspaceDrawer();
  return (
    <div>
      <button onClick={() => openNotesPanel(<ActivityNotesPanel activityId={ID} />)}>open-notes</button>
      <button onClick={() => closeNotesPanel()}>close-notes</button>
      <button onClick={() => openDrawer(<div data-testid="other-top">other</div>, { title: "Other" })}>
        open-other
      </button>
    </div>
  );
}

const renderWorkspace = () =>
  render(
    <SWRConfig value={{ fetcher, dedupingInterval: 0, provider: () => new Map() }}>
      <WorkspaceCoque>
        <Trigger />
      </WorkspaceCoque>
    </SWRConfig>,
  );

const advance = async (ms) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

async function openNotes() {
  fireEvent.click(screen.getByText("open-notes"));
  await advance(0); // SWR resolves the activity
}

const notesBox = () => screen.queryByRole("textbox", { name: "Notes" });
const type = (text) => fireEvent.change(notesBox(), { target: { value: text } });

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  vi.clearAllMocks();
  clearLocalNoteWrites();
  server.activity = { id: ID, status: "PLANNED", outcome_notes: "First thoughts" };
  saveActivityNotes.mockImplementation(async (_id, notes) => {
    server.activity = { ...server.activity, outcome_notes: notes };
    return { success: true, data: { outcome_notes: notes, updated_at: new Date().toISOString() } };
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

// ==============================|| TESTS ||============================== //

describe("notes panel — autosave in the coque", () => {
  it("shows the server's note, always editable, no Save / Cancel", async () => {
    renderWorkspace();
    await openNotes();
    expect(notesBox()).toHaveValue("First thoughts");
    expect(screen.queryByRole("button", { name: /save/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
  });

  it("type → pause → ONE request with the whole note → « Saved · HH:mm »", async () => {
    renderWorkspace();
    await openNotes();
    type("First thoughts, then");
    type("First thoughts, then more");
    await advance(NOTES_AUTOSAVE_DELAY_MS - 1);
    expect(saveActivityNotes).not.toHaveBeenCalled();
    expect(screen.queryByTestId("notes-saved-indicator")).not.toBeInTheDocument();
    await advance(1);
    expect(saveActivityNotes).toHaveBeenCalledTimes(1);
    expect(saveActivityNotes).toHaveBeenCalledWith(ID, "First thoughts, then more");
    expect(screen.getByTestId("notes-saved-indicator")).toHaveTextContent("Saved · 10:15");
    // the text typed is untouched by the cache update
    expect(notesBox()).toHaveValue("First thoughts, then more");
  });

  it("the indicator hides while a new change is pending, back once saved", async () => {
    renderWorkspace();
    await openNotes();
    type("v1");
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(screen.getByTestId("notes-saved-indicator")).toBeInTheDocument();
    type("v1, v2");
    expect(screen.queryByTestId("notes-saved-indicator")).not.toBeInTheDocument();
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(screen.getByTestId("notes-saved-indicator")).toBeInTheDocument();
  });

  it("closing the panel with a pending note → immediate keepalive flush; back on reopening", async () => {
    renderWorkspace();
    await openNotes();
    type("Typed just before closing");
    fireEvent.click(screen.getByText("close-notes"));
    expect(saveActivityNotesKeepalive).toHaveBeenCalledTimes(1);
    expect(saveActivityNotesKeepalive).toHaveBeenCalledWith(ID, "Typed just before closing", expect.any(Function));
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).not.toHaveBeenCalled();
    await openNotes();
    expect(notesBox()).toHaveValue("Typed just before closing");
  });

  it("another content opened at the top → the note keeps saving", async () => {
    renderWorkspace();
    await openNotes();
    type("While another drawer opens");
    fireEvent.click(screen.getByText("open-other"));
    expect(screen.getByTestId("other-top")).toBeInTheDocument();
    expect(saveActivityNotesKeepalive).not.toHaveBeenCalled();
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).toHaveBeenCalledWith(ID, "While another drawer opens");
    expect(screen.getByTestId("notes-saved-indicator")).toBeInTheDocument();
  });
});

describe("notes panel — never older than the last local write (N4b)", () => {
  it("the field's accessible name is « Notes »", async () => {
    renderWorkspace();
    await openNotes();
    expect(screen.getByRole("textbox", { name: "Notes" })).toBeInTheDocument();
  });

  it("closed with a pending note, reopened on a STALE server answer → the local text stays, nothing is lost", async () => {
    // The keepalive has not reached the server yet: the server still holds
    // (and answers) the OLD note.
    saveActivityNotesKeepalive.mockImplementation(() => true);
    renderWorkspace();
    await openNotes();
    type("Typed before closing");
    fireEvent.click(screen.getByText("close-notes"));
    expect(saveActivityNotesKeepalive).toHaveBeenCalledWith(ID, "Typed before closing", expect.any(Function));
    expect(server.activity.outcome_notes).toBe("First thoughts");

    await openNotes();
    await advance(NOTES_AUTOSAVE_DELAY_MS); // the refetch answers the stale note
    expect(notesBox()).toHaveValue("Typed before closing");

    type("Typed before closing, and more");
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(saveActivityNotes).toHaveBeenCalledTimes(1);
    expect(saveActivityNotes).toHaveBeenCalledWith(ID, "Typed before closing, and more");
  });
});

describe("notes panel — last write wins against a NEWER server note (N4b)", () => {
  it("after our confirmed save, another session's newer note is shown on reopening", async () => {
    renderWorkspace();
    await openNotes();
    type("Mine");
    await advance(NOTES_AUTOSAVE_DELAY_MS); // confirmed at NOW
    fireEvent.click(screen.getByText("close-notes"));
    server.activity = {
      ...server.activity,
      outcome_notes: "Another session's",
      updated_at: new Date(NOW.getTime() + 60_000).toISOString(),
    };
    await openNotes();
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(notesBox()).toHaveValue("Another session's");
  });
});

describe("notes panel — CANCELLED", () => {
  it("a CANCELLED activity → read-only: the note shown, no text box", async () => {
    server.activity = { ...server.activity, status: "CANCELLED" };
    renderWorkspace();
    await openNotes();
    expect(screen.getByText("First thoughts")).toBeInTheDocument();
    expect(notesBox()).not.toBeInTheDocument();
  });

  it("the server refuses while typing (became CANCELLED) → ORANGE, read-only, text kept", async () => {
    saveActivityNotes.mockResolvedValue({ success: false, error: SOURCE_LOCKED_MESSAGE, status: 400 });
    renderWorkspace();
    await openNotes();
    type("Typed as it got cancelled");
    await advance(NOTES_AUTOSAVE_DELAY_MS);
    expect(displayWarningSnackbar).toHaveBeenCalledWith(SOURCE_LOCKED_MESSAGE);
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
    expect(notesBox()).not.toBeInTheDocument();
    expect(screen.getByText("Typed as it got cancelled")).toBeInTheDocument();
    expect(screen.queryByTestId("notes-saved-indicator")).not.toBeInTheDocument();
  });
});

describe("notes panel — the indicator's format", () => {
  it("« Saved · HH:mm » today, « Saved · d MMM HH:mm » otherwise (24 h)", () => {
    expect(formatNotesSavedAt(new Date(2026, 10, 11, 22, 5).toISOString())).toBe("Saved · 22:05");
    expect(formatNotesSavedAt(new Date(2026, 10, 3, 9, 7).toISOString())).toBe("Saved · 3 Nov 09:07");
  });
});
