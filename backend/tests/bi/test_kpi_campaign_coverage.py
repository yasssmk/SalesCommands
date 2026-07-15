# backend/tests/bi/test_kpi_campaign_coverage.py
"""
KPI 3 — Campaign coverage = still-active targets / total.

Primary = CampaignContact (active = status NOT in FINAL{COMPLETED,STOPPED});
secondary = CampaignAccount (same rule). Proves:
- both levels' active/total ratios,
- scope positive for owner AND executor, negative for a third user,
- query-bounded (assertNumQueries 3: campaign + 2 aggregates).
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact
from app_modules.campaigns.constants import (
    CampaignAccountStatus, CampaignContactStatus,
)
from app_modules.campaigns.models.campaign import Campaign
from app_modules.campaigns.models.campaign_account import CampaignAccount
from app_modules.campaigns.models.campaign_contact import CampaignContact
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.campaigns import campaign_coverage
from app_modules.bi.signals import cache_invalidation as ci
from permissions.compat import AuthContext


TODAY = timezone.now().date()


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_campaign(owner, ca, executor=None):
    c = Campaign(name='Camp', campaign_type='OUTBOUND', owner=owner, executor=executor,
                 planned_start_date=TODAY, planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_ca(campaign, account, ca, status=CampaignAccountStatus.PENDING):
    x = CampaignAccount(campaign=campaign, account=account, status=status)
    x.save(user=campaign.owner, client_id=ca.id)
    return x


def _mk_contact(account, owner, ca):
    ct = Contact(account=account, first_name='C', last_name='X')
    ct.save(user=owner, client_id=ca.id)
    return ct


def _mk_cc(campaign_account, contact, ca, status):
    x = CampaignContact(campaign_account=campaign_account, contact=contact, status=status)
    x.save(user=campaign_account.campaign.owner, client_id=ca.id)
    return x


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpi(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield campaign_coverage
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def owner(db, client_account_a, role_individual_a):
    return _mk_user('owner@a.test', client_account_a, role_individual_a)


@pytest.fixture
def executor(db, client_account_a, role_individual_a):
    return _mk_user('exec@a.test', client_account_a, role_individual_a)


@pytest.fixture
def outsider(db, client_account_a, role_individual_a):
    return _mk_user('outsider@a.test', client_account_a, role_individual_a)


@pytest.fixture
def campaign(db, client_account_a, owner, executor):
    """4 accounts (2 active / 2 final) and 5 contacts (3 active / 2 final).
    Account statuses are forced via .update() to decouple from the
    CampaignContact auto-complete signal."""
    c = _mk_campaign(owner, client_account_a, executor=executor)
    accts = [_mk_account(f'A{i}', owner, client_account_a) for i in range(4)]
    cas = [_mk_ca(c, a, client_account_a) for a in accts]

    # contacts on the first two campaign-accounts
    active_statuses = [CampaignContactStatus.PENDING,
                       CampaignContactStatus.IN_PROGRESS,
                       CampaignContactStatus.CALLBACK_PENDING]
    # 3 active
    for st in active_statuses:
        _mk_cc(cas[0], _mk_contact(accts[0], owner, client_account_a), client_account_a, st)
    # 2 final
    _mk_cc(cas[1], _mk_contact(accts[1], owner, client_account_a),
           client_account_a, CampaignContactStatus.COMPLETED)
    _mk_cc(cas[1], _mk_contact(accts[1], owner, client_account_a),
           client_account_a, CampaignContactStatus.STOPPED)

    # Force account statuses: 2 active (PENDING), 2 final (COMPLETED/STOPPED).
    CampaignAccount.objects.filter(id__in=[cas[0].id, cas[1].id]).update(
        status=CampaignAccountStatus.PENDING)
    CampaignAccount.objects.filter(id=cas[2].id).update(
        status=CampaignAccountStatus.COMPLETED)
    CampaignAccount.objects.filter(id=cas[3].id).update(
        status=CampaignAccountStatus.STOPPED)
    return c


@pytest.mark.django_db
def test_registered(kpi):
    assert registry.get('campaign_coverage') is kpi
    assert kpi.compute_fn is not None


@pytest.mark.django_db
class TestValue:

    def test_both_levels(self, kpi, owner, client_account_a, campaign):
        res = cached_run(kpi, _ctx(owner, client_account_a), scope='mine',
                         params={'campaign_id': str(campaign.id)})
        # contacts: 3 active / 5 total = 60% (headline)
        assert res.value == 60.0
        assert res.meta['contacts'] == {'total': 5, 'active': 3, 'coverage_pct': 60.0}
        # accounts: 2 active / 4 total = 50%
        assert res.meta['accounts'] == {'total': 4, 'active': 2, 'coverage_pct': 50.0}


@pytest.mark.django_db
class TestScope:

    def test_owner_and_executor_see_outsider_not(
        self, kpi, owner, executor, outsider, client_account_a, campaign
    ):
        params = {'campaign_id': str(campaign.id)}
        assert cached_run(kpi, _ctx(owner, client_account_a), scope='mine',
                          params=params).value == 60.0
        assert cached_run(kpi, _ctx(executor, client_account_a), scope='mine',
                          params=params).value == 60.0
        res_out = cached_run(kpi, _ctx(outsider, client_account_a), scope='mine',
                             params=params)
        assert res_out.value is None
        assert res_out.meta['reason'] == 'out_of_scope_or_missing'

    def test_client_scope(self, kpi, outsider, client_account_a, campaign):
        assert cached_run(kpi, _ctx(outsider, client_account_a), scope='client',
                          params={'campaign_id': str(campaign.id)}).value == 60.0


@pytest.mark.django_db
class TestQueryBound:

    def test_bounded(self, kpi, owner, client_account_a, campaign,
                     django_assert_num_queries):
        # campaign fetch + contacts aggregate + accounts aggregate = 3
        with django_assert_num_queries(3):
            res = cached_run(kpi, _ctx(owner, client_account_a), scope='mine',
                             params={'campaign_id': str(campaign.id)})
            _ = res.value
