# backend/tests/activities/test_activity_date_rule.py
"""
Sprint « Cycle de vie des contacts », 8g-1 (TD-230) — THE date rule of an
activity creation, ONE validator (services/date_rules.py, on the model of
participant_rules.py) called by BOTH creation paths:
  * POST /module-activities/                      (ActivityCreateSerializer)
  * POST /module-activities/create-with-entities/ (ActivityCreationService)
Rule: at least one date, and only one — a scheduled date OR a due date.
Refusals through the standard error system (400, a business message).
"""

import pytest
from rest_framework import status

from tests.activities.test_activity_stakeholders import URL, _payload


pytestmark = pytest.mark.django_db

CWE = '/module-activities/create-with-entities/'


def _cwe(api, activity):
    return api.post(CWE, {'activity': activity, 'inline_contact': None, 'inline_cycle': None,
                          'inline_step_stage': None}, format='json')


def _task(account, **dates):
    body = _payload(account, activity_type='TASK')
    body.pop('scheduled_date')
    body.update(dates)
    return body


@pytest.mark.parametrize('dates', [{}, {'scheduled_date': None, 'due_date': None}])
def test_create_with_entities_refuses_no_date(authed_api_a, account, dates):
    r = _cwe(authed_api_a, _task(account, **dates))
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert 'date' in r.content.decode().lower()


def test_create_with_entities_refuses_two_dates(authed_api_a, account):
    r = _cwe(authed_api_a, _task(account, scheduled_date='2026-11-20', due_date='2026-11-25'))
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert 'not both' in r.content.decode().lower()


@pytest.mark.parametrize('dates', [{'scheduled_date': '2026-11-20'}, {'due_date': '2026-11-25'}])
def test_create_with_entities_accepts_one_date(authed_api_a, account, dates):
    r = _cwe(authed_api_a, _task(account, **dates))
    assert r.status_code in (200, 201), r.content


def test_post_refuses_two_dates_too(authed_api_a, account):
    """The SAME rule on the standard create path."""
    r = authed_api_a.post(URL, _task(account, scheduled_date='2026-11-20', due_date='2026-11-25'),
                          format='json')
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert 'not both' in r.content.decode().lower()


def test_post_refuses_no_date(authed_api_a, account):
    r = authed_api_a.post(URL, _task(account), format='json')
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert 'date' in r.content.decode().lower()
