# backend/tests/activities/test_activity_serializer_equivalence.py
"""
BUSINESS EQUIVALENCE — Sprint Timeout (v2) / Fil sérialiseur activité.

The N+1 fix only changed the SOURCE of the data (select_related /
prefetch_related / Prefetch(contacts, select_related standard_department) /
annotate _contacts_count on ActivityViewSet.get_queryset), never the
serializer. These tests lock that the payload is byte-for-byte identical.

Reference = the pre-fix data path: ActivityListSerializer fed a PLAIN,
un-optimized instance (Activity.objects.get(...)), where the serializer falls
back to obj.contacts.count() / obj.contacts.all() / obj.campaign_contact — the
exact per-row queries the fix eliminated. The optimized endpoints must produce
the same dict for every activity.

Critical guard (get_contacts, enriched with phone_number + linkedin in sprint β):
get_contacts applies NO filter and NO explicit order — it iterates
obj.contacts.all(), so the contact set is ALL contacts, ordered by
Contact.Meta.ordering = ['last_name', 'first_name']. The Prefetch replacement
(no order_by, no filter) must reproduce exactly that set and order, with the
same coordinates (phone_number / email / linkedin / department).

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.activities.serializers import ActivityListSerializer
from app_modules.campaigns.constants import (
    CampaignAccountStatus,
    CampaignStatus,
    CampaignType,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
from app_modules.contacts.models import Contact
from app_modules.core_modules.models import StandardDepartment

TODAY = timezone.now().date()


@pytest.fixture(autouse=True)
def _dummy_cache_and_no_debug(settings):
    """Force the uncached path so each call serializes live, DEBUG off."""
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}
    settings.DEBUG = False


@pytest.fixture
def scenario(db, account, user_a, client_account_a):
    """Activities on one account with multi-contact fan-out in a non-trivial
    insertion order (so ordering is observable), coordinates populated, and a
    campaign_contact set (so get_campaign_contact_status is exercised)."""
    ca = client_account_a
    dept, _ = StandardDepartment.objects.get_or_create(
        name=StandardDepartment.DepartmentChoices.SALES
    )

    # Contacts inserted OUT of Meta order (Meta = last_name, first_name).
    # Expected serialized order: Alpha, Beta, Mistral, Zephyr.
    last_names = ["Zephyr", "Alpha", "Mistral", "Beta"]
    contacts = []
    for i, ln in enumerate(last_names):
        c = Contact(
            account=account, first_name=f"F{i}", last_name=ln,
            email=f"{ln.lower()}@acme.test", phone_number="+14155550123",
            linkedin=f"https://linkedin.com/in/{ln.lower()}",
            standard_department=dept,
        )
        c.save(user=user_a, client_id=ca.id)
        contacts.append(c)

    camp = Campaign(name="Equiv", campaign_type=CampaignType.OUTBOUND, owner=user_a,
                    status=CampaignStatus.ACTIVE, planned_start_date=TODAY,
                    planned_end_date=TODAY + timedelta(days=30))
    camp.save(user=user_a, client_id=ca.id)
    camp_acc = CampaignAccount(campaign=camp, account=account,
                              status=CampaignAccountStatus.IN_PROGRESS)
    camp_acc.save(user=user_a, client_id=ca.id)
    cc_contact = Contact(account=account, first_name="CC", last_name="Lead")
    cc_contact.save(user=user_a, client_id=ca.id)
    cc = CampaignContact(campaign_account=camp_acc, contact=cc_contact)
    cc.save(user=user_a, client_id=ca.id)

    activities = []
    for i in range(6):
        a = Activity(title=f"Act {i}", activity_type=ActivityType.CALL,
                     status=ActivityStatus.PLANNED, account=account, owner=user_a,
                     campaign=camp, campaign_contact=cc,
                     scheduled_date=TODAY + timedelta(days=i + 1))
        a.save(user=user_a, client_id=ca.id)
        # Attach all four contacts to each activity.
        a.contacts.add(*contacts)
        activities.append(a)

    return {'account': account, 'activities': activities, 'contacts': contacts}


def _reference(activity_ids):
    """Pre-fix data path: the SAME serializer on plain, un-optimized instances
    (per-row fallbacks). This is the ground-truth payload."""
    qs = Activity.objects.filter(id__in=activity_ids)
    return {str(a.id): ActivityListSerializer(a).data for a in qs}


def _rows(resp):
    return resp.data["data"]["results"]


@pytest.mark.django_db
class TestPayloadEquivalence:

    def test_list_payload_identical_to_reference(self, scenario, authed_api_a):
        ids = [str(a.id) for a in scenario['activities']]
        ref = _reference(ids)

        url = reverse('module_activities:list')
        resp = authed_api_a.get(f"{url}?page_size=100")
        assert resp.status_code == 200, resp.content

        rows = [r for r in _rows(resp) if r["id"] in ref]
        assert len(rows) == len(ids), "not all activities returned"
        for row in rows:
            assert dict(row) == dict(ref[row["id"]]), f"payload differs for {row['id']}"

    def test_by_account_payload_identical_to_reference(self, scenario, authed_api_a):
        ids = [str(a.id) for a in scenario['activities']]
        ref = _reference(ids)

        url = reverse('module_activities:by-account')
        resp = authed_api_a.get(f"{url}?account_id={scenario['account'].id}&page_size=100")
        assert resp.status_code == 200, resp.content

        rows = [r for r in _rows(resp) if r["id"] in ref]
        assert len(rows) == len(ids)
        for row in rows:
            assert dict(row) == dict(ref[row["id"]]), f"payload differs for {row['id']}"


@pytest.mark.django_db
class TestGetContactsEquivalence:

    def test_contacts_subset_order_and_coordinates_identical(self, scenario, authed_api_a):
        """The contacts list, its ORDER, and every coordinate are identical to
        the reference — and follow Contact.Meta.ordering (last_name, first_name)."""
        act = scenario['activities'][0]
        ref = _reference([str(act.id)])[str(act.id)]

        url = reverse('module_activities:list')
        resp = authed_api_a.get(f"{url}?page_size=100")
        row = next(r for r in _rows(resp) if r["id"] == str(act.id))

        # Same contacts, same order as the reference path.
        assert row["contacts"] == ref["contacts"]
        # And that order is the model default (last_name, first_name) — NOT the
        # insertion order (Zephyr, Alpha, Mistral, Beta).
        got_ids = [c["id"] for c in row["contacts"]]
        expected_ids = [str(c.id) for c in
                        Contact.objects.filter(id__in=got_ids).order_by('last_name', 'first_name')]
        assert got_ids == expected_ids, "contacts not in Meta order"

        # Coordinates (sprint β) present and exact on every contact.
        for c in row["contacts"]:
            assert c["phone_number"] == "+14155550123"
            assert c["linkedin"].startswith("https://linkedin.com/in/")
            assert c["email"].endswith("@acme.test")
            assert c["department"] == StandardDepartment.DepartmentChoices.SALES.label

    def test_contacts_count_not_cartesian_inflated(self, scenario, authed_api_a):
        """contacts_count == the real number of contacts (4), not inflated by
        the annotation joining other relations."""
        act = scenario['activities'][0]
        url = reverse('module_activities:list')
        resp = authed_api_a.get(f"{url}?page_size=100")
        row = next(r for r in _rows(resp) if r["id"] == str(act.id))

        assert row["contacts_count"] == 4
        assert row["contacts_count"] == len(row["contacts"])
