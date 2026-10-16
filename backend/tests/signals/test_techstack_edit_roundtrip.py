# backend/tests/signals/test_techstack_edit_roundtrip.py
"""
Sprint TechStack T2b — the Activity TechStack edit drawer round-trip.

The drawer (EditTechStackContent) is opened with the /module-signals/all/
row and PATCHes every field it edits — never is_to_replace (out of the UI,
kept in the DB). This test builds the payload exactly as the form does from
that row, applies a rep's edits, PATCHes the real route and reads the row
back from the database.

Characterisation of the backend contract the drawer relies on (no backend
change in T2b): string department ids accepted, the three usage cases, the
discontinued pair, and is_to_replace left untouched.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def sales(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Sales')
    return d


@pytest.fixture
def marketing(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return d


def _tech(account, activity, user, sales):
    sig = TechStackSignal(
        account=account, source_activity=activity,
        source=SignalSource.LLM_EXTRACTED, tech_name='HubSpot',
        usage_scope='DEPARTMENT', is_to_replace=True,
        source_quote='Sales lives in HubSpot.', notes='Initial note',
    )
    sig.save(user=user, client_id=account.client_id)
    sig.usage_departments.set([sales])
    return sig


def _all_row(api, activity, signal):
    response = api.get(
        reverse('module_signals:signal-all'), {'activity_id': str(activity.id)},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    rows = body.get('results', body)
    return next(r for r in rows if r['id'] == str(signal.id))


def _form_payload(row, **edits):
    """
    Mirror of EditTechStackContent: initial values read from the LIST row,
    the rep's edits applied, then the submit mapping (departments sent only
    for DEPARTMENT, year as a number, empty dates -> null, no is_to_replace).
    """
    values = {
        'tech_name': row['tech_name'] or '',
        'usage_scope': row['usage_scope'] or 'UNKNOWN',
        'usage_departments': [d['id'] for d in row['usage_departments']],
        'usage_start_year': row['usage_start_year'],
        'renewal_date': row['renewal_date'] or '',
        'cost_description': row['cost_description'] or '',
        'is_discontinued': bool(row['is_discontinued']),
        'discontinued_date': row['discontinued_date'] or '',
        'notes': row['notes'] or '',
        'source_quote': row['source_quote'] or '',
    }
    values.update(edits)
    is_department = values['usage_scope'] == 'DEPARTMENT'
    return {
        'tech_name': values['tech_name'].strip(),
        'usage_scope': values['usage_scope'],
        'usage_departments': values['usage_departments'] if is_department else [],
        'usage_start_year': values['usage_start_year'],
        'renewal_date': values['renewal_date'] or None,
        'cost_description': values['cost_description'],
        'is_discontinued': values['is_discontinued'],
        'discontinued_date': (
            values['discontinued_date'] or None if values['is_discontinued'] else None
        ),
        'notes': values['notes'],
        'source_quote': values['source_quote'],
    }


def _patch(api, sig, payload):
    return api.patch(
        reverse('module_signals:tech-stack-detail', kwargs={'pk': sig.id}),
        payload, format='json',
    )


class TestTechStackEditRoundTrip:

    def test_every_edited_field_is_persisted(
        self, authed_api_a, account, activity, user_a, sales, marketing,
    ):
        sig = _tech(account, activity, user_a, sales)
        row = _all_row(authed_api_a, activity, sig)

        payload = _form_payload(
            row,
            tech_name='HubSpot CRM',
            usage_departments=[str(sales.id), str(marketing.id)],
            usage_start_year=2019,
            renewal_date='2027-01-31',
            cost_description='60k/year',
            is_discontinued=True,
            discontinued_date='2026-12-31',
            notes='Unhappy with support.',
            source_quote='Sales and Marketing live in HubSpot.',
        )
        assert 'is_to_replace' not in payload

        response = _patch(authed_api_a, sig, payload)
        assert response.status_code == status.HTTP_200_OK, response.json()

        sig.refresh_from_db()
        assert sig.tech_name == 'HubSpot CRM'
        assert sig.usage_scope == 'DEPARTMENT'
        assert set(sig.usage_departments.values_list('name', flat=True)) == {
            'Sales', 'Marketing',
        }
        assert sig.usage_start_year == 2019
        assert str(sig.renewal_date) == '2027-01-31'
        assert sig.cost_description == '60k/year'
        assert sig.is_discontinued is True
        assert str(sig.discontinued_date) == '2026-12-31'
        assert sig.notes == 'Unhappy with support.'
        assert sig.source_quote == 'Sales and Marketing live in HubSpot.'
        # Out of the UI, never sent: the stored value is untouched.
        assert sig.is_to_replace is True

    def test_company_clears_the_departments(
        self, authed_api_a, account, activity, user_a, sales,
    ):
        sig = _tech(account, activity, user_a, sales)
        row = _all_row(authed_api_a, activity, sig)

        response = _patch(authed_api_a, sig, _form_payload(row, usage_scope='COMPANY'))
        assert response.status_code == status.HTTP_200_OK, response.json()

        sig.refresh_from_db()
        assert sig.usage_scope == 'COMPANY'
        assert not sig.usage_departments.exists()
        assert sig.notes == 'Initial note'
        assert sig.is_to_replace is True

    def test_untick_discontinued_clears_the_date(
        self, authed_api_a, account, activity, user_a, sales,
    ):
        sig = _tech(account, activity, user_a, sales)
        sig.is_discontinued = True
        sig.discontinued_date = '2026-06-30'
        sig.save(user=user_a, client_id=account.client_id)
        row = _all_row(authed_api_a, activity, sig)

        response = _patch(authed_api_a, sig, _form_payload(row, is_discontinued=False))
        assert response.status_code == status.HTTP_200_OK, response.json()

        sig.refresh_from_db()
        assert sig.is_discontinued is False
        assert sig.discontinued_date is None
