# backend/tests/signals/test_source_context_contact_department.py
"""
B0: the standardised source_context.contacts block (SignalSourceSerializer)
must expose each contact's department so the unified signal line can render
"origin contact: name + job_title + department".

Shape matches the source_context block's own FK convention (decision_cycle /
campaign / decision_step / target_department are all {id, name}):

    department = {'id': <str>, 'name': <human display>}   # has standard_department
    department = None                                     # no standard_department

A contact keeps its existing keys (id, first_name, last_name, job_title);
department is additive.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource
from app_modules.signals.models import BlockerSignal


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def marketing_dept(db):
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return dept


@pytest.fixture
def contact_with_dept(db, account, user_a, marketing_dept):
    from app_modules.contacts.models import Contact
    c = Contact(
        account=account,
        first_name='Dana',
        last_name='Marketing',
        job_title='CMO',
        standard_department=marketing_dept,
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


def _results(response):
    body = response.json()
    results = body.get('results') or body.get('data', {}).get('results') or body
    if isinstance(results, dict):
        results = results.get('results', results)
    return results


def _row(response, signal_id):
    return next(r for r in _results(response) if r['id'] == str(signal_id))


class TestSourceContextContactDepartment:

    def test_contact_with_department_exposes_id_and_name(
        self, authed_api_a, account, activity, user_a,
        contact_with_dept, marketing_dept,
    ):
        activity.contacts.add(contact_with_dept)

        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='blocker with a departmented contact',
            source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)

        resp = authed_api_a.get(
            reverse('module_signals:blocker-list'),
            {'source_activity': str(activity.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        row = _row(resp, b.id)

        contacts = row['source_context']['contacts']
        entry = next(c for c in contacts if c['id'] == str(contact_with_dept.id))
        # Existing keys preserved
        assert entry['first_name'] == 'Dana'
        assert entry['job_title'] == 'CMO'
        # New department field — {id, name}, matching the block convention
        assert entry['department'] == {
            'id':   str(marketing_dept.id),
            'name': marketing_dept.get_name_display(),
        }

    def test_contact_without_department_is_null(
        self, authed_api_a, account, activity, user_a, contact,
    ):
        # `contact` fixture has no standard_department.
        activity.contacts.add(contact)

        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='blocker with a department-less contact',
            source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)

        resp = authed_api_a.get(
            reverse('module_signals:blocker-list'),
            {'source_activity': str(activity.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        row = _row(resp, b.id)

        contacts = row['source_context']['contacts']
        entry = next(c for c in contacts if c['id'] == str(contact.id))
        assert 'department' in entry
        assert entry['department'] is None
