# app_modules/signals/services/signal_cycle_attachment.py
"""
An activity's signals take its decision cycle -- THE one place
(sprint « Cycle de vie des contacts », étape 2).

SignalManager copies decision_cycle from the source activity when a signal is
CREATED (_propagate_activity_context). This service covers what happens
AFTER: an activity linked to a cycle once its signals exist --
  * « Start Decision Cycle » (5.13): the cycle is put on the NEW activity
    created from a campaign activity, never on the campaign activity itself;
  * an activity analysed first, then linked to a cycle (PATCH).

Triggered by the Activity post_save (activities/signals/
signal_cycle_attachment.py) when the activity's decision_cycle is set or
changes; also run, read-only or not, by the catch-up command
(manage.py attach_signals_to_cycles).

Rules (PO decisions):
  * the activities whose signals join: the activity itself, plus -- when it
    was created FROM a campaign activity (source_activity) -- every activity
    of that campaign activity's campaign_account (same campaign, same
    account): every prospect, every run;
  * every status (PENDING / VALIDATED / REJECTED);
  * every signal type with a decision_cycle column EXCEPT the ones in
    EXCLUDED_SIGNAL_TYPES (THE one exclusion list -- the hook and the
    catch-up command read it through _attachable_models);
  * decision_cycle only (no signal model has a decision_step column --
    SignalManager._ACTIVITY_PROPAGATED_FIELDS lists it, a no-op);
  * only a NULL decision_cycle is written. A signal already on ANOTHER cycle
    is never moved: counted, logged and returned (kept_on_other_cycle);
  * idempotent: a second run attaches nothing.

The writes are queryset updates (no per-signal save()), so the per-model
post_save receivers do not run: the signal / cluster caches and the
readiness score of the cycle are refreshed here, after commit.
"""

from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger(__name__)


# THE exclusion list (signal_type -> reason). Read by _attachable_models only.
EXCLUDED_SIGNAL_TYPES = {
    # Its born cycle is computed at read time (5.14b), never stored.
    'next_step': 'born cycle computed at read time (5.14b)',
    # (tech_stack, excluded temporarily in 2a, is re-included since 2b (3):
    # its scope is the explicit TechStackSignal.scope field, never the DC.)
}


def _all_cycle_models():
    """(signal_type, model) for every signal model with a decision_cycle
    column."""
    from app_modules.signals.models import (
        BlockerSignal, CompetitorSignal, ConstraintSignal, ImpactSignal,
        NextStepSignal, ObjectiveSignal, PainSignal, PeopleSignal, TechStackSignal,
    )
    return (
        ('pain', PainSignal),
        ('objective', ObjectiveSignal),
        ('impact', ImpactSignal),
        ('tech_stack', TechStackSignal),
        ('blocker', BlockerSignal),
        ('next_step', NextStepSignal),
        ('people', PeopleSignal),
        ('constraint', ConstraintSignal),
        ('competitor', CompetitorSignal),
    )


def _attachable_models():
    """(signal_type, model) for every signal joining a cycle -- every cycle
    model minus EXCLUDED_SIGNAL_TYPES."""
    return tuple(
        (signal_type, model) for signal_type, model in _all_cycle_models()
        if signal_type not in EXCLUDED_SIGNAL_TYPES
    )


@dataclass
class AttachmentResult:
    """Per signal type counts (types with 0 are omitted)."""
    cycle_id: object = None
    attached: dict = field(default_factory=dict)
    kept_on_other_cycle: dict = field(default_factory=dict)
    # 8c-0: People linked to a stakeholder at the passage campaign -> DC.
    people_linked: int = 0

    @property
    def total_attached(self):
        return sum(self.attached.values())

    @property
    def total_kept(self):
        return sum(self.kept_on_other_cycle.values())


def _source_campaign_account_id(activity):
    """The campaign_account of the activity `activity` was created FROM, or
    None — set = the passage campaign -> DC (« Start Decision Cycle »)."""
    from app_modules.activities.models import Activity
    if not activity.source_activity_id:
        return None
    return (
        Activity.objects
        .filter(pk=activity.source_activity_id, client_id=activity.client_id)
        .values_list('campaign_account_id', flat=True)
        .first()
    )


def source_activity_ids(activity):
    """
    The ids of the activities whose signals join `activity`'s cycle: the
    activity itself, plus the whole campaign_account sequence of the
    campaign activity it was created from.
    """
    from app_modules.activities.models import Activity

    ids = {activity.pk}
    source_id = activity.source_activity_id
    if source_id:
        campaign_account_id = _source_campaign_account_id(activity)
        if campaign_account_id:
            ids.update(
                Activity.objects
                .filter(campaign_account_id=campaign_account_id,
                        client_id=activity.client_id)
                .values_list('id', flat=True)
            )
    return ids


def attach_signals_to_activity_cycle(activity, *, dry_run=False):
    """
    Give `activity.decision_cycle` to the signals of its activities (see
    source_activity_ids) whose decision_cycle is NULL.

    Args:
        activity: an Activity (its decision_cycle_id as saved).
        dry_run: count only, write nothing.

    Returns:
        AttachmentResult -- attached / kept_on_other_cycle per signal type.
    """
    result = AttachmentResult(cycle_id=activity.decision_cycle_id)
    cycle_id = activity.decision_cycle_id
    if not cycle_id:
        return result

    ids = source_activity_ids(activity)
    for signal_type, model in _attachable_models():
        scoped = model.objects.filter(
            client_id=activity.client_id, source_activity_id__in=ids,
        )
        kept = (
            scoped.filter(decision_cycle_id__isnull=False)
            .exclude(decision_cycle_id=cycle_id)
            .count()
        )
        orphans = scoped.filter(decision_cycle_id__isnull=True)
        attached = orphans.count() if dry_run else orphans.update(decision_cycle_id=cycle_id)
        if attached:
            result.attached[signal_type] = attached
        if kept:
            result.kept_on_other_cycle[signal_type] = kept

    # 8c-0 (PO): at the passage campaign -> DC, every VALIDATED People of the
    # sequence is linked to a stakeholder of the DC (stakeholder_service —
    # THE match rule); PENDING ones keep resolve. Elsewhere: unchanged.
    if not dry_run and _source_campaign_account_id(activity):
        result.people_linked = _link_sequence_people(activity, ids, cycle_id)

    if result.attached or result.kept_on_other_cycle:
        logger.info(
            'signals_attached_to_cycle',
            extra={
                'activity_id': str(activity.pk),
                'cycle_id': str(cycle_id),
                'dry_run': dry_run,
                'attached': result.attached,
                'kept_on_other_cycle': result.kept_on_other_cycle,
            },
        )
    if result.kept_on_other_cycle:
        logger.warning(
            'signals_kept_on_other_cycle',
            extra={
                'activity_id': str(activity.pk),
                'cycle_id': str(cycle_id),
                'kept_on_other_cycle': result.kept_on_other_cycle,
            },
        )

    if result.attached and not dry_run:
        _refresh_after_commit(activity.client_id, cycle_id)
    return result


def _link_sequence_people(activity, ids, cycle_id):
    """The VALIDATED People of the sequence, on the cycle, not yet affiliated
    -> link_people_signal_automatically, oldest first. Returns the count."""
    from app_modules.decision_cycles.services.stakeholder_service import (
        link_people_signal_automatically,
    )
    from app_modules.signals.constants import SignalStatus
    from app_modules.signals.models import PeopleSignal

    linked = 0
    people = (
        PeopleSignal.objects
        .filter(client_id=activity.client_id, source_activity_id__in=ids,
                decision_cycle_id=cycle_id, status=SignalStatus.VALIDATED,
                stakeholder__isnull=True)
        .select_related('decision_cycle', 'target_contact', 'target_department')
        .order_by('created_at', 'id')
    )
    for people_signal in people:
        if link_people_signal_automatically(people_signal, activity.owner):
            linked += 1
    if linked:
        logger.info('people_linked_at_conversion', extra={
            'activity_id': str(activity.pk), 'cycle_id': str(cycle_id), 'linked': linked,
        })
    return linked


def _refresh_after_commit(client_id, cycle_id):
    """Signal + cluster caches of the tenant, readiness of the cycle -- the
    receivers a queryset update skips."""
    from app_modules.decision_cycles.signals.readiness_recompute import (
        _recompute_after_commit_by_id,
    )
    from app_modules.signals.signals.cache_invalidation import (
        _invalidate_clusters_after_commit,
        _invalidate_signals_after_commit,
    )
    _invalidate_signals_after_commit(str(client_id))
    _invalidate_clusters_after_commit(str(client_id))
    _recompute_after_commit_by_id(cycle_id)
