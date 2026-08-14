# backend/tests/end_users/test_client_accounts_count_equivalence.py
"""
BUSINESS EQUIVALENCE — Sprint Timeout / Fil accounts.

The N+1 fix moved users_count / organizations_count from per-row .count()
calls to queryset annotations (Count(..., distinct=True)). These tests lock
that the fix changed HOW the counts are computed, never WHAT they are:

- the annotated endpoint values equal the DIRECT reference counts the old
  code produced (active users only; all organizations);
- the counts are NOT inflated by a cartesian product — annotating two Count()
  over different relations WITHOUT distinct=True would make each equal
  active_users * organizations; we prove they stay separate (3 and 2, not 6);
- the is_active filter is respected: inactive users never counted;
- the annotated path (list/retrieve) and the fallback path (serializer on an
  un-annotated instance, e.g. the product_admin create path) return the SAME
  numbers.

DB: Postgres.
"""

import pytest
from django.urls import reverse

from end_users.models import ClientAccount, Organization, User
from end_users.serializers import ClientAccountSerializer

from tests.signals.conftest import (  # noqa: F401
    api,
    authenticate,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
    authed_api_a,
)

# A deliberately asymmetric mix so a cartesian product (active*orgs = 12) would
# be unmistakably different from the true values (active=3, orgs=4).
ACTIVE_USERS = 3
INACTIVE_USERS = 2
ORGS = 4


@pytest.fixture
def account_with_mix(db, client_account_a):
    ca = ClientAccount.objects.create(name="Mix Co", is_b2b=True, max_users=20)
    for u in range(ACTIVE_USERS):
        User.objects.create(email=f"act-{u}@mix.test", client_account=ca,
                            role=None, is_active=True)
    for u in range(INACTIVE_USERS):
        User.objects.create(email=f"ina-{u}@mix.test", client_account=ca,
                            role=None, is_active=False)
    for o in range(ORGS):
        Organization.objects.create(name=f"MixOrg-{o}", client_account=ca)
    return ca


def _endpoint_row(authed_api_a, account_id):
    url = reverse('client:client-account-list')
    resp = authed_api_a.get(f"{url}?page_size=100")
    assert resp.status_code == 200, resp.content
    for row in resp.data["results"]:
        if row["id"] == str(account_id):
            return row
    raise AssertionError("account not found in list response")


@pytest.mark.django_db
class TestCountEquivalence:

    def test_annotated_values_equal_direct_reference_counts(self, account_with_mix,
                                                            authed_api_a):
        ca = account_with_mix
        # DIRECT reference = exactly what the old per-row code computed.
        ref_users = User.objects.filter(client_account=ca, is_active=True).count()
        ref_orgs = Organization.objects.filter(client_account=ca).count()

        row = _endpoint_row(authed_api_a, ca.id)
        assert row["users_count"] == ref_users
        assert row["organizations_count"] == ref_orgs
        # Sanity: the reference itself is the realistic, non-trivial mix.
        assert ref_users == ACTIVE_USERS
        assert ref_orgs == ORGS

    def test_no_cartesian_product_inflation(self, account_with_mix, authed_api_a):
        """Without distinct=True the two Count()s would inflate to
        active_users * organizations. Prove they don't."""
        ca = account_with_mix
        row = _endpoint_row(authed_api_a, ca.id)
        assert row["users_count"] == ACTIVE_USERS          # 3, not 3*4=12
        assert row["organizations_count"] == ORGS          # 4, not 4*3=12
        assert row["users_count"] != ACTIVE_USERS * ORGS
        assert row["organizations_count"] != ACTIVE_USERS * ORGS

    def test_inactive_users_never_counted(self, account_with_mix, authed_api_a):
        """The is_active filter survives the move to an annotation."""
        ca = account_with_mix
        row = _endpoint_row(authed_api_a, ca.id)
        total_users = User.objects.filter(client_account=ca).count()
        assert total_users == ACTIVE_USERS + INACTIVE_USERS      # 5 total
        assert row["users_count"] == ACTIVE_USERS                # only the 3 active

    def test_annotated_path_matches_fallback_path(self, account_with_mix,
                                                  authed_api_a):
        """The annotated list/retrieve path and the un-annotated fallback path
        (serializer on a plain instance, as in the product_admin create
        response) return identical numbers."""
        ca = account_with_mix
        annotated_row = _endpoint_row(authed_api_a, ca.id)

        # Plain instance — no annotation attributes: exercises the .count()
        # fallback in get_users_count / get_organizations_count.
        plain = ClientAccount.objects.get(id=ca.id)
        assert not hasattr(plain, 'users_count_annotated')
        fallback = ClientAccountSerializer(plain).data

        assert fallback["users_count"] == annotated_row["users_count"]
        assert fallback["organizations_count"] == annotated_row["organizations_count"]
