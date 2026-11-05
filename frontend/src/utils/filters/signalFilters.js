// frontend/src/utils/filters/signalFilters.js
//
// Sprint « Cycle de vie des contacts », 8h — the signal filter DEFINITIONS
// (utils/filters/filterDefinitions), read by every signal filter renderer:
// SignalsFilterPanel (the drawer of the DC / Account views) and the inline
// InlinePillsFilter (PersonSignalsContent). Options derived from the ONE
// type vocabulary (utils/signalTypes) — the server evaluates each one
// (backend test_aggregated_filter_validation.py, the contract test).

import { getSignalTypeLabel, QUALIFICATION_SIGNAL_TYPES, SIGNAL_TYPE_SLUGS } from "utils/signalTypes";
import { EMPTY_MEANS } from "utils/filters/filterDefinitions";

// Every signal type; nothing chosen = all (no param).
export const SIGNAL_TYPE_FILTER = {
  key: "types",
  param: "signal_type",
  label: "Type",
  multiple: true,
  emptyMeans: EMPTY_MEANS.ALL,
  options: SIGNAL_TYPE_SLUGS.map((value) => ({ value, label: getSignalTypeLabel(value) })),
};

// The 8 qualification types (no next steps), in THEIR order (the Signals
// band's); nothing chosen = the 8.
export const QUALIFICATION_TYPE_FILTER = {
  ...SIGNAL_TYPE_FILTER,
  emptyMeans: EMPTY_MEANS.SURFACE,
  options: QUALIFICATION_SIGNAL_TYPES.map((value) => ({ value, label: getSignalTypeLabel(value) })),
};
