# backend/tests/end_users/test_client_accounts_list_nplus1_baseline.py
"""
RED BASELINE — Sprint Timeout / Fil accounts (MESURE, aucun fix).

GET /client/client-accounts/ (ClientAccountViewSet.list) is N+1 on the
serializer. The measured cost — NOT the assumed one — is exactly ONE extra
COUNT query per row, emitted by:

  - ClientAccountSerializer.get_users_count (serializers/client_account_serializers.py:24-26)
        obj.users.filter(is_active=True).count()

The `.filter(is_active=True)` clones a FRESH queryset whose result cache is
empty, so `.count()` issues its own aggregate SQL for every row AND bypasses
the users prefetch the viewset declared (views/client_account_viewset.py:39-40):

        Prefetch('users', queryset=User.objects.filter(is_active=True))

=> that prefetch is loaded once then WASTED.

By contrast, the sibling count does NOT N+1:

  - ClientAccountSerializer.get_organizations_count (:28-30)
        obj.organizations.count()

`.count()` on the un-refiltered related manager reuses the prefetched
`organizations` cache (Django returns len(cache), 0 queries). Verified
directly: users_count -> 1 query, organizations_count -> 0 queries.

So the honest red is: slope = 1 COUNT / row (users_count), a wasted users
prefetch, and a correctly-consumed organizations prefetch. The list action
is NOT cached, so it pays this on every call.

This module GRAVES those starting numbers: it measures the real endpoint at
two page sizes (10 and 20), proves the +1 query/row slope, and isolates in
the SQL trace the per-row users COUNT, the absent organizations COUNT, and
the two prefetch queries (one wasted, one consumed).

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
    """Split a captured SQL trace into the per-row COUNT queries and the
    prefetch queries, by table + shape."""
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
class TestClientAccountsListNPlus1RedBaseline:

    def test_query_count_grows_one_per_row(self, many_accounts, authed_api_a):
        """The list query count grows by exactly 1 per additional row — the
        signature of the single per-row COUNT (users_count) in the
        serializer. (organizations_count reuses its prefetch: no per-row SQL.)"""
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
        print("RED BASELINE — GET /client/client-accounts/ (serializer N+1)")
        print("=" * 66)
        print(f"  page_size={PAGE_SMALL:>2}  rows={rows_small:>2}  queries={q_small}")
        print(f"  page_size={PAGE_LARGE:>2}  rows={rows_large:>2}  queries={q_large}")
        print(f"  slope (extra queries per extra row) : {slope}")
        print(f"  => {slope:.0f} SQL / row = users_count "
              f"(organizations_count reuses its prefetch: 0/row)")
        print("=" * 66 + "\n")

        # Full pages both times (volume is realistic).
        assert rows_small == PAGE_SMALL
        assert rows_large == PAGE_LARGE
        # THE RED: exactly 1 extra query per extra row (the users_count COUNT).
        assert (q_large - q_small) == 1 * (rows_large - rows_small), (
            f"expected +1 query/row, got +{q_large - q_small} over "
            f"{rows_large - rows_small} rows"
        )
        assert slope == 1.0
        # Not a bounded-plan endpoint: the count scales with the page.
        assert q_small > PAGE_SMALL

    def test_users_count_nplus1_and_wasted_prefetch_vs_orgs_prefetch_reused(
        self, many_accounts, authed_api_a
    ):
        """On a page of PAGE_LARGE rows:
        - exactly PAGE_LARGE users-COUNT queries fire (1 per row) — the N+1;
        - ZERO organizations-COUNT queries fire — that count reuses its prefetch;
        - BOTH prefetch queries run: the users one is WASTED (reopened by the
          per-row filter), the organizations one is CONSUMED (feeds count)."""
        with CaptureQueriesContext(connection) as cap:
            resp = _list(authed_api_a, PAGE_LARGE)
        rows = len(resp.data["results"])
        users_count, orgs_count, users_prefetch, orgs_prefetch = _classify(
            cap.captured_queries
        )

        print("\n" + "=" * 66)
        print("RED BASELINE — 1 COUNT / row (users) + wasted users prefetch")
        print("=" * 66)
        print(f"  rows returned                            : {rows}")
        print(f"  users_count   COUNT queries (N+1, 1/row) : {len(users_count)}")
        print(f"  organizations COUNT queries (no N+1)     : {len(orgs_count)}")
        print(f"  users        prefetch (loaded, WASTED)   : {len(users_prefetch)}")
        print(f"  organizations prefetch (loaded, CONSUMED): {len(orgs_prefetch)}")
        print("=" * 66 + "\n")

        # One users COUNT per row — the N+1.
        assert len(users_count) == rows, "expected one users COUNT per row"
        # organizations_count does NOT N+1 (prefetch cache reused).
        assert len(orgs_count) == 0, "organizations_count should not emit per-row SQL"
        # Both prefetch queries the viewset declares DO run...
        assert len(users_prefetch) >= 1, "users prefetch query not observed"
        assert len(orgs_prefetch) >= 1, "organizations prefetch query not observed"
        # ...but the users prefetch is WASTED: the per-row COUNTs still fire.
        assert len(users_count) == rows

    def test_counted_values_are_the_expected_realistic_numbers(
        self, many_accounts, authed_api_a
    ):
        """The counts are non-trivial (so the N+1 is not measuring zeros):
        each seeded account reports ACTIVE_USERS_PER active users (inactive
        excluded) and ORGS_PER organizations."""
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
