# backend/tests/signals/test_aggregated_filter_validation.py
"""
Sprint « Cycle de vie des contacts », 8h — the inline filter pattern's
server side. GET /module-signals/all/:
  * `signal_type` and `status` are repeatable;
  * an INVALID value is a standard 400 (centralised SignalErrorMessages),
    as the view's docstring says — formerly ignored silently (empty list);
  * CONTRACT (« no dead filter »): every type option the front filter
    definitions can expose (utils/signalTypes.js SIGNAL_TYPE_META, the
    source of utils/filters/signalFilters.js) is a type the server evaluates.
"""

import re
from pathlib import Path

import pytest
from rest_framework import status

from app_modules.signals.views.aggregated_signal_view import _TYPES
from tests.signals.test_aggregated_signals_endpoint import _mk_blocker, _mk_pain, _results, _url
from tests.signals.test_signal_cycle_attachment import _plain_activity


FRONT_SIGNAL_TYPES = Path(__file__).resolve().parents[3] / 'frontend' / 'src' / 'utils' / 'signalTypes.js'


@pytest.mark.django_db
class TestAggregatedFilterValidation:

    def _get(self, api, account, **params):
        return api.get(_url(), {'account_id': str(account.id), **params})

    def test_several_signal_types_restrict_the_list(self, authed_api_a, account, user_a):
        activity = _plain_activity(account, user_a)
        _mk_pain(account, activity, user_a)
        _mk_blocker(account, activity, user_a)
        r = self._get(authed_api_a, account, signal_type=['pain', 'blockers'])
        assert r.status_code == status.HTTP_200_OK, r.content
        assert sorted(row['signal_type'] for row in _results(r)) == ['blockers', 'pain']
        r = self._get(authed_api_a, account, signal_type=['pain'])
        assert [row['signal_type'] for row in _results(r)] == ['pain']

    @pytest.mark.parametrize('values', [['bogus'], ['pain', 'bogus']])
    def test_an_invalid_signal_type_is_a_400(self, authed_api_a, account, values):
        r = self._get(authed_api_a, account, signal_type=values)
        assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
        assert 'bogus' in r.content.decode()

    def test_an_invalid_status_is_a_400(self, authed_api_a, account):
        r = self._get(authed_api_a, account, status=['PENDING', 'DONE'])
        assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
        assert 'DONE' in r.content.decode()

    def test_valid_statuses_pass(self, authed_api_a, account):
        r = self._get(authed_api_a, account, status=['PENDING', 'VALIDATED', 'REJECTED'])
        assert r.status_code == status.HTTP_200_OK, r.content


def test_contract_every_front_type_option_is_evaluated_by_the_server():
    if not FRONT_SIGNAL_TYPES.exists():
        pytest.skip('frontend sources not present')
    source = FRONT_SIGNAL_TYPES.read_text()
    meta = source[source.index('export const SIGNAL_TYPE_META = {'):]
    meta = meta[:meta.index('};')]
    front = set(re.findall(r'^\s*"?([a-z-]+)"?:\s*\{\s*label', meta, flags=re.M))
    qual = source[source.index('export const QUALIFICATION_SIGNAL_TYPES = ['):]
    qual = set(re.findall(r'"([a-z-]+)"', qual[:qual.index('];')]))
    server = {slug for slug, *_ in _TYPES}
    assert len(front) == 9 and qual <= front
    assert front <= server, f'dead filter options: {sorted(front - server)}'
