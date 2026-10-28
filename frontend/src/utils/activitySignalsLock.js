// frontend/src/utils/activitySignalsLock.js
//
// Sprint Next steps 5.11 — the ONE lock rule of the activity's signal bands
// (Signals, Next steps): a COMPLETED activity stays workable on the signals
// side — the conversation is over and its signals are handled now (PO) — only
// these statuses lock the bands. The backend refuses no lifecycle action on a
// COMPLETED activity (signal_manager.py guards the SIGNAL status only).

import { ACTIVITY_STATUSES } from "api/accounts/activities";

export const ACTIVITY_SIGNALS_LOCKED_STATUSES = [ACTIVITY_STATUSES.CANCELLED];

export function isActivitySignalsLocked(activity) {
  return ACTIVITY_SIGNALS_LOCKED_STATUSES.includes(activity?.status);
}
