# backend/tests/signals/test_aggregated_stakeholder_filter.py
"""
Sprint « Cycle de vie des contacts », 8g-6 (TD-232 « See signals ») — the
`stakeholder` filter, modelled on `contact` (same places): the signals whose
source activity counts this NON-converted stakeholder among its participants
(Activity.stakeholders, M2M).
  * GET /module-signals/all/?account_id=…&stakeholder=… — bounded by the
    tenant (the type ViewSets' queryset) and the account (the scope);
  * the per-type filterset: ?source_stakeholder=… (as ?source_contact=…).
Builders reused from test_aggregated_signals_endpoint.py.
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import SignalStatus
from tests.signals.test_aggregated_signals_endpoint import _mk_blocker, _mk_pain, _results, _url
from tests.signals.test_signal_cycle_attachment import _cycle, _plain_activity


pytestmark = pytest.mark.django_db


def _stakeholder(cycle, user, name='Marc'):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, full_name=name)
    s.save(user=user, client_id=cycle.client_id)
    return s


@pytest.fixture
def world(account, other_account, user_a):
    st = _stakeholder(_cycle(account, user_a), user_a)
    with_st = _plain_activity(account, user_a, 'Workshop with Marc')
    with_st.stakeholders.add(st)
    without = _plain_activity(account, user_a, 'Call without Marc')
    elsewhere = _plain_activity(other_account, user_a, 'Other account call')
    elsewhere.stakeholders.add(st)
    rejected = _mk_blocker(account, with_st, user_a)
    type(rejected).objects.filter(pk=rejected.pk).update(status=SignalStatus.REJECTED)
    return {
        'st': st,
        'in': _mk_pain(account, with_st, user_a),
        'out': _mk_pain(account, without, user_a),
        'other_account': _mk_pain(other_account, elsewhere, user_a),
        'rejected': rejected,
    }


def _ids(r):
    assert r.status_code == status.HTTP_200_OK, r.content
    return {row['id'] for row in _results(r)}


def test_the_signals_of_the_activities_the_stakeholder_took_part_in(authed_api_a, account, world):
    r = authed_api_a.get(_url(), {'account_id': str(account.id), 'stakeholder': str(world['st'].id)})
    assert _ids(r) == {str(world['in'].id)}            # not `out`, not the other account, not rejected


def test_another_tenant_sees_nothing(authed_api_b, account, world):
    r = authed_api_b.get(_url(), {'account_id': str(account.id), 'stakeholder': str(world['st'].id)})
    assert _ids(r) == set()


def test_an_invalid_stakeholder_is_a_400(authed_api_a, account):
    r = authed_api_a.get(_url(), {'account_id': str(account.id), 'stakeholder': 'nope'})
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content


def test_the_type_endpoint_filters_on_source_stakeholder(authed_api_a, world):
    r = authed_api_a.get('/module-signals/pain/', {'source_stakeholder': str(world['st'].id)})
    assert r.status_code == status.HTTP_200_OK, r.content
    body = r.json()
    rows = body.get('results', body.get('data', body))
    if isinstance(rows, dict):
        rows = rows.get('results', [])
    assert {row['id'] for row in rows} == {str(world['in'].id), str(world['other_account'].id)}
