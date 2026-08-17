# backend/tests/campaigns/test_outbound_target_departments.py
"""
S13 sub-step 3/6 — campaign-level target departments + OUTBOUND enrollment filter.

An OUTBOUND campaign can declare TARGET DEPARTMENTS (a campaign-wide M2M to
StandardDepartment). At creation, _enroll_from_territories only pre-creates
CampaignContact rows for contacts whose standard_department is in the target set
(still excluding unreachable / opted_out). Empty target set = unchanged behaviour.

Real creation path: POST /campaigns/ (CampaignCreateSerializer.create ->
CampaignCreationService._enroll_from_territories). Postgres.

Mirrors tests/campaigns/test_activity_objective_outbound.py for the create
endpoint + territory setup and tests/contacts/test_contact_filter.py for
StandardDepartment.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignStatus, CampaignType
from app_modules.campaigns.models import Campaign, CampaignContact
from app_modules.campaigns.services.campaign_lifecycle_service import CampaignLifecycleService
from app_modules.contacts.models import Contact
from app_modules.territories.models import Territory

CREATE_URL = '/campaigns/'


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _dept(name):
    from app_modules.core_modules.models.standar_dept import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name=name)
    return d


def _contact(account, user_a, *, dept=None, email='c@example.io', opted_out=False):
    c = Contact(
        account=account, first_name='C', last_name='X',
        email=email, opted_out=opted_out, standard_department=dept,
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


def _territory(user_a, client_id):
    """Permissive territory (empty filter_definition) → all tenant accounts."""
    t = Territory(name='All Tenant', owner=user_a, filter_definition={})
    t.save(user=user_a, client_id=client_id)
    return t


def _create_outbound(api, territory, *, target_department_ids=None,
                     activity_objective=None):
    today = timezone.now().date()
    data = {
        'name': 'Dept Outbound',
        'campaign_type': CampaignType.OUTBOUND,
        'territory_ids': [str(territory.id)],
        'start_date': str(today),
        'end_date': str(today + timedelta(days=30)),
    }
    if target_department_ids is not None:
        data['target_department_ids'] = target_department_ids
    if activity_objective is not None:
        data['activity_objective'] = activity_objective
    return api.post(CREATE_URL, data=data, format='json')


def _enrolled_contact_ids(campaign):
    return set(
        CampaignContact.objects.filter(campaign_account__campaign=campaign)
        .values_list('contact_id', flat=True)
    )


# ---------------------------------------------------------------------------
# RED repro — target=[IT] enrolls only IT contacts
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_target_it_enrolls_only_it_contacts(authed_api_a, account, user_a, client_account_a):
    it = _dept('IT')
    sales = _dept('Sales')
    it_contact = _contact(account, user_a, dept=it, email='it@example.io')
    sales_contact = _contact(account, user_a, dept=sales, email='sales@example.io')

    territory = _territory(user_a, client_account_a.id)
    resp = _create_outbound(authed_api_a, territory, target_department_ids=[it.id])
    assert resp.status_code in (200, 201), resp.data

    campaign = Campaign.objects.get(name='Dept Outbound')
    assert _enrolled_contact_ids(campaign) == {it_contact.id}, \
        "only the IT contact should be enrolled"
    assert sales_contact.id not in _enrolled_contact_ids(campaign)


# ---------------------------------------------------------------------------
# target=[IT, Sales] → both; Finance excluded
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_target_multiple_departments(authed_api_a, account, user_a, client_account_a):
    it = _dept('IT')
    sales = _dept('Sales')
    finance = _dept('Finance')
    it_c = _contact(account, user_a, dept=it, email='it@example.io')
    sales_c = _contact(account, user_a, dept=sales, email='sales@example.io')
    finance_c = _contact(account, user_a, dept=finance, email='fin@example.io')

    territory = _territory(user_a, client_account_a.id)
    resp = _create_outbound(authed_api_a, territory,
                            target_department_ids=[it.id, sales.id])
    assert resp.status_code in (200, 201), resp.data

    campaign = Campaign.objects.get(name='Dept Outbound')
    assert _enrolled_contact_ids(campaign) == {it_c.id, sales_c.id}
    assert finance_c.id not in _enrolled_contact_ids(campaign)


# ---------------------------------------------------------------------------
# no target departments → unchanged (all reachable non-opted-out)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_target_enrolls_all_reachable(authed_api_a, account, user_a, client_account_a):
    it = _dept('IT')
    sales = _dept('Sales')
    it_c = _contact(account, user_a, dept=it, email='it@example.io')
    sales_c = _contact(account, user_a, dept=sales, email='sales@example.io')

    territory = _territory(user_a, client_account_a.id)
    resp = _create_outbound(authed_api_a, territory)  # no target_department_ids
    assert resp.status_code in (200, 201), resp.data

    campaign = Campaign.objects.get(name='Dept Outbound')
    assert _enrolled_contact_ids(campaign) == {it_c.id, sales_c.id}


# ---------------------------------------------------------------------------
# opted_out + unreachable excluded regardless of department
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_opted_out_and_unreachable_excluded_within_target(
    authed_api_a, account, user_a, client_account_a
):
    it = _dept('IT')
    good = _contact(account, user_a, dept=it, email='good@example.io')
    opted = _contact(account, user_a, dept=it, email='opted@example.io', opted_out=True)
    # unreachable IT contact: no email/phone/linkedin
    unreachable = _contact(account, user_a, dept=it, email=None)

    territory = _territory(user_a, client_account_a.id)
    resp = _create_outbound(authed_api_a, territory, target_department_ids=[it.id])
    assert resp.status_code in (200, 201), resp.data

    campaign = Campaign.objects.get(name='Dept Outbound')
    enrolled = _enrolled_contact_ids(campaign)
    assert enrolled == {good.id}
    assert opted.id not in enrolled
    assert unreachable.id not in enrolled


# ---------------------------------------------------------------------------
# no cross-contamination with sub-step 1 (activity_objective still carried)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_activity_objective_still_carried_with_department_filter(
    authed_api_a, account, user_a, client_account_a
):
    it = _dept('IT')
    sales = _dept('Sales')
    it_c = _contact(account, user_a, dept=it, email='it@example.io')
    _contact(account, user_a, dept=sales, email='sales@example.io')

    territory = _territory(user_a, client_account_a.id)
    resp = _create_outbound(
        authed_api_a, territory,
        target_department_ids=[it.id],
        activity_objective='Book a discovery call',
    )
    assert resp.status_code in (200, 201), resp.data

    campaign = Campaign.objects.get(name='Dept Outbound')
    assert campaign.activity_objective == 'Book a discovery call'

    # Start the campaign to generate activities via the real lifecycle path.
    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).start(campaign)

    acts = list(Activity.objects.filter(campaign=campaign))
    assert acts, "start() should have generated activities for the IT contact"
    # Only the IT contact was enrolled, and its activity carries the objective.
    assert {a.campaign_contact.contact_id for a in acts} == {it_c.id}
    assert all(a.call_to_action == 'Book a discovery call' for a in acts), \
        [a.call_to_action for a in acts]
