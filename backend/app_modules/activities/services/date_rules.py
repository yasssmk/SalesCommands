# app_modules/activities/services/date_rules.py
"""
THE date rule of an activity creation — sprint « Cycle de vie des contacts »,
8g-1 (TD-230). One module (the model of participant_rules.py), called by
both creation paths:
  * POST /module-activities/                      (ActivityCreateSerializer)
  * POST /module-activities/create-with-entities/ (ActivityCreationService)

Rule: at least one date, and only one — a scheduled date (when the activity
happens) OR a due date (a deadline), never both.
System exception: the campaign generation (campaign_execution_service) writes
its activities on the model directly and does not go through these paths.
"""

from core.error_messages import ActivityErrorMessages, CoreErrorMessages
from core.exceptions import StandardizedValidationError


def check_activity_dates(scheduled_date, due_date):
    """Exactly one of `scheduled_date` / `due_date` — else the standard refusal."""
    if not scheduled_date and not due_date:
        raise StandardizedValidationError(
            CoreErrorMessages.REQUIRED_FIELD.format(field='Scheduled date or due date')
        )
    if scheduled_date and due_date:
        raise StandardizedValidationError(ActivityErrorMessages.DATES_EXCLUSIVE)
