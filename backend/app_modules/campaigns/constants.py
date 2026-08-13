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
# CHANNEL OVERRIDE
# ==========================================================================

class ChannelOverride(models.TextChoices):
    """
    Per-campaign channel strategy applied at activity generation.

    AUTO     — the backend selects the sequence variant from each contact's
               available channels (phone/email/LinkedIn).
    NO_CALLS — never place a call: after dropping the phone, routing picks
               WITHOUT_PHONE when the contact has an email, otherwise
               LINKEDIN_ONLY. Enrollment stays reachable on email OR LinkedIn.
    """
    AUTO     = 'AUTO',     _('Auto')
    NO_CALLS = 'NO_CALLS', _('No calls')


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


# Objective types whose current value is read from DecisionCycle.source_campaign.
# Because a campaign's objectives are always computed with period=None, these
# three collapse into ONE conditional aggregate (count + two filtered sums) over
# the campaign's decision cycles — the grouped objective-value calculation only
# needs a single query for the whole family.
DECISION_CYCLE_OBJECTIVE_TYPES = frozenset({
    ObjectiveType.DECISION_CYCLES,
    ObjectiveType.PIPELINE_VALUE,
    ObjectiveType.REVENUE_WON,
})


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


# ==========================================================================
# CAPACITY LIMITS (product-locked caps)
# ==========================================================================

# Maximum accounts a single campaign may hold.
#   - Creation (OUTBOUND territory enrollment): counted RAW (every resolved account).
#   - Add Target (manual enrollment): counted on ACTIVE (non-terminal) accounts only;
#     COMPLETED/STOPPED accounts do not count toward the cap.
MAX_ACCOUNTS_PER_CAMPAIGN = 50

# Maximum simultaneously ACTIVE campaigns a single user (owner) may hold, per type.
# The two caps are INDEPENDENT — a user may hold 10 active OUTBOUND AND 1 active
# TARGETED at the same time (not a combined total of 11).
MAX_ACTIVE_OUTBOUND_CAMPAIGNS_PER_USER = 10
MAX_ACTIVE_TARGETED_CAMPAIGNS_PER_USER = 1

# Per-type lookup for the active-campaign cap, so the guard stays data-driven.
ACTIVE_CAMPAIGN_CAPS_BY_TYPE: dict = {
    CampaignType.OUTBOUND: MAX_ACTIVE_OUTBOUND_CAMPAIGNS_PER_USER,
    CampaignType.TARGETED: MAX_ACTIVE_TARGETED_CAMPAIGNS_PER_USER,
}


# ==========================================================================
# INACTIVITY DETECTION
# ==========================================================================

# An OPEN campaign (status not terminal) whose last DONE activity — or, when
# nothing has been done yet, its creation — is older than this many days is
# flagged inactive at read-time (Campaign.is_inactive). No stored field.
# Set to 0 to flag any campaign idle for at least a full day (used for testing).
N_INACTIVE_DAYS = 30