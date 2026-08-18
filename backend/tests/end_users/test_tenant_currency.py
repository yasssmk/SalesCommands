# backend/tests/end_users/test_tenant_currency.py
"""
Tenant currency — one currency per tenant, attached to the figures it explains.

A tenant's money is all in ONE currency: there is no conversion, no FX, no
per-deal or per-product currency, and nothing ever sums across currencies
(everything a tenant owns shares its own). Amounts stay bare numbers; this is
the CONTEXT that lets a caller render 60000 as "60000 EUR".

The field already existed on the tenant as ``default_quota_currency``
(end_users/models/client_account.py, migration 0002) with a single reader on
the legacy quota payload. It is renamed to ``currency`` — the fact is the
tenant's, not the quota's — rather than adding a second currency column beside
it. Data is preserved by the RenameField migration.

Surfaced in three places, each resolved from the tenant at read time so the code
never copies a currency onto a deal:
  * ClientAccountSerializer — the tenant's own payload;
  * DealProductListSerializer — beside a line's ``line_total``;
  * the BI KPI envelope — beside the value of a MONETARY KPI (and only those).

DB: Postgres.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.cache import cache

from app_modules.accounts.models import CompanyAccount
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.decision_cycles import dc_pipeline_value
from app_modules.bi.presentation import serialize_result
from app_modules.decision_cycles.models import DealProduct, DecisionCycle
from app_modules.decision_cycles.serializers import DealProductListSerializer
from app_modules.product_catalog.models import ProductCatalog
from end_users.models import ClientAccount
from end_users.serializers.client_account_serializers import ClientAccountSerializer
from permissions.compat import AuthContext


pytestmark = pytest.mark.django_db


TODAY = date.today()


# ---------------------------------------------------------------------------
# factories
# ---------------------------------------------------------------------------

def _tenant(name, currency=None):
    kwargs = {'name': name}
    if currency is not None:
        kwargs['currency'] = currency
    return ClientAccount.objects.create(**kwargs)


def _user(email, ca):
    from end_users.models import User, UserRole
    role = UserRole.objects.create(
        client_account=ca, name=f'Ind-{email}', is_individual=True,
        read=True, write=True, modify=True, can_delete=True,
    )
    return User.objects.create(email=email, client_account=ca, role=role,
                               is_active=True)


def _priced_cycle(owner, ca, amount):
    account = CompanyAccount(company_name=f'Acc-{owner.email}',
                             has_buying_decision=True, account_owner=owner)
    account.save(user=owner, client_id=ca.id)

    cycle = DecisionCycle(account=account, owner=owner, name='dc')
    cycle.save(user=owner, client_id=ca.id)

    product = ProductCatalog(name=f'P-{owner.email}')
    product.save(user=owner, client_id=ca.id)
    line = DealProduct(decision_cycle=cycle, product_catalog_entry=product,
                       quantity=1, unit_price=amount)
    line.save(user=owner, client_id=ca.id)
    return cycle, line


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpis(db):
    load_all()
    yield dc_pipeline_value
    registry.clear()


# ===========================================================================
# The field on the tenant
# ===========================================================================

class TestTenantCurrencyField:

    def test_a_new_tenant_defaults_to_eur(self):
        assert _tenant('Defaulting Co').currency == 'EUR'

    @pytest.mark.parametrize('code', ['EUR', 'USD', 'GBP'])
    def test_a_supported_code_is_accepted(self, code):
        tenant = _tenant(f'Co-{code}', currency=code)
        tenant.full_clean()                       # choices validation runs

        tenant.refresh_from_db()
        assert tenant.currency == code

    def test_an_unsupported_code_is_rejected(self):
        tenant = _tenant('Bad Co', currency='XXX')

        with pytest.raises(ValidationError) as excinfo:
            tenant.full_clean()

        assert 'currency' in excinfo.value.message_dict

    def test_one_currency_per_tenant_not_per_deal(self):
        """The column lives on the tenant and nowhere else — no deal, line or
        product carries its own."""
        assert 'currency' in {f.name for f in ClientAccount._meta.concrete_fields}
        for model in (DecisionCycle, DealProduct, ProductCatalog):
            names = {f.name for f in model._meta.concrete_fields}
            assert not {n for n in names if 'currency' in n}, model.__name__


# ===========================================================================
# Surfaced beside the figures
# ===========================================================================

class TestSurfacedOnTheTenantPayload:

    def test_the_tenant_payload_carries_its_currency(self):
        tenant = _tenant('Serialized Co', currency='GBP')

        assert ClientAccountSerializer(tenant).data['currency'] == 'GBP'


class TestSurfacedOnADealLine:

    def test_a_line_carries_its_tenant_currency(self):
        tenant = _tenant('Line Co', currency='USD')
        owner = _user('line@usd.test', tenant)
        _cycle, line = _priced_cycle(owner, tenant, Decimal('60000'))

        data = DealProductListSerializer(line).data

        assert Decimal(data['line_total']) == Decimal('60000')
        assert data['currency'] == 'USD'

    def test_two_tenants_each_get_their_own(self):
        """Resolved per tenant, not hardcoded."""
        eur_tenant = _tenant('EUR Co', currency='EUR')
        usd_tenant = _tenant('USD Co', currency='USD')
        _c1, eur_line = _priced_cycle(_user('a@eur.test', eur_tenant),
                                      eur_tenant, Decimal('1000'))
        _c2, usd_line = _priced_cycle(_user('a@usd.test', usd_tenant),
                                      usd_tenant, Decimal('1000'))

        assert DealProductListSerializer(eur_line).data['currency'] == 'EUR'
        assert DealProductListSerializer(usd_line).data['currency'] == 'USD'


class TestSurfacedOnMonetaryKpis:

    def _pipeline_payload(self, kpi, tenant, owner):
        auth_ctx = AuthContext(user_id=str(owner.id), client_id=str(tenant.id),
                               is_authenticated=True)
        result = cached_run(kpi, auth_ctx, scope='mine', period=None)
        return serialize_result(result, kpi, client_id=auth_ctx.client_id)

    def test_a_money_kpi_carries_the_tenant_currency(self, kpis):
        tenant = _tenant('KPI Co', currency='GBP')
        owner = _user('kpi@gbp.test', tenant)
        _priced_cycle(owner, tenant, Decimal('60000'))

        payload = self._pipeline_payload(kpis, tenant, owner)

        assert float(payload['value']) == 60000.0
        assert payload['currency'] == 'GBP'

    def test_two_tenants_each_get_their_own(self, kpis):
        eur_tenant = _tenant('KPI EUR Co', currency='EUR')
        usd_tenant = _tenant('KPI USD Co', currency='USD')
        eur_owner = _user('kpi@eur.test', eur_tenant)
        usd_owner = _user('kpi2@usd.test', usd_tenant)
        _priced_cycle(eur_owner, eur_tenant, Decimal('1000'))
        _priced_cycle(usd_owner, usd_tenant, Decimal('1000'))

        assert self._pipeline_payload(kpis, eur_tenant, eur_owner)['currency'] == 'EUR'
        assert self._pipeline_payload(kpis, usd_tenant, usd_owner)['currency'] == 'USD'

    def test_a_non_monetary_kpi_carries_no_currency(self, kpis):
        """Only figures that ARE money get the context — a count would be
        nonsense in EUR."""
        from app_modules.bi.definitions.decision_cycles import dc_cycles_by_outcome

        tenant = _tenant('Counting Co', currency='EUR')
        owner = _user('count@eur.test', tenant)
        _priced_cycle(owner, tenant, Decimal('1000'))
        auth_ctx = AuthContext(user_id=str(owner.id), client_id=str(tenant.id),
                               is_authenticated=True)

        result = cached_run(dc_cycles_by_outcome, auth_ctx, scope='mine', period=None)
        payload = serialize_result(result, dc_cycles_by_outcome,
                                   client_id=auth_ctx.client_id)

        assert payload.get('currency') is None


# ===========================================================================
# No conversion — the numbers are untouched
# ===========================================================================

class TestNoConversion:

    def test_the_same_amount_serialises_identically_under_any_currency(self):
        eur_tenant = _tenant('No FX EUR', currency='EUR')
        usd_tenant = _tenant('No FX USD', currency='USD')
        _c1, eur_line = _priced_cycle(_user('fx@eur.test', eur_tenant),
                                      eur_tenant, Decimal('60000'))
        _c2, usd_line = _priced_cycle(_user('fx@usd.test', usd_tenant),
                                      usd_tenant, Decimal('60000'))

        eur = DealProductListSerializer(eur_line).data
        usd = DealProductListSerializer(usd_line).data

        assert Decimal(eur['line_total']) == Decimal(usd['line_total'])
        assert eur['currency'] != usd['currency']
