# app_modules/signals/services/next_step_link_service.py
"""
Next step "link to an existing activity" candidates (Sprint Next steps 2.3).

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
                  else today); an activity without a date comes last.

Ties end on created_at then id — a stable order. The first candidate is the
"link" proposal. A next step without a decision cycle has no candidate
(next steps are DC-only).
"""

import datetime

from app_modules.activities.constants import NON_TERMINAL_STATUSES

from ..constants import NEXT_STEP_LINK_RANKING


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


def link_candidates(signal):
    """
    The ranked open activities `signal` can be linked to, as
    [(activity, criteria)], best first ([] without a decision cycle).
    """
    from app_modules.activities.models import Activity

    if signal.decision_cycle_id is None:
        return []

    activities = (
        Activity.objects
        .filter(
            client_id=signal.client_id,
            decision_cycle_id=signal.decision_cycle_id,
            status__in=NON_TERMINAL_STATUSES,
        )
        .exclude(id=signal.source_activity_id)
        .select_related('decision_step')
        .prefetch_related('contacts')
    )
    signal_contacts = _signal_contact_ids(signal)
    reference_date = signal.suggested_due_date or datetime.date.today()

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
