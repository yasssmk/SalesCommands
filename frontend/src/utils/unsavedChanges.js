// frontend/src/utils/unsavedChanges.js
//
// Sprint « Source / Notes » 2.2 — the scopes of a source of UNSAVED changes,
// shared by the coque's guard (contexts/WorkspaceDrawerContext) and the hook
// that declares a source (hooks/useUnsavedChanges):
//   - DRAWER — a drawer content: replacing / closing the drawer or opening the
//     menu asks first;
//   - PAGE — a field of the page (e.g. the Source band's notes): covered by
//     beforeunload (and the internal links, 2.3), not by the drawer.

export const UNSAVED_SCOPE = { DRAWER: "drawer", PAGE: "page" };
