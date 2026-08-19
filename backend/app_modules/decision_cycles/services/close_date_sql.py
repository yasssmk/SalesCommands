# app_modules/decision_cycles/services/close_date_sql.py
"""
Single source of truth for a DecisionCycle's EFFECTIVE CLOSE DATE.

ONE rule, declared once in ``_effective_close_date_expr()``, with a two-level
priority (PO-locked):

    1. ``DecisionCycle.expected_close_date`` — the MANUAL field. When the rep
       set it, it wins outright.
    2. FALLBACK — the date of the LAST activity of the cycle's CLOSING step
       (``DecisionStep.stage == PipelineStep.CLOSING``).
    3. Neither → NULL. A deal whose close date nobody stated and whose closing
       step holds no dated activity has NO expected close. That is the honest
       answer, and a windowed read excludes it rather than guessing.

This replaces the previous anchor ``Max(steps.expected_end)``
(bi/metrics/sales_metrics.py), which was NULL for every freshly created cycle:
step auto-creation sets ``expected_end=None`` on all five steps
(views/views.py, "expected_end will be set by user later"), so a normally-used
deal was invisible to any windowed pipeline read.

WHY THE CLOSING STEP, AND WHAT "LAST" MEANS
-------------------------------------------
The closing step is identified by ``stage='CLOSING'`` (constants.PipelineStep),
never by ``order`` and never by ``name``: ``IMPLEMENTATION`` (6) and ``GO_LIVE``
(7) remain in the enum for legacy cycles, so "the last step by order" would
resolve to the wrong node on those. ``stage`` is auto-assigned and, per the
model, "cannot be changed by user".

Within that one step, "last" is the FURTHEST-OUT activity date — the Max of the
activities' own dates. The step chain (``DecisionStep.previous_step``) is what
makes "the CLOSING step" a single unambiguous node in the cycle's ordering; it
does not order activities inside a step, so the ordering reused at the activity
level is the Activity model's own temporal ordering (``Meta.ordering``
``['-scheduled_date', '-created_at']``, backed by the composite index on
``['decision_cycle', 'decision_step', 'scheduled_date', 'scheduled_time',
'created_at']``).

An activity's date is read as ``COALESCE(due_date, scheduled_date)`` — the
CANONICAL activity effective date already declared in
``app_modules/activities/todo_rules.py`` for every non-campaign activity, reused
here rather than restated. The PO's rule is "read the date that is set"; the two
columns are validated as an INCLUSIVE or ("at least one of scheduled_date OR
due_date", activities/serializers.py), so they CAN both be set and a bare "read
the one that's set" would be undefined. The coalesce order settles it
deterministically and matches the existing convention. ``completed_at`` is
deliberately NOT part of it: it records when something HAPPENED, and an expected
close is forward-looking (todo_rules.py does not read it either).

CANCELLED activities are excluded, consistent with every other activity-derived
read (services/step_aggregation_service.py).

TWO BINDINGS, ONE RULE
----------------------
Exactly the shape of ``deal_value_sql.py`` (the deal roll-up), and for the same
reason:

* ``annotate_effective_close_date(queryset)`` — the PER-ROW form, an isolated
  correlated Subquery. Every mass read (the personal pipeline aggregation sums
  over many cycles) MUST use this. It composes safely with
  ``annotate_deal_value`` because both are correlated subqueries, not to-many
  joins: neither fans out over the other.

* ``effective_close_date_for(cycle)`` — the SINGLE-INSTANCE form, one query,
  behind the ``DecisionCycle.effective_close_date`` property, which reads the
  annotation when the row carries one and falls back to this otherwise.

No stored column, no write, no backfill: the date follows the manual field and
the activities, so it is derived on read.
"""

from django.db.models import DateField, Max, OuterRef, Subquery
from django.db.models.functions import Coalesce


# Alias for the per-row annotation. Underscored so it can never clash with a
# model field or a serializer output key (same convention as deal_value_sql.py
# and derivation_sql.py).
CLOSE_DATE_ALIAS = '_effective_close_date'


def _closing_activity_date_subquery():
    """The date of the LAST dated activity of the cycle's CLOSING step.

    An isolated correlated Subquery grouped by the cycle, so it returns exactly
    one scalar per outer row (NULL when the cycle has no closing step, no
    activity on it, or no dated one). Built lazily: it needs the Activity model,
    which lives in another app and imports decision_cycles back.
    """
    from app_modules.activities.constants import ActivityStatus
    from app_modules.activities.models import Activity

    from ..constants import PipelineStep

    last_closing_activity = (
        Activity.objects
        .filter(
            # The activity's step belongs to THIS cycle and IS the closing one.
            # Traversing decision_step__cycle_id (not decision_cycle_id) is
            # deliberate: it is the step link that makes the activity a CLOSING
            # activity, and an activity attached to the cycle but to no step
            # must not count.
            decision_step__cycle_id=OuterRef('pk'),
            decision_step__stage=PipelineStep.CLOSING,
        )
        .exclude(status=ActivityStatus.CANCELLED)
        .order_by()                       # drop Meta.ordering — it would leak
                                          # into the GROUP BY of the aggregate
        .values('decision_step__cycle_id')
        .annotate(_last=Max(Coalesce('due_date', 'scheduled_date')))
        .values('_last')[:1]
    )
    return Subquery(last_closing_activity, output_field=DateField())


def effective_close_date_expr():
    """THE rule, as ONE expression: the manual date, else the closing-step
    fallback, else NULL. Every binding below is built from this."""
    return Coalesce(
        'expected_close_date',
        _closing_activity_date_subquery(),
        output_field=DateField(),
    )


def annotate_effective_close_date(queryset):
    """Annotate a DecisionCycle queryset with its effective close date under
    ``CLOSE_DATE_ALIAS``.

    This is the ONLY performant path for a mass read. Reading
    ``cycle.effective_close_date`` on an annotated row costs no extra query (the
    property reads the annotation); on a non-annotated instance it costs one.
    """
    return queryset.annotate(**{CLOSE_DATE_ALIAS: effective_close_date_expr()})


def effective_close_date_for(cycle):
    """The effective close date of ONE cycle, in one query, from the same rule.

    Short-circuits on the manual field: when it is set the answer is already in
    hand and the fallback subquery is not worth a round trip.
    """
    if cycle.expected_close_date is not None:
        return cycle.expected_close_date

    from ..models import DecisionCycle

    return (
        annotate_effective_close_date(DecisionCycle.objects.filter(pk=cycle.pk))
        .values_list(CLOSE_DATE_ALIAS, flat=True)
        .first()
    )
