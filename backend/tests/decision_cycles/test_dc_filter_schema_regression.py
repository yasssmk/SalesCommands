"""
Guards around the removed DecisionStep.status column.

1. StepMinimalSerializer still listed the dropped `status` field — the last
   residual reference to the column that 4b missed. It is unused, so it emits no
   SQL, but instantiating it raises ImproperlyConfigured; the test below builds
   it (red before the field is dropped, green after).

2. Cross-coverage of the whole filterset against the REAL (post-0019) schema:
   every facet under owner_scope=team must return 200 with no SQL error. This is
   the coverage that was missing when the production 500 "column
   decision_steps.status does not exist" was reported — no test combined a
   filter facet with owner_scope=team on the post-0019 schema, so a latent
   reader could have survived undetected. It proves none does.
"""

import pytest

from django.utils import timezone
from rest_framework import status

from app_modules.accounts.models import CompanyAccount
from app_modules.decision_cycles.models import DealProduct, DecisionCycle, DecisionStep
from app_modules.decision_cycles.constants import PIPELINE_STEPS_CONFIG
from app_modules.decision_cycles.serializers import StepMinimalSerializer
from app_modules.product_catalog.models import ProductCatalog


LIST_URL = '/decision_cycles/'
TODAY = timezone.now().date()


# =============================================================================
# RESIDUAL REFERENCE — StepMinimalSerializer must not list the dropped field
# =============================================================================

def test_step_minimal_serializer_builds_without_the_dropped_status_field():
    """
    StepMinimalSerializer is a ModelSerializer; binding its fields against the
    post-0019 DecisionStep model raises ImproperlyConfigured while `status` is
    still listed. Accessing `.fields` forces the binding.
    """
    fields = StepMinimalSerializer().fields
    assert 'status' not in fields
    assert set(fields).issuperset({'id', 'name', 'stage'})


def _rows(resp):
    body = resp.json()['data']
    results = body.get('results', body)
    if isinstance(results, dict):
        results = results.get('results', [])
    return results


# =============================================================================
# ORG — a manager over a team with one member (AE), so owner_scope=team resolves
# =============================================================================

def _user(email, ca, role, **extra):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True, **extra)


def _team(name, ca, manager=None):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca, manager=manager)


def _account(owner, ca, name):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _cycle(owner, ca, account, name, **kw):
    c = DecisionCycle(account=account, owner=owner, name=name, **kw)
    c.save(user=owner, client_id=ca.id)
    return c


def _steps(cycle, owner, ca):
    previous = None
    for cfg in PIPELINE_STEPS_CONFIG:
        s = DecisionStep(
            cycle=cycle, name=cfg['step'].label, stage=cfg['step'].value,
            order=cfg['order'], previous_step=previous, expected_end=None,
        )
        s.save(user=owner, client_id=ca.id)
        previous = s


@pytest.fixture
def org(db, client_account_a, role_individual_a):
    ca = client_account_a
    mgr = _user('mgr-schema@a.test', ca, role_individual_a)
    emea = _team('EMEA-schema', ca, manager=mgr)
    ae = _user('ae-schema@a.test', ca, role_individual_a, team=emea)
    acc = _account(ae, ca, 'AE Portfolio schema')
    cycle = _cycle(ae, ca, acc, 'AE deal schema')
    _steps(cycle, ae, ca)
    product = ProductCatalog(name='Schema Widget', description='x', default_unit_price=1000)
    product.save(user=ae, client_id=ca.id)
    DealProduct.objects.create(
        decision_cycle=cycle, product_catalog_entry=product, quantity=1, client_id=ca.id,
    )
    return {
        'ca': ca, 'mgr': mgr, 'emea': emea, 'ae': ae,
        'account': acc, 'cycle': cycle, 'product': product,
    }


# =============================================================================
# THE REPRO — product filter under owner_scope=team
# =============================================================================

@pytest.mark.django_db
def test_product_filter_with_team_scope_does_not_500(org, api, authenticate):
    """
    /decision_cycles/?product=<uuid>&owner_scope=team must return 200, not a
    500 from `column decision_steps.status does not exist`.
    """
    authenticate(api, org['mgr'], org['ca'].id)
    resp = api.get(LIST_URL, {
        'product': str(org['product'].id),
        'owner_scope': 'team',
    })
    assert resp.status_code == status.HTTP_200_OK, resp.content
    # the AE's cycle carries the product and is in the manager's team scope
    assert str(org['cycle'].id) in {r['id'] for r in _rows(resp)}


# =============================================================================
# CROSS-COVERAGE — every facet under owner_scope=team returns 200, no SQL error
# =============================================================================

@pytest.mark.django_db
def test_every_facet_with_team_scope_returns_200(org, api, authenticate):
    authenticate(api, org['mgr'], org['ca'].id)

    facets = {
        'account': str(org['account'].id),
        'owner': str(org['ae'].id),
        'team': str(org['emea'].id),
        'contact': '00000000-0000-0000-0000-000000000000',
        'source_campaign': '00000000-0000-0000-0000-000000000000',
        'product': str(org['product'].id),
        'status': 'IN_PROGRESS',   # unified derived-state facet
    }

    for facet, value in facets.items():
        resp = api.get(LIST_URL, {facet: value, 'owner_scope': 'team'})
        assert resp.status_code == status.HTTP_200_OK, (
            f"facet {facet!r} raised {resp.status_code}: {resp.content}"
        )
