// frontend/src/hooks/useUnsavedChanges.js
//
// Sprint « Source / Notes » 2.2 — declares a source of UNSAVED changes to the
// central guard of the workspace coque (contexts/WorkspaceDrawerContext). While
// `dirty` is true the source is registered:
//   - scope "drawer" (default) — a drawer content: replacing / closing the
//     drawer or opening the menu asks first (shared ConfirmDialog);
//   - scope "page" — a field of the page (e.g. the Source band's notes): not
//     touched by the drawer, but covered by beforeunload (and the internal
//     links, 2.3).
// Registration happens in a LAYOUT effect, so it is current at commit — an
// action fired right after (e.g. the close that follows a save) reads the
// fresh state. It re-syncs on every render (cheap: a Map set / delete).
//
// Returns release(): unregisters at once — for a deliberate discard (the
// content's own Cancel), so the action that follows is not asked again. A
// source that is still modified re-registers on its next render.

"use client";

import { useCallback, useId, useLayoutEffect } from "react";

import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { UNSAVED_SCOPE } from "utils/unsavedChanges";

export default function useUnsavedChanges(dirty, { scope = UNSAVED_SCOPE.DRAWER } = {}) {
  const id = useId();
  const { registerUnsaved, releaseUnsaved } = useWorkspaceDrawer();

  // Outside the coque's provider (an isolated render) there is no registry:
  // the guard is simply inactive.
  useLayoutEffect(() => {
    if (dirty) registerUnsaved?.(id, scope);
    else releaseUnsaved?.(id);
  });

  // Unregister when the source unmounts (its content is gone).
  useLayoutEffect(() => () => releaseUnsaved?.(id), [id, releaseUnsaved]);

  return useCallback(() => releaseUnsaved?.(id), [id, releaseUnsaved]);
}
