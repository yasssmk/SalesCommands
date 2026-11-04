# backend/tests/activities/test_conversion_single_birth.py
"""
Sprint « Cycle de vie des contacts », 8g-3 (TD-296) — ONE decision cycle is
born from a campaign activity. Two conversions (« Start Decision Cycle »)
of the same campaign activity, concurrent or one after the other, used to
give two born DCs. Now both creation paths lock the source activity
(select_for_update) and refuse a second birth
(activity_sequence_service.guard_decision_cycle_birth — born_decision_cycle
stays THE definition). Joining the cycle already born stays allowed.
"""

import threading
import time

import pytest
from django.db import connection

from tests.signals.test_signal_cycle_attachment import (
    TODAY, _campaign_account, _cycle, _prospect_activity,
)


def _activity_data(account, source, **extra):
    data = {'account_id': str(account.id), 'title': 'Follow-up', 'activity_type': 'TASK',
            'status': 'PLANNED', 'due_date': str(TODAY), 'source_activity_id': str(source.id)}
    data.update(extra)
    return data


def _convert(user, account, source, name):
    from app_modules.activities.services.activity_creation_service import ActivityCreationService
    return ActivityCreationService(user, account.client_id).create_with_entities(
        activity_data=_activity_data(account, source),
        inline_cycle={'name': name}, inline_step_stage='QUALIFICATION',
    )


def _born_cycles(account):
    from app_modules.decision_cycles.models import DecisionCycle
    return DecisionCycle.objects.filter(account=account).count()


@pytest.mark.django_db
def test_a_second_conversion_is_refused(account, user_a):
    from core.exceptions import StandardizedValidationError
    call = _prospect_activity(_campaign_account(account, user_a), user_a, 'Lea', outcome='SUCCESSFUL')
    _convert(user_a, account, call, 'Deal 1')
    with pytest.raises(StandardizedValidationError) as exc:
        _convert(user_a, account, call, 'Deal 2')
    assert 'already' in str(exc.value).lower()
    assert _born_cycles(account) == 1


@pytest.mark.django_db
def test_a_second_conversion_into_another_existing_cycle_is_refused(authed_api_a, account, user_a):
    call = _prospect_activity(_campaign_account(account, user_a), user_a, 'Lea', outcome='SUCCESSFUL')
    _convert(user_a, account, call, 'Deal 1')
    other = _cycle(account, user_a, 'Other deal')
    r = authed_api_a.post('/module-activities/', {
        **_activity_data(account, call, decision_cycle_id=str(other.id),
                         decision_step_id=str(other.qualification.id)),
    }, format='json')
    assert r.status_code == 400, r.content
    assert 'already' in r.content.decode().lower()


@pytest.mark.django_db
def test_joining_the_cycle_already_born_stays_allowed(authed_api_a, account, user_a):
    call = _prospect_activity(_campaign_account(account, user_a), user_a, 'Lea', outcome='SUCCESSFUL')
    born = _convert(user_a, account, call, 'Deal 1')['cycle']
    step = born.steps.order_by('order').first()
    r = authed_api_a.post('/module-activities/', {
        **_activity_data(account, call, decision_cycle_id=str(born.id), decision_step_id=str(step.id)),
    }, format='json')
    assert r.status_code == 201, r.content


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_conversions_give_one_born_cycle(account, user_a, monkeypatch):
    """Two threads convert the same campaign activity at the same time; the
    cycle creation is slowed down so both pass any check before either
    commits — only the lock on the source activity makes the second wait,
    then see the born cycle and be refused."""
    from app_modules.activities.services.activity_creation_service import ActivityCreationService
    call = _prospect_activity(_campaign_account(account, user_a), user_a, 'Lea', outcome='SUCCESSFUL')

    real_create_cycle = ActivityCreationService._create_cycle

    def slow_create_cycle(self, *args, **kwargs):
        time.sleep(0.6)
        return real_create_cycle(self, *args, **kwargs)

    monkeypatch.setattr(ActivityCreationService, '_create_cycle', slow_create_cycle)

    barrier = threading.Barrier(2)
    outcomes = []

    def convert(name):
        try:
            barrier.wait()
            _convert(user_a, account, call, name)
            outcomes.append('ok')
        except Exception as exc:  # noqa: BLE001 — the refusal is the expected outcome
            outcomes.append(type(exc).__name__)
        finally:
            connection.close()

    threads = [threading.Thread(target=convert, args=(f'Deal {i}',)) for i in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(outcomes) == ['StandardizedValidationError', 'ok'], outcomes
    assert _born_cycles(account) == 1
