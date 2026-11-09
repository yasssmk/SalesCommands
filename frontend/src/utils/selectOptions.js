// frontend/src/utils/selectOptions.js
//
// Lot 3 / 4 (TD-244) — THE empty option of an optional, clearable select of
// the signal drawers (Impact impact_type, Constraint rigidity, People
// influence / department). Formerly a `{ value: "", label: "—" }` prefix
// copied in each Edit*Content (EditPeopleContent had its own EMPTY_OPTION).

export const EMPTY_OPTION = { value: "", label: "—" };

/** `options` (may be missing while the choices load) prefixed by EMPTY_OPTION. */
export function withEmptyOption(options) {
  return [EMPTY_OPTION, ...(options ?? [])];
}
