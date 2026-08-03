# backend/tests/decision_cycles/test_dc_owner_is_creator.py
"""
A DecisionCycle must ALWAYS be owned by its creator, on every creation path.

Before the fix:
- the serializer path (POST /decision-cycles/) already set owner = creator;
- the inline-cycle service path (POST /activities/create-with-entities/) left
  owner = NULL.

These tests pin owner = creator on every path (never the account owner, never
null), plus a model-level safety net that backfills owner from created_by.
"""

import pytest
from types import SimpleNamespace

from end_users.models import User, UserRole, ClientAccount
from app_modules.accounts.models import CompanyAccount, AccountType
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.activities.services.activity_creation_service import (
    ActivityCreationService,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def ca(db):
    return ClientAccount.objects.create(name="Co", is_b2b=True, max_users=50)


@pytest.fixture
def role(db, ca):
    return UserRole.objects.filter(client_account=ca, is_individual=True).first() \
        or UserRole.objects.create(client_account=ca, name="Individual", is_individual=True)


@pytest.fixture
def creator(db, ca, role):
    return User.objects.create(
        email="creator@a.test", client_account=ca, role=role, is_active=True
    )


@pytest.fixture
def account_owner_user(db, ca, role):
    return User.objects.create(
        email="acct-owner@a.test", client_account=ca, role=role, is_active=True
    )


@pytest.fixture
def account(db, ca, account_owner_user):
    acc = CompanyAccount(
        company_name="Acct", type=AccountType.PROSPECT,
        has_buying_decision=True, account_owner=account_owner_user,
    )
    acc.save(user=account_owner_user, client_id=ca.id)
    return acc


# ---------------------------------------------------------------------------
# Path 2 — inline-cycle service (the campaign / follow-up path). THE bug.
# ---------------------------------------------------------------------------

def test_path2_create_cycle_owner_is_creator(ca, creator, account, account_owner_user):
    """The inline cycle is owned by the CREATOR, not the account owner, not null."""
    svc = ActivityCreationService(user=creator, client_id=ca.id)
    cycle = svc._create_cycle({'name': 'Inline DC'}, str(account.id))
    cycle.refresh_from_db()
    assert cycle.owner_id == creator.id
    assert cycle.owner_id != account_owner_user.id
    assert cycle.created_by_id == creator.id


def test_path2_create_with_entities_owner_is_creator(ca, creator, account, account_owner_user):
    """End-to-end: the person who clicks (creator) owns the inline cycle."""
    svc = ActivityCreationService(user=creator, client_id=ca.id)
    result = svc.create_with_entities(
        activity_data={
            'account_id': str(account.id),
            'title': 'Follow up',
            'activity_type': 'CALL',
        },
        inline_cycle={'name': 'From campaign'},
    )
    cycle = result['cycle']
    assert cycle is not None
    cycle.refresh_from_db()
    assert cycle.owner_id == creator.id
    assert cycle.owner_id != account_owner_user.id


# ---------------------------------------------------------------------------
# Path 1 — DecisionCycleCreateSerializer (POST /decision-cycles/). Already OK.
# ---------------------------------------------------------------------------

def test_path1_serializer_owner_is_creator(ca, creator, account):
    from app_modules.decision_cycles.serializers import DecisionCycleCreateSerializer
    ser = DecisionCycleCreateSerializer(
        data={'account_id': str(account.id), 'name': 'Via API'},
        context={'request': SimpleNamespace(user=creator), 'client_id': str(ca.id)},
    )
    ser.is_valid(raise_exception=True)
    cycle = ser.save()
    cycle.refresh_from_db()
    assert cycle.owner_id == creator.id


# ---------------------------------------------------------------------------
# Guard — model-level safety net: owner backfilled from created_by if left null.
# ---------------------------------------------------------------------------

def test_guard_owner_backfilled_from_created_by(ca, creator, account):
    cycle = DecisionCycle(
        client_id=ca.id, account_id=account.id, name="Guarded",
        created_by=creator, updated_by=creator,
    )
    cycle.save()
    cycle.refresh_from_db()
    assert cycle.owner_id == creator.id
