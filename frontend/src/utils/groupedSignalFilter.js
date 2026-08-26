// frontend/src/utils/groupedSignalFilter.js
//
// Client-side Qualification filter for the ACTIVITY grouped view. The Activity
// synthesis is a single-activity, client-side view (no cluster endpoint), so
// the same filters Account/DC apply server-side are applied here in the browser
// on the already-loaded signals. Semantics mirror the backend cluster endpoint
// exactly:
//   - perimeter: OR — scope_level=BUSINESS (when 'BUSINESS' selected) OR
//     target_department in the selected department ids.
//   - what / dimension: AND — the signal's value must be in the selected set; a
//     signal type that has no such field (tech-stack / blockers) is EXCLUDED
//     when that filter is active.
//   - contact: AND — the signal's source contacts must intersect the selection.
//   - status: AND — defaults to pending + validated (rejected only when asked),
//     matching the backend default.

const DEFAULT_STATUSES = ["PENDING", "VALIDATED"];

/**
 * @param {Object} signal - A signal object from the per-type list serializer
 *   (carries scope_level, target_department {id,name}|null, what, dimension,
 *   status, source_context.contacts[]).
 * @param {Object} filters - { perimeter, whats, dimensions, contacts, statuses }.
 * @returns {boolean}
 */
export function matchesGroupedFilters(signal, filters = {}) {
  const {
    perimeter = [],
    whats = [],
    dimensions = [],
    contacts = [],
    statuses = [],
  } = filters;

  // Status (AND) — empty selection = the default set, so REJECTED never shows
  // unless explicitly selected (mirrors the backend default).
  const effectiveStatuses = statuses.length ? statuses : DEFAULT_STATUSES;
  if (!effectiveStatuses.includes(signal.status)) return false;

  // Perimeter (OR) — scope=BUSINESS OR target_department in the selected ids.
  if (perimeter.length) {
    const wantBusiness = perimeter.includes("BUSINESS");
    const deptIds = perimeter.filter((p) => p !== "BUSINESS").map(String);
    const isBusiness = signal.scope_level === "BUSINESS";
    const deptId =
      signal.target_department?.id != null
        ? String(signal.target_department.id)
        : null;
    const matchesPerimeter =
      (wantBusiness && isBusiness) ||
      (deptIds.length > 0 && deptId !== null && deptIds.includes(deptId));
    if (!matchesPerimeter) return false;
  }

  // Domain (`what`) — AND. A type without `what` is excluded when active.
  if (whats.length && (!signal.what || !whats.includes(signal.what))) {
    return false;
  }

  // Dimension — AND. A type without `dimension` is excluded when active.
  if (
    dimensions.length &&
    (!signal.dimension || !dimensions.includes(signal.dimension))
  ) {
    return false;
  }

  // Contact (source) — AND. The signal's source contacts must intersect.
  if (contacts.length) {
    const sourceIds = (signal.source_context?.contacts || []).map((c) =>
      String(c.id),
    );
    const wanted = contacts.map(String);
    if (!sourceIds.some((id) => wanted.includes(id))) return false;
  }

  return true;
}

/**
 * Filter a list of signals by the grouped Qualification filters.
 * @returns {Array} the signals that match every active filter.
 */
export function applyGroupedFilters(signals, filters) {
  return (signals || []).filter((s) => matchesGroupedFilters(s, filters));
}
