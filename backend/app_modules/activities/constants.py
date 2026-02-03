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
    TASK = 'TASK', _('Task')
    LINKEDIN = 'LINKEDIN', _('LinkedIn Message')
    OTHER = 'OTHER', _('Other')


class ActivityStatus(models.TextChoices):
    """
    Status of an activity.
    
    Lifecycle: PLANNED → COMPLETED/CANCELLED
    """
    PLANNED = 'PLANNED', _('Planned')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')


class ActivityOutcome(models.TextChoices):
    """
    Outcome of a completed activity.
    
    Used to track results and feed Decision Cycle progression.
    Only applicable when status = COMPLETED.
    """
    SUCCESSFUL = 'SUCCESSFUL', _('Successful')
    NO_ANSWER = 'NO_ANSWER', _('No Answer')
    CALLBACK_REQUESTED = 'CALLBACK_REQUESTED', _('Callback Requested')
    NOT_INTERESTED = 'NOT_INTERESTED', _('Not Interested')
    WRONG_CONTACT = 'WRONG_CONTACT', _('Wrong Contact')
    MEETING_SCHEDULED = 'MEETING_SCHEDULED', _('Meeting Scheduled')
    FOLLOW_UP_NEEDED = 'FOLLOW_UP_NEEDED', _('Follow-up Needed')
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