# app_modules/activities/constants.py
"""
Constants for Activity module.

Contains choices for Activity Types, Status, and Outcomes.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class ActivityType(models.TextChoices):
    """
    Type of activity to be performed.
    
    Determines UX presentation and future AI preparation logic.
    """
    CALL = 'CALL', _('Phone Call')
    EMAIL = 'EMAIL', _('Email')
    MEETING = 'MEETING', _('Meeting')
    DEMO = 'DEMO', _('Demo')
    TASK = 'TASK', _('Task')
    LINKEDIN = 'LINKEDIN', _('LinkedIn Message')
    OTHER = 'OTHER', _('Other')


class ActivityStatus(models.TextChoices):
    """
    Status of an activity.
    
    Lifecycle: PLANNED → ON_HOLD (campaign pause) → PLANNED (campaign resume) → COMPLETED/CANCELLED
    """

    PLANNED = 'PLANNED', _('Planned')
    ON_HOLD = 'ON_HOLD', _('On Hold')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')


# Terminal vs non-terminal (still-open) activity statuses. A terminal activity
# is history and must never be re-owned or re-cancelled; a non-terminal one is
# pending work. Single definition, reused by consumers (e.g. user-deactivation
# transfer) instead of re-listing the members inline.
TERMINAL_STATUSES = frozenset({ActivityStatus.COMPLETED, ActivityStatus.CANCELLED})
NON_TERMINAL_STATUSES = frozenset({ActivityStatus.PLANNED, ActivityStatus.ON_HOLD})


class ActivityOutcome(models.TextChoices):
    SUCCESSFUL = 'SUCCESSFUL', _('Successful')
    NO_ANSWER = 'NO_ANSWER', _('No Answer')
    CALLBACK_REQUESTED = 'CALLBACK_REQUESTED', _('Callback Requested')
    NOT_INTERESTED = 'NOT_INTERESTED', _('Not Interested')
    WRONG_CONTACT = 'WRONG_CONTACT', _('Wrong Contact')
    MEETING_SCHEDULED = 'MEETING_SCHEDULED', _('Meeting Scheduled')
    FOLLOW_UP_NEEDED = 'FOLLOW_UP_NEEDED', _('Follow-up Needed')
    UNSUBSCRIBE_OPTOUT = 'UNSUBSCRIBE_OPTOUT', _('Unsubscribe / Opt-out')
    WRONG_EMAIL = 'WRONG_EMAIL', _('Wrong Email')
    INVALID_PHONE_NUMBER = 'INVALID_PHONE_NUMBER', _('Invalid Phone Number')
    OTHER = 'OTHER', _('Other')

class NoNextStepReason(models.TextChoices):
    """
    Reasons why no next step was agreed after an activity.
    
    Used when next_step_agreed=False to track why the sales
    process ended or paused at this point.
    
    Note: If prospect says "I'll call you back", the salesperson
    MUST create a TASK with due_date to ensure follow-up tracking.
    """
    CLOSE_WON = 'CLOSE_WON', _('Close Won')
    CLOSE_LOST = 'CLOSE_LOST', _('Close Lost')
    ON_HOLD = 'ON_HOLD', _('On Hold')
    NOT_QUALIFIED = 'NOT_QUALIFIED', _('Not Qualified')
    OTHER = 'OTHER', _('Other')

