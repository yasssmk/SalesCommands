# backend/tests/end_users/test_client_accounts_list_nplus1_baseline.py
"""
RE-MEASURE (GREEN) — Sprint Timeout / Fil accounts (re-pointed by TD-322).

The client-account serializer used to be N+1: get_users_count did
obj.users.filter(is_active=True).count(), reopening a fresh queryset per
serialized row (1 COUNT / row) and wasting the users prefetch. The graved RED
baseline (commit b8267608, on the former list endpoint):

    page_size=10 -> 14 queries
    page_size=20 -> 24 queries
    slope        -> 1 query / row  (users_count)

The fix moves both counts into the main query as annotations on the view's
queryset (views/client_account_viewset.py):

    users_count_annotated         = Count('users', filter=Q(users__is_active=True), distinct=True)
    organizations_count_annotated = Count('organizations', distinct=True)

and the serializer reads those annotations (with a direct-count fallback for
un-annotated callers).

Since TD-322 the endpoint is read-only on the requester's OWN tenant: the list
is gone, so the per-row slope no longer exists. What this module now GUARDS on
GET /client/client-accounts/<own id>/ and .../seats/:

- the query count does NOT grow with the tenant's volume (a tenant with many
  users and organizations costs exactly as many queries as a small one);
- zero separate users / organizations COUNT queries and zero prefetch
  queries: the counts come from the annotations of the main query;
- the counted values are the expected, realistic numbers.

If the annotation is reverted to a per-serialization .count(), separate COUNT
queries reappear and these tests fail (non-vacuity).

DB: Postgres.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from end_users.models import Organization, User

# Fixtures: authenticated DRF client on the seed tenant (Tenant A Co).
from tests.signals.conftest import (  # noqa: F401
    api,
    authenticate,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
    authed_api_a,
)

# Volume added to the requester's tenant for the "large" measurement: several
# ACTIVE users (+ inactive ones, so the is_active filter is non-trivial) and
# multiple organizations, so both counted values are realistic and non-zero.
EXTRA_ACTIVE_USERS = 12
EXTRA_INACTIVE_USERS = 4
EXTRA_ORGS = 7


def _grow_tenant(ca):
    for u in range(EXTRA_ACTIVE_USERS):
        User.objects.create(email=f"active-{u}@acct.test", client_account=ca,
                            role=None, is_active=True)
    for u in range(EXTRA_INACTIVE_USERS):
        User.objects.create(email=f"inactive-{u}@acct.test", client_account=ca,
                            role=None, is_active=False)
    for o in range(EXTRA_ORGS):
        Organization.objects.create(name=f"Org-{o}", client_account=ca)


def _get(authed_api_a, route, pk):
    resp = authed_api_a.get(reverse(route, kwargs={'pk': pk}))
    assert resp.status_code == 200, resp.content
    return resp


def _classify(captured):
    """Split a captured SQL trace into separate users / organizations COUNT
    queries and prefetch queries, by table + shape. The main query reads
    FROM "client_accounts" (annotations are joins on it), so it is never
    classified here."""
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


ROUTES = ('client:client-account-detail', 'client:client-account-seats')


@pytest.mark.django_db
class TestClientAccountQueriesBounded:

    @pytest.mark.parametrize('route', ROUTES)
    def test_query_count_independent_of_tenant_volume(
        self, route, client_account_a, authed_api_a
    ):
        """A big tenant costs exactly as many queries as a small one."""
        with CaptureQueriesContext(connection) as cap_small:
            _get(authed_api_a, route, client_account_a.id)
        q_small = len(cap_small.captured_queries)

        _grow_tenant(client_account_a)

        with CaptureQueriesContext(connection) as cap_large:
            _get(authed_api_a, route, client_account_a.id)
        q_large = len(cap_large.captured_queries)

        print(f"\n{route}: small tenant={q_small} queries, "
              f"large tenant={q_large} queries")
        assert q_large == q_small, (
            f"query count grows with the tenant's volume: {q_small} vs {q_large}"
        )

    @pytest.mark.parametrize('route', ROUTES)
    def test_no_separate_count_or_prefetch_queries(
        self, route, client_account_a, authed_api_a
    ):
        """No separate users / organizations COUNT query and no prefetch:
        the counts come from the main query's annotations."""
        _grow_tenant(client_account_a)
        with CaptureQueriesContext(connection) as cap:
            _get(authed_api_a, route, client_account_a.id)
        users_count, orgs_count, users_prefetch, orgs_prefetch = _classify(
            cap.captured_queries
        )
        assert len(users_count) == 0, "a separate users COUNT survived"
        assert len(orgs_count) == 0, "a separate organizations COUNT survived"
        assert len(users_prefetch) == 0, "users prefetch not removed"
        assert len(orgs_prefetch) == 0, "organizations prefetch not removed"

    def test_counted_values_are_the_expected_realistic_numbers(
        self, client_account_a, authed_api_a
    ):
        """The counts are non-trivial AND not inflated by a cartesian product:
        active users only (the requester + the extra ones), all organizations."""
        _grow_tenant(client_account_a)
        expected_active = 1 + EXTRA_ACTIVE_USERS  # user_a is active

        detail = _get(authed_api_a, ROUTES[0], client_account_a.id).data
        assert detail["users_count"] == expected_active
        assert detail["organizations_count"] == EXTRA_ORGS

        seats = _get(authed_api_a, ROUTES[1], client_account_a.id).data["data"]
        assert seats["seats_used"] == expected_active
        assert seats["seats"] == client_account_a.max_users
        assert seats["seats_left"] == max(0, client_account_a.max_users - expected_active)
