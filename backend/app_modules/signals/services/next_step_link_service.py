# app_modules/signals/services/next_step_link_service.py
"""
Next step "link to an existing activity" (Sprint Next steps 2.3 / 2.4).

  * link_candidates   — the activities a next step can be linked to, ranked;
  * link_differences  — what the next step proposes that differs from one of
                        those activities (the differences screen), by section;
  * attach_next_step  — the link itself, with the changes the rep chose.

Candidates
----------

link_candidates(signal) — the OPEN activities (NON_TERMINAL_STATUSES) of the
next step's decision cycle, same tenant, the next step's own conversation
(source_activity) excepted, ranked by the criteria of NEXT_STEP_LINK_RANKING
(signals/constants.py), in that order:

  shared_people — how many contacts of the next step's People
                  (suggested_people → target_contact) and of its
                  suggested_contacts are also on the activity — more first;
  same_step     — the activity is on the proposed DC step;
  same_type     — the activity has the proposed type;
  closest_date  — gap in days between the activity's date (scheduled_date,
                  else due_date) and the next step's date (suggested_due_date,
                  else today in the project's time zone, timezone.localdate);
                  an activity without a date comes last.

Ties end on created_at then id — a stable order. The first candidate is the
"link" proposal. The decision cycle is next_step_cycle: the next step's own,
else -- a next step of a SUCCESSFUL campaign activity (5.14b) -- the cycle
born from its conversation; without one, no candidate.

Differences (one dict per candidate; a section without difference is absent)
-----------
  activity_type / date / decision_step — single-choice fields:
                    {current, proposed}; the proposed date field follows D6 on
                    the activity's type (SCHEDULED_DATE_ACTIVITY_TYPES);
  call_to_action / description — texts: {current, proposed} (the UI offers to
                    append the proposal);
  contacts        — {to_add}: the next step's contacts missing on the activity.

Link (attach_next_step), in ONE transaction (the caller's)
----
  the `updates` the rep chose (NEXT_STEP_LINK_UPDATE_FIELDS only) are applied
  through ActivityUpdateSerializer — same validations, campaign lock COND-1
  included — no other field is touched; then attached_activity is set and the
  signal validated LAST (SignalManager.validate: the 2.1 invariants), so any
  refusal rolls the updates back.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from app_modules.activities.constants import (
    NON_TERMINAL_STATUSES,
    SCHEDULED_DATE_ACTIVITY_TYPES,
)
from core.error_messages import CoreErrorMessages, SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import (
    NEXT_STEP_LINK_RANKING,
    NEXT_STEP_LINK_UPDATE_FIELDS,
    SignalStatus,
)


def _signal_contact_ids(signal):
    """Contacts the next step involves: its People's contacts + its
    suggested contacts."""
    ids = {
        p.target_contact_id
        for p in signal.suggested_people.all()
        if p.target_contact_id
    }
    ids.update(signal.suggested_contacts.values_list('id', flat=True))
    return ids


def _activity_date(activity):
    return activity.scheduled_date or activity.due_date


def _criteria(activity, signal, signal_contacts, reference_date):
    """Per-criterion values of `activity` (shown to the rep as the reasons of
    the ranking)."""
    activity_contacts = {c.id for c in activity.contacts.all()}
    date = _activity_date(activity)
    return {
        'shared_people':     len(activity_contacts & signal_contacts),
        'same_step':         (
            signal.suggested_decision_step_id is not None
            and activity.decision_step_id == signal.suggested_decision_step_id
        ),
        'same_type':         activity.activity_type == signal.suggested_activity_type,
        'date_distance_days': (
            abs((date - reference_date).days) if date is not None else None
        ),
    }


# Sort-key part of each criterion — smaller sorts first.
_SORT_KEY = {
    'shared_people': lambda c: -c['shared_people'],
    'same_step':     lambda c: 0 if c['same_step'] else 1,
    'same_type':     lambda c: 0 if c['same_type'] else 1,
    'closest_date':  lambda c: (
        (1, 0) if c['date_distance_days'] is None else (0, c['date_distance_days'])
    ),
}


def _candidate_activities(signal):
    """The activities `signal` can be linked to (unranked): the open ones of
    its decision cycle (next_step_cycle: its own, else the one born from its
    campaign conversation), same tenant, its own conversation excepted."""
    from app_modules.activities.models import Activity
    from app_modules.activities.services.next_step_materialization import next_step_cycle

    cycle = next_step_cycle(signal)
    if cycle is None:
        return Activity.objects.none()
    return (
        Activity.objects
        .filter(
            client_id=signal.client_id,
            decision_cycle_id=cycle.id,
            status__in=NON_TERMINAL_STATUSES,
        )
        .exclude(id=signal.source_activity_id)
    )


def link_candidates(signal):
    """
    The ranked open activities `signal` can be linked to, as
    [(activity, criteria)], best first ([] without a decision cycle).
    """
    activities = (
        _candidate_activities(signal)
        .select_related('decision_step')
        .prefetch_related('contacts')
    )
    signal_contacts = _signal_contact_ids(signal)
    reference_date = signal.suggested_due_date or timezone.localdate()

    ranked = [
        (activity, _criteria(activity, signal, signal_contacts, reference_date))
        for activity in activities
    ]
    ranked.sort(key=lambda pair: (
        tuple(_SORT_KEY[name](pair[1]) for name in NEXT_STEP_LINK_RANKING),
        pair[0].created_at,
        pair[0].id,
    ))
    return ranked


# =============================================================================
# DIFFERENCES next step ↔ activity
# =============================================================================

def _signal_contacts(signal):
    """The contacts the next step involves (its People's contacts + its
    suggested contacts), ordered by name."""
    contacts = {
        p.target_contact.id: p.target_contact
        for p in signal.suggested_people.all()
        if p.target_contact_id
    }
    contacts.update({c.id: c for c in signal.suggested_contacts.all()})
    return sorted(contacts.values(), key=lambda c: (c.last_name, c.first_name, str(c.id)))


def _date_value(field, value):
    return {'field': field, 'value': value.isoformat()} if value else None


def _step_value(step):
    return {'id': str(step.id), 'name': step.name} if step is not None else None


def link_differences(signal, activity):
    """What `signal` proposes that differs from `activity`, by section
    (module docstring); {} when nothing differs."""
    from app_modules.activities.services.next_step_materialization import (
        next_step_objective,
    )

    differences = {}

    if signal.suggested_activity_type != activity.activity_type:
        differences['activity_type'] = {
            'current':  activity.activity_type,
            'proposed': signal.suggested_activity_type,
        }

    if signal.suggested_due_date:
        current = (
            _date_value('scheduled_date', activity.scheduled_date)
            or _date_value('due_date', activity.due_date)
        )
        proposed = _date_value(
            'scheduled_date'
            if activity.activity_type in SCHEDULED_DATE_ACTIVITY_TYPES
            else 'due_date',
            signal.suggested_due_date,
        )
        if current != proposed:
            differences['date'] = {'current': current, 'proposed': proposed}

    proposed_step = signal.suggested_decision_step
    if (
        proposed_step is not None
        and proposed_step.cycle_id == activity.decision_cycle_id
        and proposed_step.id != activity.decision_step_id
    ):
        differences['decision_step'] = {
            'current':  _step_value(activity.decision_step),
            'proposed': _step_value(proposed_step),
        }

    for field, proposed_text in (
        ('call_to_action', next_step_objective(signal)),
        ('description',    signal.suggested_topics),
    ):
        current_text = getattr(activity, field) or ''
        if proposed_text and proposed_text != current_text:
            differences[field] = {'current': current_text, 'proposed': proposed_text}

    on_activity = {c.id for c in activity.contacts.all()}
    to_add = [c for c in _signal_contacts(signal) if c.id not in on_activity]
    if to_add:
        differences['contacts'] = {'to_add': [
            {'id': str(c.id), 'first_name': c.first_name, 'last_name': c.last_name}
            for c in to_add
        ]}

    return differences


# =============================================================================
# LINK — attach the next step to an existing activity
# =============================================================================

def attach_next_step(signal, activity_id, updates, request):
    """
    Link `signal` to the candidate activity `activity_id`, applying the
    `updates` the rep chose (module docstring). MUST run inside the caller's
    transaction: the signal is validated LAST so a refusal rolls everything
    back.

    Raises:
        StandardizedValidationError — updates outside
        NEXT_STEP_LINK_UPDATE_FIELDS, signal not PENDING, unknown /
        other-tenant activity, activity not a link candidate, invalid
        updates (ActivityUpdateSerializer), 2.1 invariants.
    """
    from app_modules.activities.models import Activity
    from app_modules.activities.serializers import ActivityUpdateSerializer
    from .signal_manager import SignalManager

    updates = updates or {}
    if not isinstance(updates, dict) or set(updates) - NEXT_STEP_LINK_UPDATE_FIELDS:
        raise StandardizedValidationError(
            SignalErrorMessages.NEXT_STEP_LINK_UPDATE_NOT_ALLOWED
        )
    if signal.status != SignalStatus.PENDING:
        raise StandardizedValidationError(SignalErrorMessages.NOT_PENDING_VALIDATED)

    try:
        activity = Activity.objects.get(id=activity_id, client_id=signal.client_id)
    except (Activity.DoesNotExist, DjangoValidationError, ValueError, TypeError):
        raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    if not _candidate_activities(signal).filter(id=activity.id).exists():
        raise StandardizedValidationError(
            SignalErrorMessages.NEXT_STEP_LINK_TARGET_INVALID
        )

    # The chosen changes only — contacts are ADDED to the current ones.
    payload = {k: v for k, v in updates.items() if k != 'add_contact_ids'}
    to_add = updates.get('add_contact_ids') or []
    if to_add:
        payload['contact_ids'] = [
            str(pk) for pk in activity.contacts.values_list('id', flat=True)
        ] + [str(pk) for pk in to_add]
    if payload:
        serializer = ActivityUpdateSerializer(
            activity, data=payload, partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

    signal.attached_activity = activity
    signal.save(user=request.user)
    return SignalManager.validate(signal, user=request.user)

