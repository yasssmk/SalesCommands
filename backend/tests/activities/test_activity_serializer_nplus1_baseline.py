# backend/tests/activities/test_activity_serializer_nplus1_baseline.py
"""
RED BASELINE — Sprint Timeout (vague 2) / Fil sérialiseur activité (MESURE, aucun fix).

Two endpoints share ONE serializer, `ActivityListSerializer`
(app_modules/activities/serializers.py:215), and therefore ONE N+1:

  - GET /module-activities/            -> ActivityViewSet.list (views/views.py:268),
        serializer chosen by get_serializer_class (views.py:154-162)
  - GET /module-activities/by-account/ -> ActivityViewSet.by_account (views.py:1151),
        which hardcodes ActivityListSerializer (views.py:1201, :1212)

Both actions build the serializer's input via ActivityViewSet.get_queryset
(views.py:164-211). The `list` branch (:176-182) and the `else` branch used by
by_account (:199-206) select_related only account/owner/decision_step(/cycle) —
they do NOT prefetch `contacts`, do NOT select_related `campaign_contact`, and
do NOT annotate `_contacts_count`. So the serializer's method fields fall back
to per-row DB access, once for every activity on the page:

  - get_contacts_count (serializers.py:324-327)  -> obj.contacts.count()          (+1/row)
  - get_contacts       (serializers.py:329-347)  -> obj.contacts.all()            (+1/row)
        and, inside the loop, c.standard_department per contact                    (+1/contact)
        (get_contacts was recently enriched with phone_number + linkedin —
         serializers.py:340-341 — on this already-unoptimized path)
  - get_campaign_contact_status (serializers.py:359-368) -> obj.campaign_contact  (+1/row when campaign-linked)

=> ~ (3 + K) extra queries per serialized row (K = contacts on the activity).

This module GRAVES the starting numbers: it measures the query count of BOTH
real endpoints at two page sizes and proves the slope (queries grow with the
number of activities), and it isolates in the SQL trace the per-activity
repeated queries (contacts / standard_departments / campaign_contact). No fix.

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

# Volume: a full page of activities, each carrying contacts (with a
# standard_department, so get_contacts' per-contact FK access fires) AND a
# campaign_contact (so get_campaign_contact_status fires) — the realistic
# campaign-navigation case behind the 4773ms. Two shared contacts + one shared
# campaign_contact are enough: the queryset prefetches none of them, so each
# activity re-hits them per row regardless of sharing.
N_ACTIVITIES = 60
CONTACTS_PER_ACTIVITY = 2
PAGE_SMALL = 10
PAGE_LARGE = 20


@pytest.fixture
def activity_dataset(db, account, user_a, client_account_a):
    """N activities on one account, each with CONTACTS_PER_ACTIVITY contacts
    (each with a standard_department) and a shared campaign_contact."""
    ca = client_account_a
    # StandardDepartment is a pre-seeded controlled list with a unique name.
    dept, _ = StandardDepartment.objects.get_or_create(
        name=StandardDepartment.DepartmentChoices.SALES
    )

    # Shared M2M contacts (each with a standard_department FK).
    shared_contacts = []
    for i in range(CONTACTS_PER_ACTIVITY):
        c = Contact(
            account=account,
            first_name=f"C{i}",
            last_name="Doe",
            email=f"c{i}@acme.test",
            phone_number="+14155550123",
            linkedin="https://linkedin.com/in/c",
            standard_department=dept,
        )
        c.save(user=user_a, client_id=ca.id)
        shared_contacts.append(c)

    # Campaign chain -> one shared CampaignContact set on every activity, so
    # get_campaign_contact_status fires per row (campaign_contact not
    # select_related on the list/by_account path).
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
    isolates the serializer N+1 (not the DEBUG-only client-scope double COUNT)."""
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
    # Both endpoints wrap results under data.results.
    return len(resp.data["data"]["results"])


def _per_activity_breakdown(captured):
    """Count the repeated per-activity queries in a trace, by table."""
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
class TestActivitySerializerNPlus1RedBaseline:

    def test_list_query_count_grows_with_activities(self, activity_dataset, authed_api_a):
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
        print("RED BASELINE — GET /module-activities/ (ActivityListSerializer N+1)")
        print("=" * 68)
        print(f"  page_size={PAGE_SMALL:>2}  rows={rows_s:>2}  queries={q_s}")
        print(f"  page_size={PAGE_LARGE:>2}  rows={rows_l:>2}  queries={q_l}")
        print(f"  slope (extra queries per activity)    : {slope}")
        print(f"  --- per-activity repeats in page={PAGE_LARGE} trace ---")
        print(f"  module_contacts queries (count + all) : {contacts_q}")
        print(f"  standard_departments queries          : {deps_q}")
        print(f"  campaign_contact queries              : {cc_q}")
        print("=" * 68 + "\n")

        assert rows_s == PAGE_SMALL and rows_l == PAGE_LARGE
        # THE RED: query count clearly scales with the number of activities.
        assert slope >= 4.0, f"expected a strong per-activity slope, got {slope}"
        assert q_s > 3 * PAGE_SMALL, "list is not exhibiting an N+1 (too few queries)"
        # The per-activity repeats scale with the page (isolated in the trace).
        assert deps_q == rows_l * CONTACTS_PER_ACTIVITY  # 1 dept fetch / contact / row
        assert cc_q >= rows_l                            # >=1 campaign_contact fetch / row

    def test_by_account_shares_the_same_nplus1(self, activity_dataset, authed_api_a):
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
        print("RED BASELINE — GET /module-activities/by-account/ (SAME serializer)")
        print("=" * 68)
        print(f"  page_size={PAGE_SMALL:>2}  rows={rows_s:>2}  queries={q_s}")
        print(f"  page_size={PAGE_LARGE:>2}  rows={rows_l:>2}  queries={q_l}")
        print(f"  slope (extra queries per activity)    : {slope}")
        print(f"  standard_departments queries          : {deps_q}")
        print(f"  campaign_contact queries              : {cc_q}")
        print("=" * 68 + "\n")

        assert rows_s == PAGE_SMALL and rows_l == PAGE_LARGE
        # Same N+1 signature as the plain list -> shared root cause.
        assert slope >= 4.0, f"by_account slope too low: {slope}"
        assert deps_q == rows_l * CONTACTS_PER_ACTIVITY
        assert cc_q >= rows_l

    def test_both_endpoints_share_the_same_per_activity_slope(
        self, activity_dataset, authed_api_a
    ):
        """Prove the cause is COMMON: the two endpoints show the same
        per-activity slope (same serializer, same missing prefetches)."""
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
        print("RED BASELINE — shared cause: per-activity slope, both endpoints")
        print("=" * 68)
        print(f"  /module-activities/            slope : {list_slope}")
        print(f"  /module-activities/by-account/ slope : {by_slope}")
        print("=" * 68 + "\n")

        # Identical per-row serializer cost -> one common fix.
        assert list_slope == by_slope
