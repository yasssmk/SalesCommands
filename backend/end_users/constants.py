# end_users/constants.py
"""
Constants of the end_users module.

SYSTEM NOTE LINES (sprint « Source / Notes », 1.4) — when a user is
deactivated, the transfer cancels their open free activities and their
TARGETED contacts' activities; it APPENDS one of these lines at the END of
each activity's notes (outcome_notes), never erasing what was written
(app_modules/activities/services/activity_notes.py). Stored as is: plain
strings, not translated at write time.
"""

DEACTIVATION_CANCELLED_NOTE_LINE = 'Cancelled on owner deactivation'
DEACTIVATION_TARGET_REMOVED_NOTE_LINE = 'Target removed on owner deactivation'
