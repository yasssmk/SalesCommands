# backend/tests/territories/test_account_counts_parity.py
"""
Parity: a territory's account count comes from the same evaluator as coverage.

commit 5a routes the workspace/batched account count through
AccountFilterService — the canonical filter core that
compute_territory_coverage_counts already uses for its denominator. This test
proves the two produce the same number for the same territory, so card counts
and coverage can never diverge.
"""

import pytest

from app_modules.accounts.models import CompanyAccount, AccountClassification
from app_modules.accounts.services.filter_service import AccountFilterService
from app_modules.territories.services.coverage import compute_territory_coverage_counts

from ._builders import mk_account, mk_territory


def _service_count(territory, ca):
    base = CompanyAccount.objects.filter(client_id=ca.id)
    return AccountFilterService.apply_filters(
        base, territory.filter_definition or {},
        client_id=ca.id, user=territory.owner,
    ).count()


@pytest.mark.django_db
def test_account_count_matches_coverage_denominator(user_a, client_account_a):
    terr = mk_territory(user_a, client_account_a, {'classification': 'SMB'})
    mk_account('SMB1', user_a, client_account_a)
    mk_account('SMB2', user_a, client_account_a)
    mk_account('SMB3', user_a, client_account_a)
    mk_account('ENT', user_a, client_account_a,
               classification=AccountClassification.ENTERPRISE)

    _, denominator = compute_territory_coverage_counts(
        terr, client_account_a.id, period=None,
    )
    assert _service_count(terr, client_account_a) == denominator == 3


@pytest.mark.django_db
def test_company_size_filter_is_evaluated(user_a, client_account_a):
    """company_size is handled by AccountFilterService but was ignored by the
    old inline workspace counter — proves the migration widens correctness."""
    terr = mk_territory(user_a, client_account_a, {'company_size': '50'})
    mk_account('S1', user_a, client_account_a, company_size='50')
    mk_account('S2', user_a, client_account_a, company_size='50')
    mk_account('S3', user_a, client_account_a, company_size='200')

    assert _service_count(terr, client_account_a) == 2
