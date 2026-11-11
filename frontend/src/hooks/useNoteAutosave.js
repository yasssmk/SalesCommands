// frontend/src/hooks/useNoteAutosave.js
//
// Sprint « Source / Notes » — notes panel, N2: the AUTOSAVE of the activity's
// note (one note per activity, outcome_notes). New element (no debounce /
// autosave pattern in the codebase): every other field saves on an explicit
// Save (EditableTextBlock).
//
//   const { note, status, savedAt, locked, schedule, flush, retry } =
//     useNoteAutosave({ activityId, initialValue, serverUpdatedAt, locked, mutateActivity });
//
//   - initialValue: the note the server holds (activity.outcome_notes) — a
//     value equal to it is not saved;
//
//   - schedule(value): the note changed → saved NOTES_AUTOSAVE_DELAY_MS after
//     the last keystroke (status "pending");
//   - flush(): save NOW (blur, closing the panel, navigation…);
//   - unmount / beforeunload with an unsaved value → a KEEPALIVE request
//     (saveActivityNotesKeepalive), the only one that survives the page.
//
// Statuses: idle → pending → saving → saved (savedAt = the server's
// updated_at) | error. Saves are serialized: a value typed during a save is
// saved right after it.
// Errors: the CANCELLED lock (the server's SOURCE_LOCKED) is a business rule
// → ORANGE warning, `locked` true, no retry; anything else (network, server)
// → RED error once per failure streak, and a new attempt after
// NOTES_AUTOSAVE_RETRY_MS (retry() for an immediate one).
// The cache of the activity is updated LOCALLY (mutate(…, { revalidate:
// false })) — no refetch at every pause.
// The note does NOT register in useUnsavedChanges (PO): it is never « lost »,
// so no confirmation — the guard's navigations flush it instead.
//
// N4b — ONE rule: a server note OLDER than the last local write of the same
// activity is never accepted. Every send (keepalive included) records that
// write (LOCAL_NOTE_WRITES — module level: it outlives the panel, closed then
// reopened); its confirmation carries the server's updated_at. A server note
// is accepted only if its updated_at is at least that one (the same clock —
// the server's); while the write is unconfirmed, the local value stays.
// `note` = the note to show (the server's, or the local one it lags behind).

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  saveActivityNotes,
  saveActivityNotesKeepalive,
} from "api/accounts/activities";
import {
  displayErrorSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";
import { SOURCE_LOCKED_MESSAGE } from "utils/activitySignalsLock";

/** Pause in typing after which the note is saved (PO: 2 s). */
export const NOTES_AUTOSAVE_DELAY_MS = 2000;
/** Delay of the automatic new attempt after a failed save. */
export const NOTES_AUTOSAVE_RETRY_MS = 5000;

export const NOTE_AUTOSAVE_STATUS = {
  IDLE: "idle",
  PENDING: "pending",
  SAVING: "saving",
  SAVED: "saved",
  ERROR: "error",
};

const isSourceLocked = (result) => result?.error === SOURCE_LOCKED_MESSAGE;

// N4b — activityId → { value, updatedAt } : the last local write (updatedAt =
// the server's answer; null while unconfirmed).
const LOCAL_NOTE_WRITES = new Map();

/** Tests only: forget the local writes. */
export function clearLocalNoteWrites() {
  LOCAL_NOTE_WRITES.clear();
}

const recordWrite = (id, value) => LOCAL_NOTE_WRITES.set(id, { value, updatedAt: null });

const confirmWrite = (id, value, updatedAt) => {
  // Superseded by a later write meanwhile: that one decides.
  if (LOCAL_NOTE_WRITES.get(id)?.value === value) {
    LOCAL_NOTE_WRITES.set(id, { value, updatedAt: updatedAt ?? null });
  }
};

const toTime = (iso) => {
  const t = Date.parse(iso ?? "");
  return Number.isNaN(t) ? null : t;
};

/** THE rule: the note to trust, given the server's note and its updated_at. */
export function resolveServerNote(id, serverNote, serverUpdatedAt) {
  const server = serverNote ?? "";
  const write = LOCAL_NOTE_WRITES.get(id);
  if (!write || write.value === server) return server;
  const confirmedAt = toTime(write.updatedAt);
  const serverAt = toTime(serverUpdatedAt);
  if (confirmedAt != null && serverAt != null && serverAt >= confirmedAt) {
    return server; // newer than our write (e.g. another session): last write wins
  }
  return write.value;
}

export default function useNoteAutosave({
  activityId,
  initialValue = "",
  serverUpdatedAt,
  locked = false,
  mutateActivity,
  delayMs = NOTES_AUTOSAVE_DELAY_MS,
  retryMs = NOTES_AUTOSAVE_RETRY_MS,
} = {}) {
  const [status, setStatus] = useState(NOTE_AUTOSAVE_STATUS.IDLE);
  const [savedAt, setSavedAt] = useState(null);
  const [serverLocked, setServerLocked] = useState(false);
  // N4b — the note to show: the server's, unless older than our last write.
  const [note, setNote] = useState(() =>
    resolveServerNote(activityId, initialValue, serverUpdatedAt),
  );

  // Refs: read by the timers, unmount and beforeunload (always fresh).
  const latestRef = useRef(undefined); // the value typed last (undefined: none)
  const savedRef = useRef(note); // the value the server holds
  const noteIdRef = useRef(activityId); // the activity the typed value belongs to
  const timerRef = useRef(null);
  const savingRef = useRef(false);
  const failingRef = useRef(false); // a failure streak is on (one red snackbar)
  const mountedRef = useRef(true);
  const ctxRef = useRef({});
  ctxRef.current = { activityId, locked: locked || serverLocked, mutateActivity };

  const isDirty = () =>
    latestRef.current !== undefined && latestRef.current !== savedRef.current;

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const setIfMounted = (fn) => {
    if (mountedRef.current) fn();
  };

  const save = useCallback(async () => {
    clearTimer();
    const { locked: isLocked, mutateActivity: mutate } = ctxRef.current;
    const id = noteIdRef.current;
    if (isLocked || savingRef.current || !isDirty()) return;

    const value = latestRef.current;
    savingRef.current = true;
    recordWrite(id, value);
    setIfMounted(() => setStatus(NOTE_AUTOSAVE_STATUS.SAVING));

    let result;
    try {
      result = await saveActivityNotes(id, value);
    } catch (err) {
      result = { success: false, error: err?.message, status: 0 };
    }
    savingRef.current = false;
    // Another activity meanwhile: this answer belongs to the previous one.
    if (noteIdRef.current !== id) return;

    if (result?.success) {
      savedRef.current = value;
      failingRef.current = false;
      confirmWrite(id, value, result.data?.updated_at);
      const updatedAt = result.data?.updated_at ?? new Date().toISOString();
      mutate?.(
        (current) =>
          current?.data
            ? {
                ...current,
                data: { ...current.data, outcome_notes: value, updated_at: updatedAt },
              }
            : current,
        { revalidate: false },
      );
      if (!mountedRef.current) return;
      setNote(value);
      setSavedAt(updatedAt);
      if (isDirty()) {
        // Typed during the save: save that too, now.
        save();
      } else {
        setStatus(NOTE_AUTOSAVE_STATUS.SAVED);
      }
      return;
    }

    if (isSourceLocked(result)) {
      // The activity became CANCELLED: a business rule, never retried.
      displayWarningSnackbar(SOURCE_LOCKED_MESSAGE);
      setIfMounted(() => {
        setServerLocked(true);
        setStatus(NOTE_AUTOSAVE_STATUS.ERROR);
      });
      return;
    }

    if (!failingRef.current) displayErrorSnackbar(result);
    failingRef.current = true;
    if (!mountedRef.current) return;
    setStatus(NOTE_AUTOSAVE_STATUS.ERROR);
    timerRef.current = setTimeout(() => save(), retryMs);
  }, [retryMs]);

  const schedule = useCallback(
    (value) => {
      if (ctxRef.current.locked) return;
      noteIdRef.current = ctxRef.current.activityId;
      latestRef.current = value ?? "";
      clearTimer();
      if (!isDirty()) {
        // Back to what the server holds: nothing to save.
        if (!savingRef.current) {
          setStatus(savedAt ? NOTE_AUTOSAVE_STATUS.SAVED : NOTE_AUTOSAVE_STATUS.IDLE);
        }
        return;
      }
      if (!savingRef.current) setStatus(NOTE_AUTOSAVE_STATUS.PENDING);
      timerRef.current = setTimeout(() => save(), delayMs);
    },
    [delayMs, save, savedAt],
  );

  const flush = useCallback(() => save(), [save]);

  const retry = useCallback(() => save(), [save]);

  // The last word when the page goes away: a keepalive request — an axios
  // request would be cancelled with the page.
  // N4: the activity's cache gets the flushed note too (no answer will come
  // back) — reopening the panel shows it. Only for the activity the cache
  // belongs to (not after a switch to another activity).
  const flushKeepalive = useCallback(() => {
    if (ctxRef.current.locked || !isDirty()) return;
    clearTimer();
    const id = noteIdRef.current;
    const value = latestRef.current;
    recordWrite(id, value);
    const sent = saveActivityNotesKeepalive(id, value, (result) => {
      if (result?.success) confirmWrite(id, value, result.data?.updated_at);
    });
    if (sent) {
      savedRef.current = value;
      if (id === ctxRef.current.activityId) {
        ctxRef.current.mutateActivity?.(
          (current) =>
            current?.data ? { ...current, data: { ...current.data, outcome_notes: value } } : current,
          { revalidate: false },
        );
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    window.addEventListener("beforeunload", flushKeepalive);
    return () => {
      window.removeEventListener("beforeunload", flushKeepalive);
      mountedRef.current = false;
    };
  }, [flushKeepalive]);

  // Unmount, or another activity: the unsaved value of the previous one goes
  // by keepalive; then start afresh on the server's note.
  const initialRef = useRef(initialValue);
  initialRef.current = initialValue;

  // N4: the server's note arrives or changes (the activity loaded after the
  // panel mounted, a revalidation): it is what the server holds — as long as
  // nothing unsaved is pending.
  // N4b: through THE rule — never older than our last write.
  const serverAtRef = useRef(serverUpdatedAt);
  serverAtRef.current = serverUpdatedAt;
  useEffect(() => {
    if (!isDirty() && !savingRef.current) {
      const trusted = resolveServerNote(noteIdRef.current, initialValue, serverUpdatedAt);
      savedRef.current = trusted;
      latestRef.current = undefined;
      setNote(trusted);
    }
  }, [initialValue, serverUpdatedAt]);
  useEffect(() => {
    noteIdRef.current = activityId;
    latestRef.current = undefined;
    const trusted = resolveServerNote(activityId, initialRef.current, serverAtRef.current);
    savedRef.current = trusted;
    setNote(trusted);
    failingRef.current = false;
    setServerLocked(false);
    setSavedAt(null);
    setStatus(NOTE_AUTOSAVE_STATUS.IDLE);
    return () => {
      flushKeepalive();
      clearTimer();
    };
  }, [activityId, flushKeepalive]);

  return {
    note,
    status,
    savedAt,
    locked: locked || serverLocked,
    schedule,
    flush,
    retry,
  };
}
