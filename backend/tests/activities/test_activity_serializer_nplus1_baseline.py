# backend/tests/activities/test_activity_serializer_nplus1_baseline.py
"""
RE-MEASURE (GREEN) — Sprint Timeout (vague 2) / Fil sérialiseur activité.

Two endpoints share ONE serializer, `ActivityListSerializer`
(app_modules/activities/serializers.py:215):

  - GET /module-activities/            -> ActivityViewSet.list
  - GET /module-activities/by-account/ -> ActivityViewSet.by_account

They used to be N+1: get_contacts_count / get_contacts (+ per-contact
standard_department) / get_campaign_contact_status each hit the DB per row,
because ActivityViewSet.get_queryset (list branch + else branch) prepared none
of them. The graved RED baseline (commit a802c6aa), 2 contacts/activity:

    /module-activities/            : page 10 = 52 queries, page 20 = 102
    /module-activities/by-account/ : page 10 = 52 queries, page 20 = 102
    slope = 5 queries / activity (= 3 + K contacts), identical on both endpoints

The fix prepares those relations once on the queryset of BOTH paths
(get_queryset list + else branches):
    select_related('campaign_contact')
    prefetch_related(Prefetch('contacts', queryset=Contact.objects.select_related('standard_department')))
    annotate(_contacts_count=Count('contacts'))

so the serializer reads prepared data instead of querying per row.

This module now GUARDS the fixed behaviour: the query count is FLAT across page
sizes (slope 0) on BOTH endpoints, with zero per-activity contacts /
standard_departments / campaign_contact repeats. Revert any of the three
preparations and the slope climbs back and these tests fail (non-vacuity).

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import (
    CampaignAccountStatus,
    CampaignStatus,
    CampaignType,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
from app_modules.contacts.models import Contact
from app_modules.core_modules.models import StandardDepartment

TODAY = timezone.now().date()

# Volume: enough activities to fill a page of 50, each with contacts (each with a
# standard_department) AND a campaign_contact — the realistic campaign-navigation
# case. Shared contacts + a shared campaign_contact are enough: pre-fix the
# queryset prefetched none of them, so each activity re-hit them per row.
N_ACTIVITIES = 60
CONTACTS_PER_ACTIVITY = 2
PAGE_SMALL = 20
PAGE_LARGE = 50


@pytest.fixture
def activity_dataset(db, account, user_a, client_account_a):
    """N activities on one account, each with CONTACTS_PER_ACTIVITY contacts
    (each with a standard_department) and a shared campaign_contact."""
    ca = client_account_a
    # StandardDepartment is a pre-seeded controlled list with a unique name.
    dept, _ = StandardDepartment.objects.get_or_create(
        name=StandardDepartment.DepartmentChoices.SALES
    )

    shared_contacts = []
    for i in range(CONTACTS_PER_ACTIVITY):
        c = Contact(
            account=account, first_name=f"C{i}", last_name="Doe",
            email=f"c{i}@acme.test", phone_number="+14155550123",
            linkedin="https://linkedin.com/in/c", standard_department=dept,
        )
        c.save(user=user_a, client_id=ca.id)
        shared_contacts.append(c)

    camp = Campaign(
        name="Serializer N+1", campaign_type=CampaignType.OUTBOUND, owner=user_a,
        status=CampaignStatus.ACTIVE, planned_start_date=TODAY,
        planned_end_date=TODAY + timedelta(days=30),
    )
    camp.save(user=user_a, client_id=ca.id)
    camp_acc = CampaignAccount(campaign=camp, account=account,
                              status=CampaignAccountStatus.IN_PROGRESS)
    camp_acc.save(user=user_a, client_id=ca.id)
    cc_contact = Contact(account=account, first_name="CC", last_name="Lead")
    cc_contact.save(user=user_a, client_id=ca.id)
    cc = CampaignContact(campaign_account=camp_acc, contact=cc_contact)
    cc.save(user=user_a, client_id=ca.id)

    for i in range(N_ACTIVITIES):
        a = Activity(
            title=f"Act {i}", activity_type=ActivityType.CALL,
            status=ActivityStatus.PLANNED, account=account, owner=user_a,
            campaign=camp, campaign_contact=cc,
            scheduled_date=TODAY + timedelta(days=i + 1),
        )
        a.save(user=user_a, client_id=ca.id)
        a.contacts.add(*shared_contacts)

    return account


@pytest.fixture(autouse=True)
def _dummy_cache_and_no_debug(settings):
    """Force the uncached path (DummyCache -> _is_redis_backend() is False) so
    every call pays the real serialization, and DEBUG off so the measurement
    isolates the serializer path (not the DEBUG-only client-scope double COUNT)."""
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}
    settings.DEBUG = False


def _get(authed_api_a, url, page_size, **params):
    q = f"?page_size={page_size}"
    for k, v in params.items():
        q += f"&{k}={v}"
    resp = authed_api_a.get(f"{url}{q}")
    assert resp.status_code == 200, resp.content
    return resp


def _rows(resp):
    return len(resp.data["data"]["results"])


def _per_activity_breakdown(captured):
    """Count the (formerly per-activity) queries in a trace, by table."""
    contacts_q = deps_q = campaign_contact_q = 0
    for qd in captured:
        sql = qd["sql"].lower()
        if "standard_departments" in sql:
            deps_q += 1
        elif "campaigncontact" in sql:
            campaign_contact_q += 1
        elif "module_contacts" in sql:
            contacts_q += 1
    return contacts_q, deps_q, campaign_contact_q


@pytest.mark.django_db
class TestActivitySerializerBounded:

    def test_list_query_count_is_flat(self, activity_dataset, authed_api_a):
        url = reverse('module_activities:list')

        with CaptureQueriesContext(connection) as cap_s:
            r_s = _get(authed_api_a, url, PAGE_SMALL)
        q_s, rows_s = len(cap_s.captured_queries), _rows(r_s)

        with CaptureQueriesContext(connection) as cap_l:
            r_l = _get(authed_api_a, url, PAGE_LARGE)
        q_l, rows_l = len(cap_l.captured_queries), _rows(r_l)

        slope = (q_l - q_s) / (rows_l - rows_s)
        contacts_q, deps_q, cc_q = _per_activity_breakdown(cap_l.captured_queries)

        print("\n" + "=" * 68)
        print("GREEN RE-MEASURE — GET /module-activities/ (prepared queryset)")
        print("=" * 68)
        print(f"  RED baseline (a802c6aa): page10=52 page20=102 slope=5/activity")
        print(f"  page_size={PAGE_SMALL:>2}  rows={rows_s:>2}  queries={q_s}")
        print(f"  page_size={PAGE_LARGE:>2}  rows={rows_l:>2}  queries={q_l}")
        print(f"  slope (extra queries per activity)    : {slope}")
        print(f"  --- per-activity repeats in page={PAGE_LARGE} trace ---")
        print(f"  module_contacts queries               : {contacts_q}")
        print(f"  standard_departments queries          : {deps_q}")
        print(f"  campaign_contact queries              : {cc_q}")
        print("=" * 68 + "\n")

        assert rows_s == PAGE_SMALL and rows_l == PAGE_LARGE
        # THE GREEN: query count is independent of the number of activities.
        assert q_l == q_s, f"query count still scales with rows: {q_s} vs {q_l}"
        assert slope == 0.0
        # No per-activity repeats survive: contacts fetched via ONE prefetch,
        # departments joined in it, campaign_contact select_related in the main
        # query. Each table appears at most a small constant number of times.
        assert contacts_q == 0
        assert deps_q <= 1
        assert cc_q <= 1

    def test_by_account_query_count_is_flat(self, activity_dataset, authed_api_a):
        acc = activity_dataset
        url = reverse('module_activities:by-account')

        with CaptureQueriesContext(connection) as cap_s:
            r_s = _get(authed_api_a, url, PAGE_SMALL, account_id=str(acc.id))
        q_s, rows_s = len(cap_s.captured_queries), _rows(r_s)

        with CaptureQueriesContext(connection) as cap_l:
            r_l = _get(authed_api_a, url, PAGE_LARGE, account_id=str(acc.id))
        q_l, rows_l = len(cap_l.captured_queries), _rows(r_l)

        slope = (q_l - q_s) / (rows_l - rows_s)
        contacts_q, deps_q, cc_q = _per_activity_breakdown(cap_l.captured_queries)

        print("\n" + "=" * 68)
        print("GREEN RE-MEASURE — GET /module-activities/by-account/ (prepared)")
        print("=" * 68)
        print(f"  RED baseline (a802c6aa): page10=52 page20=102 slope=5/activity")
        print(f"  page_size={PAGE_SMALL:>2}  rows={rows_s:>2}  queries={q_s}")
        print(f"  page_size={PAGE_LARGE:>2}  rows={rows_l:>2}  queries={q_l}")
        print(f"  slope (extra queries per activity)    : {slope}")
        print(f"  standard_departments queries          : {deps_q}")
        print(f"  campaign_contact queries              : {cc_q}")
        print("=" * 68 + "\n")

        assert rows_s == PAGE_SMALL and rows_l == PAGE_LARGE
        assert q_l == q_s, f"by_account still scales with rows: {q_s} vs {q_l}"
        assert slope == 0.0
        assert contacts_q == 0 and deps_q <= 1 and cc_q <= 1

    def test_both_endpoints_flat(self, activity_dataset, authed_api_a):
        """Both endpoints are now flat (slope 0) — the shared fix covers both."""
        list_url = reverse('module_activities:list')
        by_url = reverse('module_activities:by-account')
        acc = activity_dataset

        def _slope(url, **params):
            with CaptureQueriesContext(connection) as c1:
                r1 = _get(authed_api_a, url, PAGE_SMALL, **params)
            with CaptureQueriesContext(connection) as c2:
                r2 = _get(authed_api_a, url, PAGE_LARGE, **params)
            return (len(c2.captured_queries) - len(c1.captured_queries)) / (
                _rows(r2) - _rows(r1)
            )

        list_slope = _slope(list_url)
        by_slope = _slope(by_url, account_id=str(acc.id))

        print("\n" + "=" * 68)
        print("GREEN RE-MEASURE — both endpoints flat")
        print("=" * 68)
        print(f"  /module-activities/            slope : {list_slope}")
        print(f"  /module-activities/by-account/ slope : {by_slope}")
        print("=" * 68 + "\n")

        assert list_slope == 0.0
        assert by_slope == 0.0
