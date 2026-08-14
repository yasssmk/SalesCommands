# backend/tests/end_users/test_client_accounts_list_nplus1_baseline.py
"""
RE-MEASURE (GREEN) — Sprint Timeout / Fil accounts.

GET /client/client-accounts/ (ClientAccountViewSet.list) used to be N+1 on
the serializer: get_users_count did obj.users.filter(is_active=True).count(),
reopening a fresh queryset per row (1 COUNT / row) and wasting the users
prefetch. The graved RED baseline (commit b8267608):

    page_size=10 -> 14 queries
    page_size=20 -> 24 queries
    slope        -> 1 query / row  (users_count)

The fix moves both counts into the main query as annotations on the
list/retrieve queryset (views/client_account_viewset.py):

    users_count_annotated         = Count('users', filter=Q(users__is_active=True), distinct=True)
    organizations_count_annotated = Count('organizations', distinct=True)

and the serializer reads those annotations (with a direct-count fallback for
un-annotated callers). The per-row COUNTs and both prefetch queries are gone.

This module now GUARDS the fixed behaviour: the query count is FLAT across
page sizes (slope 0), with zero per-row users/organizations COUNT queries and
zero prefetch queries. If the annotation is reverted to a per-row .count(),
the slope climbs back to 1 and these tests fail (non-vacuity).

DB: Postgres.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from end_users.models import ClientAccount, Organization, User

# Fixtures: authenticated DRF client + one seed tenant (Tenant A Co).
from tests.signals.conftest import (  # noqa: F401
    api,
    authenticate,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
    authed_api_a,
)

# Volume: enough accounts to fully fill a page of 20 (plus the seed tenant),
# each carrying several ACTIVE users (+ an inactive one, so the is_active
# filter is non-trivial) and multiple organizations, so both counted values
# are realistic and non-zero.
N_ACCOUNTS = 24
ACTIVE_USERS_PER = 3
INACTIVE_USERS_PER = 1
ORGS_PER = 2

PAGE_SMALL = 10
PAGE_LARGE = 20


@pytest.fixture
def many_accounts(db, client_account_a):
    """Create N_ACCOUNTS client accounts, each with active + inactive users
    and organizations. Returns the list of created ClientAccount rows."""
    accounts = []
    for i in range(N_ACCOUNTS):
        ca = ClientAccount.objects.create(
            name=f"Acct-{i:02d}",
            is_b2b=True,
            max_users=20,
        )
        for u in range(ACTIVE_USERS_PER):
            User.objects.create(
                email=f"active-{i:02d}-{u}@acct.test",
                client_account=ca,
                role=None,
                is_active=True,
            )
        for u in range(INACTIVE_USERS_PER):
            User.objects.create(
                email=f"inactive-{i:02d}-{u}@acct.test",
                client_account=ca,
                role=None,
                is_active=False,
            )
        for o in range(ORGS_PER):
            Organization.objects.create(name=f"Org-{i:02d}-{o}", client_account=ca)
        accounts.append(ca)
    return accounts


def _list(authed_api_a, page_size):
    url = reverse('client:client-account-list')
    resp = authed_api_a.get(f"{url}?page_size={page_size}")
    assert resp.status_code == 200, resp.content
    return resp


def _classify(captured):
    """Split a captured SQL trace into per-row COUNT queries and prefetch
    queries, by table + shape."""
    users_count, orgs_count, users_prefetch, orgs_prefetch = [], [], [], []
    for q in captured:
        sql = q["sql"].lower()
        is_count = "count(" in sql
        if 'from "users"' in sql:
            if is_count and "is_active" in sql:
                users_count.append(sql)
            elif not is_count and " in (" in sql:
                users_prefetch.append(sql)
        elif 'from "organizations"' in sql:
            if is_count:
                orgs_count.append(sql)
            elif " in (" in sql:
                orgs_prefetch.append(sql)
    return users_count, orgs_count, users_prefetch, orgs_prefetch


@pytest.mark.django_db
class TestClientAccountsListBounded:

    def test_query_count_is_flat_across_page_sizes(self, many_accounts, authed_api_a):
        """The list query count no longer grows with the page: slope 0.
        (RED baseline b8267608 was +1 query/row.)"""
        with CaptureQueriesContext(connection) as cap_small:
            resp_small = _list(authed_api_a, PAGE_SMALL)
        q_small = len(cap_small.captured_queries)
        rows_small = len(resp_small.data["results"])

        with CaptureQueriesContext(connection) as cap_large:
            resp_large = _list(authed_api_a, PAGE_LARGE)
        q_large = len(cap_large.captured_queries)
        rows_large = len(resp_large.data["results"])

        slope = (q_large - q_small) / (rows_large - rows_small)

        print("\n" + "=" * 66)
        print("GREEN RE-MEASURE — GET /client/client-accounts/ (annotated)")
        print("=" * 66)
        print(f"  RED baseline (b8267608): page10=14  page20=24  slope=1/row")
        print(f"  page_size={PAGE_SMALL:>2}  rows={rows_small:>2}  queries={q_small}")
        print(f"  page_size={PAGE_LARGE:>2}  rows={rows_large:>2}  queries={q_large}")
        print(f"  slope (extra queries per extra row) : {slope}")
        print("=" * 66 + "\n")

        # Full pages both times (volume is realistic).
        assert rows_small == PAGE_SMALL
        assert rows_large == PAGE_LARGE
        # THE GREEN: query count is independent of the number of rows.
        assert q_large == q_small, (
            f"query count still scales with rows: {q_small} vs {q_large}"
        )
        assert slope == 0.0

    def test_no_per_row_count_or_prefetch_queries(self, many_accounts, authed_api_a):
        """No per-row users/organizations COUNT queries survive, and the two
        prefetch queries are gone (the counts come from annotations)."""
        with CaptureQueriesContext(connection) as cap:
            resp = _list(authed_api_a, PAGE_LARGE)
        rows = len(resp.data["results"])
        users_count, orgs_count, users_prefetch, orgs_prefetch = _classify(
            cap.captured_queries
        )

        print("\n" + "=" * 66)
        print("GREEN RE-MEASURE — no per-row COUNT, no prefetch (page of 20)")
        print("=" * 66)
        print(f"  rows returned                       : {rows}")
        print(f"  users_count   COUNT queries         : {len(users_count)}")
        print(f"  organizations COUNT queries         : {len(orgs_count)}")
        print(f"  users        prefetch queries       : {len(users_prefetch)}")
        print(f"  organizations prefetch queries      : {len(orgs_prefetch)}")
        print("=" * 66 + "\n")

        assert rows == PAGE_LARGE
        assert len(users_count) == 0, "a per-row users COUNT survived"
        assert len(orgs_count) == 0, "a per-row organizations COUNT survived"
        assert len(users_prefetch) == 0, "users prefetch not removed"
        assert len(orgs_prefetch) == 0, "organizations prefetch not removed"

    def test_counted_values_are_the_expected_realistic_numbers(
        self, many_accounts, authed_api_a
    ):
        """The counts are non-trivial AND not inflated by a cartesian product:
        each seeded account reports ACTIVE_USERS_PER active users (inactive
        excluded) and ORGS_PER organizations — 3 and 2, not 6."""
        resp = _list(authed_api_a, PAGE_LARGE)
        by_id = {row["id"]: row for row in resp.data["results"]}
        seen = 0
        for ca in many_accounts:
            row = by_id.get(str(ca.id))
            if row is None:
                continue  # not on this page (ordering) — skip
            seen += 1
            assert row["users_count"] == ACTIVE_USERS_PER
            assert row["organizations_count"] == ORGS_PER
        assert seen >= 1, "no seeded account landed on the measured page"
