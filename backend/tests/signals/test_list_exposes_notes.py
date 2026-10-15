# backend/tests/signals/test_list_exposes_notes.py
"""
Verify the Pain / Constraint / TechStack LIST payloads expose `notes`.

The Activity detail + edit drawers are fed by the aggregated (list) payload
(GET /module-signals/all/?activity_id=…), which maps each type to its LIST
serializer — the detail is never re-fetched. These three LIST serializers
omitted `notes` while their edit forms always send it:

  * EditPainContent / EditConstraintContent  → notes: signal.notes || ""
  * InlineTechStackForm (via SignalEditDrawer) → notes: signal.notes ?? ""

so a save from Activity PATCHed notes to "" and silently ERASED the stored
value (and the detail never showed it). Same fix as the Objective precedent
(SIG-5e-fix4 P1, 295443e): expose `notes` on the LIST payload.

Each type has two checks through the real path:
  (a) the /all/ row carries `notes` with its value;
  (b) a PATCH built from that row exactly as the edit form builds it leaves
      the stored notes intact.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import (
    ConstraintNature,
    Rigidity,
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalWhat,
)
from app_modules.signals.models import (
    ConstraintSignal,
    PainSignal,
    TechStackSignal,
)


pytestmark = pytest.mark.django_db(transaction=True)


NOTES = 'Sponsor confirmed in the QBR'


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _all_row(api, activity, signal):
    """The signal's row in GET /module-signals/all/?activity_id=… (the Activity feed)."""
    response = api.get(
        reverse('module_signals:signal-all'),
        {'activity_id': str(activity.id)},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    rows = body.get('results', body)
    return next(r for r in rows if r['id'] == str(signal.id))


def _dept_ids(row, key):
    return [d['id'] for d in (row.get(key) or [])]


# Payload builders — mirror of each edit form's submit, fed by the LIST row.

def _pain_payload(row):
    # EditPainContent.jsx initialValues + onSubmit.
    return {
        'summary': (row.get('summary') or '').strip(),
        'what': row.get('what') or '',
        'dimension': row.get('dimension') or '',
        'scope_level': row.get('scope_level'),
        'target_departments': _dept_ids(row, 'target_departments'),
        'notes': row.get('notes') or '',
        'related_techstack_mention': row.get('related_techstack_mention') or '',
        'source_quote': row.get('source_quote') or '',
    }


def _constraint_payload(row):
    # EditConstraintContent.jsx initialValues + onSubmit.
    return {
        'summary': (row.get('summary') or '').strip(),
        'nature': row.get('nature') or '',
        'rigidity': row.get('rigidity') or '',
        'notes': row.get('notes') or '',
        'target_departments': _dept_ids(row, 'target_departments'),
        'source_quote': row.get('source_quote') or '',
    }


def _techstack_payload(row):
    # buildEditInitialValues.js (tech-stack) + InlineTechStackForm.jsx onSubmit.
    return {
        'tech_name': (row.get('tech_name') or '').strip(),
        'is_to_replace': bool(row.get('is_to_replace')),
        'usage_scope': row.get('usage_scope') or None,
        'usage_departments': _dept_ids(row, 'usage_departments'),
        'usage_start_year': row.get('usage_start_year'),
        'renewal_date': row.get('renewal_date') or None,
        'cost_description': (row.get('cost_description') or '').strip(),
        'is_discontinued': bool(row.get('is_discontinued')),
        'discontinued_date': (
            row.get('discontinued_date') if row.get('is_discontinued') else None
        ),
        'source_quote': (row.get('source_quote') or '').strip() or None,
        'notes': (row.get('notes') or '').strip(),
    }


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------

def _mk_pain(account, activity, user):
    p = PainSignal(
        account=account, source_activity=activity,
        source=SignalSource.MANUAL,
        what=SignalWhat.DATA, dimension=SignalDimension.QUALITY,
        scope_level=ScopeLevel.BUSINESS, summary='pain here',
        source_quote='we lose data', notes=NOTES,
    )
    p.save(user=user, client_id=account.client_id)
    return p


def _mk_constraint(account, activity, user):
    c = ConstraintSignal(
        account=account, source_activity=activity,
        source=SignalSource.MANUAL,
        nature=ConstraintNature.TECHNICAL, rigidity=Rigidity.FIRM,
        summary='must stay on-prem', source_quote='no cloud', notes=NOTES,
    )
    c.save(user=user, client_id=account.client_id)
    return c


def _mk_tech(account, activity, user):
    t = TechStackSignal(
        account=account, source_activity=activity,
        source=SignalSource.MANUAL, tech_name='Salesforce',
        source_quote='we run on Salesforce', notes=NOTES,
    )
    t.save(user=user, client_id=account.client_id)
    return t


CASES = [
    pytest.param(_mk_pain, 'pain', _pain_payload, id='pain'),
    pytest.param(_mk_constraint, 'constraint', _constraint_payload, id='constraint'),
    pytest.param(_mk_tech, 'tech-stack', _techstack_payload, id='tech-stack'),
]


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

class TestListExposesNotes:

    @pytest.mark.parametrize('make, route, build_payload', CASES)
    def test_all_row_carries_notes(
        self, make, route, build_payload, authed_api_a, account, activity, user_a,
    ):
        signal = make(account, activity, user_a)

        row = _all_row(authed_api_a, activity, signal)

        assert 'notes' in row, f'{route}: /module-signals/all/ row has no `notes` key'
        assert row['notes'] == NOTES

    @pytest.mark.parametrize('make, route, build_payload', CASES)
    def test_edit_from_list_row_keeps_notes(
        self, make, route, build_payload, authed_api_a, account, activity, user_a,
    ):
        signal = make(account, activity, user_a)
        row = _all_row(authed_api_a, activity, signal)

        response = authed_api_a.patch(
            reverse(f'module_signals:{route}-detail', kwargs={'pk': signal.id}),
            build_payload(row),
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK, response.json()

        signal.refresh_from_db()
        assert signal.notes == NOTES, f'{route}: notes erased by an edit from the list row'
