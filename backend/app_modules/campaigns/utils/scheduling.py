# app_modules/campaigns/utils/scheduling.py
"""
Shared scheduling utilities for campaign sequence calculations.

Replaces the duplicated _cumulative_delay_from_root() / _next_business_day()
methods previously scattered across CampaignLifecycleService and
CampaignContactViewSet.
"""

from datetime import timedelta

from app_modules.activities.constants import ActivityStatus


def next_business_day(date):
    """Advance date past weekends (Mon–Fri only)."""
    while date.weekday() >= 5:
        date += timedelta(days=1)
    return date


def cumulative_delay_for_position(campaign_contact_id, target_sequence_position):
    """
    Return the total min_delay_days for all sequence steps up to and including
    target_sequence_position, for a given CampaignContact.

    Replaces the recursive _cumulative_delay_from_root() linked-list walk.
    Uses sequence_position ordering — no previous_activity traversal.

    Args:
        campaign_contact_id: UUID of the CampaignContact
        target_sequence_position: int — position of the activity to schedule

    Returns:
        int: cumulative delay in days from position 1 up to target (inclusive)
    """
    from app_modules.activities.models import Activity

    activities = (
        Activity.objects
        .filter(
            campaign_contact_id=campaign_contact_id,
            sequence_position__lte=target_sequence_position,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
        )
        .order_by('sequence_position')
        .values_list('min_delay_days', flat=True)
    )

    return sum(d for d in activities if d is not None)