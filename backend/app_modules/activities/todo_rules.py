# app_modules/activities/todo_rules.py
"""
Todo date rules — the single home of the campaign "actionable date" clamp.

Product rule (outbound campaigns are chasing, not client commitments):
a PENDING (PLANNED) campaign step is bucketed/displayed on an *actionable*
date = max(scheduled_date, today), computed at READ time. A passed step is not
late — it is "still to do today" — so a campaign step is NEVER overdue: the
clamp floors the date at today, which structurally keeps it out of any
"< today" (OVERDUE) window.

Every non-campaign activity (decision cycles, standalone activities) keeps its
existing effective date COALESCE(due_date, scheduled_date) and its real overdue
behaviour — untouched.

This module owns the rule once; both consumers import it:
  - the BI todo (bi/definitions/activities.py) — bucketing + flood control,
  - the campaign playlist (campaigns/services/campaign_execution_service.py) —
    the date shown on the activity card.

Nothing here writes. The clamp is a pure read-time ORM expression (Q6-native).
"""

from django.db.models import Case, DateField, Exists, OuterRef, Q, Value, When
from django.db.models.functions import Coalesce, Greatest

from app_modules.activities.constants import ActivityStatus


# A campaign step that is still pending action (PLANNED). ON_HOLD (paused
# campaign) is intentionally excluded: a paused step is not "to do today".
CAMPAIGN_PENDING_STEP = Q(campaign_id__isnull=False, status=ActivityStatus.PLANNED)


def campaign_actionable_date_expr(today):
    """max(scheduled_date, today) as a DB expression — THE shared clamp.

    Postgres GREATEST ignores NULLs, so a campaign step with no scheduled_date
    clamps to today (still actionable). Never returns a date before today, which
    is what keeps a campaign step out of the OVERDUE window by construction.
    """
    return Greatest(
        'scheduled_date',
        Value(today, output_field=DateField()),
        output_field=DateField(),
    )


def todo_effective_date_expr(today):
    """The effective date the todo buckets/sorts on.

    Campaign PENDING steps → the clamped actionable date (never < today).
    Everything else → COALESCE(due_date, scheduled_date), UNCHANGED.
    """
    return Case(
        When(CAMPAIGN_PENDING_STEP, then=campaign_actionable_date_expr(today)),
        default=Coalesce('due_date', 'scheduled_date'),
        output_field=DateField(),
    )


def only_next_pending_campaign_steps(queryset):
    """Drop campaign regular steps that are not the next pending one for their
    contact (a neglected chain's cascaded step 2/3 have past dates too — without
    this they would all clamp to today and flood the todo).

    A step is superseded iff another PLANNED, non-callback step with a lower
    sequence_position exists for the same campaign_contact. Callbacks are never
    superseded (they surface on their own, clamped like any step). Non-campaign
    rows never match the exclusion (campaign_id is NULL), so decision-cycle and
    standalone activities are untouched.

    One correlated EXISTS — query-bounded, no N+1.
    """
    from app_modules.activities.models import Activity

    earlier_pending_step = Activity.objects.filter(
        campaign_contact_id=OuterRef('campaign_contact_id'),
        status=ActivityStatus.PLANNED,
        is_callback_followup=False,
        sequence_position__lt=OuterRef('sequence_position'),
    )

    return queryset.annotate(
        _has_earlier_pending_step=Exists(earlier_pending_step),
    ).exclude(
        campaign_id__isnull=False,
        status=ActivityStatus.PLANNED,
        is_callback_followup=False,
        campaign_contact_id__isnull=False,
        _has_earlier_pending_step=True,
    )
