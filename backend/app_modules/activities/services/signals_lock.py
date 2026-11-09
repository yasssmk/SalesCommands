# app_modules/activities/services/signals_lock.py
"""
THE lock rule of an activity's signal bands — server side (sprint « Cycle de
vie des contacts », 8g-2, TD-297). MIRROR of the front rule
frontend/src/utils/activitySignalsLock.js (keep both in sync): only a
CANCELLED activity locks its signals — a COMPLETED one stays workable, its
signals are handled after the conversation (5.11).

Called by:
  * SignalManager.validate / reject / reopen — the central point behind the
    signal lifecycle endpoints (base_views validate_signal / reject_signal /
    reopen_signal), the People resolve and the next-step materialisation;
  * the AI analysis endpoint (activity_extraction_view).
"""

from core.error_messages import ActivityErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import ActivityStatus

ACTIVITY_SIGNALS_LOCKED_STATUSES = frozenset({ActivityStatus.CANCELLED})


def check_activity_signals_unlocked(activity):
    """The standard refusal when `activity` (may be None) locks its signals."""
    if activity is not None and activity.status in ACTIVITY_SIGNALS_LOCKED_STATUSES:
        raise StandardizedValidationError(ActivityErrorMessages.SIGNALS_LOCKED)
