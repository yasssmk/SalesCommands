# app_modules/campaigns/constants.py
"""
Centralized constants for the Campaign module.

All TextChoices, state machines, and transition dicts live here.
Models import from this file — never define enums inline in models.

Reference: app_modules/activities/constants.py (same pattern).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==========================================================================
# CAMPAIGN TYPE
# ==========================================================================

class CampaignType(models.TextChoices):
    """Campaign execution strategy."""
    OUTBOUND = 'OUTBOUND', _('Outbound Campaign')
    TARGETED = 'TARGETED', _('Targeted Campaign')


# ==========================================================================
# CAMPAIGN STATUS
# ==========================================================================

class CampaignStatus(models.TextChoices):
    """
    Campaign lifecycle status.

    Transitions:
        DRAFT → ACTIVE (start)
        ACTIVE → PAUSED (pause)
        PAUSED → ACTIVE (resume)
        ACTIVE | PAUSED → COMPLETED (complete)
        any non-final → CANCELLED (cancel)
    """
    DRAFT     = 'DRAFT',     _('Draft')
    ACTIVE    = 'ACTIVE',    _('Active')
    PAUSED    = 'PAUSED',    _('Paused')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')


CAMPAIGN_STATUS_TRANSITIONS: dict = {
    CampaignStatus.DRAFT:     [CampaignStatus.ACTIVE, CampaignStatus.CANCELLED],
    CampaignStatus.ACTIVE:    [CampaignStatus.PAUSED, CampaignStatus.COMPLETED, CampaignStatus.CANCELLED],
    CampaignStatus.PAUSED:    [CampaignStatus.ACTIVE, CampaignStatus.COMPLETED, CampaignStatus.CANCELLED],
    CampaignStatus.COMPLETED: [],
    CampaignStatus.CANCELLED: [],
}

FINAL_CAMPAIGN_STATES: frozenset = frozenset({
    CampaignStatus.COMPLETED,
    CampaignStatus.CANCELLED,
})

MODIFIABLE_CAMPAIGN_STATES: frozenset = frozenset({
    CampaignStatus.DRAFT,
    CampaignStatus.ACTIVE,
    CampaignStatus.PAUSED,
})


# ==========================================================================
# CAMPAIGN ACCOUNT STATUS
# ==========================================================================

class CampaignAccountStatus(models.TextChoices):
    PENDING     = 'PENDING',     _('Pending')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    COMPLETED   = 'COMPLETED',   _('Completed')
    STOPPED     = 'STOPPED',     _('Stopped')


CAMPAIGN_ACCOUNT_TRANSITIONS: dict = {
    CampaignAccountStatus.PENDING:     [CampaignAccountStatus.IN_PROGRESS, CampaignAccountStatus.STOPPED],
    CampaignAccountStatus.IN_PROGRESS: [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.STOPPED],
    CampaignAccountStatus.COMPLETED:   [],
    CampaignAccountStatus.STOPPED:     [],
}

FINAL_ACCOUNT_STATES: frozenset = frozenset({
    CampaignAccountStatus.COMPLETED,
    CampaignAccountStatus.STOPPED,
})


# ==========================================================================
# CAMPAIGN CONTACT STATUS
# ==========================================================================

class CampaignContactStatus(models.TextChoices):
    """
    Per-contact lifecycle status within a campaign.

    Transitions:
        PENDING → IN_PROGRESS | STOPPED
        IN_PROGRESS → ON_HOLD | CALLBACK_PENDING | COMPLETED | STOPPED
        ON_HOLD → IN_PROGRESS | STOPPED
        CALLBACK_PENDING → IN_PROGRESS | COMPLETED | STOPPED
    """
    PENDING          = 'PENDING',          _('Pending')
    IN_PROGRESS      = 'IN_PROGRESS',      _('In Progress')
    ON_HOLD          = 'ON_HOLD',          _('On Hold')
    CALLBACK_PENDING = 'CALLBACK_PENDING', _('Callback Pending')
    COMPLETED        = 'COMPLETED',        _('Completed')
    STOPPED          = 'STOPPED',          _('Stopped')


CAMPAIGN_CONTACT_TRANSITIONS: dict = {
    CampaignContactStatus.PENDING: [
        CampaignContactStatus.IN_PROGRESS,
        CampaignContactStatus.STOPPED,
    ],
    CampaignContactStatus.IN_PROGRESS: [
        CampaignContactStatus.ON_HOLD,
        CampaignContactStatus.CALLBACK_PENDING,
        CampaignContactStatus.COMPLETED,
        CampaignContactStatus.STOPPED,
    ],
    CampaignContactStatus.ON_HOLD: [
        CampaignContactStatus.IN_PROGRESS,
        CampaignContactStatus.STOPPED,
    ],
    CampaignContactStatus.CALLBACK_PENDING: [
        CampaignContactStatus.IN_PROGRESS,
        CampaignContactStatus.COMPLETED,
        CampaignContactStatus.STOPPED,
    ],
    CampaignContactStatus.COMPLETED: [],
    CampaignContactStatus.STOPPED:   [],
}

FINAL_CONTACT_STATES: frozenset = frozenset({
    CampaignContactStatus.COMPLETED,
    CampaignContactStatus.STOPPED,
})


# ==========================================================================
# OBJECTIVE TYPE
# ==========================================================================

class ObjectiveType(models.TextChoices):
    """Campaign objective type choices (aligned with DecisionCycle tracking)."""
    MEETINGS         = 'MEETINGS',         _('Number of Meetings')
    DECISION_CYCLES  = 'DECISION_CYCLES',  _('Decision Cycles Opened')
    CONTACTS_REACHED = 'CONTACTS_REACHED', _('Contacts Reached')
    PIPELINE_VALUE   = 'PIPELINE_VALUE',   _('Pipeline Value')
    REVENUE_WON      = 'REVENUE_WON',      _('Revenue Won')
    NEW_LOGOS        = 'NEW_LOGOS',        _('New Logos')


# ==========================================================================
# MEMBER ROLE
# ==========================================================================

class MemberRole(models.TextChoices):
    """
    Campaign member roles.

    Extracted from CampaignMember inner class to module level
    so services and serializers can import without loading the model.
    """
    OWNER    = 'OWNER',    _('Campaign Owner')
    EXECUTOR = 'EXECUTOR', _('Executor')
    RECEIVER = 'RECEIVER', _('Receiver')
    OBSERVER = 'OBSERVER', _('Observer')