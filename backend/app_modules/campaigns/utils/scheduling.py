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


def prefetch_delays(campaign_contact_id):
    """
    Fetch all min_delay_days for a CampaignContact in a single query.

    Returns a dict mapping sequence_position → min_delay_days (0 if None).
    Pass the result to cumulative_delay_for_position() to avoid N+1 reads
    when looping over multiple ON_HOLD activities for the same contact.

    Args:
        campaign_contact_id: UUID of the CampaignContact

    Returns:
        dict[int, int]: {sequence_position: min_delay_days}
    """
    from app_modules.activities.models import Activity
    rows = (
        Activity.objects
        .filter(
            campaign_contact_id=campaign_contact_id,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
        )
        .values_list('sequence_position', 'min_delay_days')
    )
    return {pos: (delay or 0) for pos, delay in rows}


def cumulative_delay_for_position(
    campaign_contact_id,
    target_sequence_position,
    prefetched=None,
):
    """
    Return the total min_delay_days for all sequence steps up to and including
    target_sequence_position, for a given CampaignContact.

    Uses sequence_position ordering — no previous_activity traversal.

    Args:
        campaign_contact_id: UUID of the CampaignContact
        target_sequence_position: int — position of the activity to schedule
        prefetched: optional dict {sequence_position: min_delay_days} from
                    prefetch_delays(). When provided, skips the DB query —
                    use this when calling in a loop over the same contact.

    Returns:
        int: cumulative delay in days from position 1 up to target (inclusive)
    """
    if prefetched is not None:
        return sum(
            delay for pos, delay in prefetched.items()
            if pos <= target_sequence_position
        )

    from app_modules.activities.models import Activity
    rows = (
        Activity.objects
        .filter(
            campaign_contact_id=campaign_contact_id,
            sequence_position__lte=target_sequence_position,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
        )
        .values_list('min_delay_days', flat=True)
    )
    return sum(d for d in rows if d is not None)