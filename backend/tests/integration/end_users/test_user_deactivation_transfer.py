# backend/tests/integration/end_users/test_user_deactivation_transfer.py
"""
Integration tests for the user-deactivation work transfer.

Deactivating a user (PATCH is_active True -> False) must, in ONE atomic block:
  - transfer non-terminal deals, prospect accounts and open deal-activities to
    an active successor,
  - cancel free activities (kept as history),
  - cancel the user's OUTBOUND campaigns (CANCELLED label),
  - empty (never cancel) the user's TARGETED campaign,
  - and finally flip is_active to False.

Terminal deals, finished activities, campaign membership, quotas and the
team-manager assignment are left untouched. A bad successor or any mid-transfer
failure aborts everything with no partial writes.
"""

import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from end_users.models import User, UserRole, ClientAccount
from app_modules.accounts.models import CompanyAccount, AccountType
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityType, ActivityStatus
from app_modules.campaigns.models import (
    Campaign, CampaignAccount, CampaignContact, CampaignContactStatus,
)
from app_modules.campaigns.constants import CampaignType, CampaignStatus
from app_modules.contacts.models import Contact

pytestmark = pytest.mark.django_db(transaction=True)


# ============================================================================
# Auth plumbing (JWT only, no CSRF) — mirrors test_perm.py
# ============================================================================

@pytest.fixture(autouse=True)
def _jwt_only_no_csrf(settings):
    rf = dict(getattr(settings, "REST_FRAMEWORK", {}))
    rf["DEFAULT_AUTHENTICATION_CLASSES"] = (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    )
    settings.REST_FRAMEWORK = rf
    settings.MIDDLEWARE = [
        m for m in settings.MIDDLEWARE
        if m != "django.middleware.csrf.CsrfViewMiddleware"
    ]


@pytest.fixture
def api():
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def tenant():
    return uuid.uuid4()


@pytest.fixture
def ca(db, tenant):
    return ClientAccount.objects.create(
        id=tenant, name="Company A", is_b2b=True, max_users=100
    )


@pytest.fixture
def roles(db, ca):
    # ClientAccount creation auto-provisions the default role set; reuse it.
    admin = UserRole.objects.filter(client_account=ca, is_admin=True).first() \
        or UserRole.objects.create(client_account=ca, name="Admin", is_admin=True)
    individual = UserRole.objects.filter(client_account=ca, is_individual=True).first() \
        or UserRole.objects.create(client_account=ca, name="Individual", is_individual=True)
    return {"admin": admin, "individual": individual}


@pytest.fixture
def admin(db, ca, roles):
    return User.objects.create(
        email="admin@a.test", client_account=ca, role=roles["admin"], is_active=True
    )


@pytest.fixture
def leaver(db, ca, roles):
    return User.objects.create(
        email="leaver@a.test", client_account=ca, role=roles["individual"], is_active=True
    )


@pytest.fixture
def successor(db, ca, roles):
    return User.objects.create(
        email="successor@a.test", client_account=ca, role=roles["individual"], is_active=True
    )


def _authenticate(api, user, client_id):
    role = getattr(user, "role", None)
    claims = {
        "origin": "end_users",
        "user_id": str(user.id),
        "client_account": str(client_id),
        "role": {
            "id": str(role.id) if role else "",
            "name": role.name if role else "",
            "is_admin": bool(getattr(role, "is_admin", False)) if role else False,
            "is_manager": bool(getattr(role, "is_manager", False)) if role else False,
            "is_individual": bool(getattr(role, "is_individual", False)) if role else False,
        },
        "is_superuser": bool(user.is_superuser),
    }
    api.force_authenticate(user=user, token=claims)
    api.credentials(
        HTTP_X_CLIENT_ID=str(client_id),
        HTTP_CLIENT_ID=str(client_id),
        HTTP_AUTHORIZATION="Bearer test-token",
    )


def _patch_user(api, target, client_id, data):
    url = reverse("client:user-detail", args=[target.pk]) + f"?client_id={client_id}"
    return api.patch(url, data=data, format="json")


def _deactivate(api, leaver, successor, ca):
    return _patch_user(api, leaver, ca.id, {
        "is_active": False, "successor_id": str(successor.id),
    })


# ============================================================================
# Object builders
# ============================================================================

def _account(owner, ca, name, atype=AccountType.PROSPECT):
    acc = CompanyAccount(
        company_name=name, type=atype, has_buying_decision=True, account_owner=owner,
    )
    acc.save(user=owner, client_id=ca.id)
    return acc


def _deal(owner, ca, account, name, outcome=None):
    c = DecisionCycle(account=account, owner=owner, name=name, outcome=outcome)
    c.save(user=owner, client_id=ca.id)
    return c


def _activity(owner, ca, account, *, status=ActivityStatus.PLANNED,
              decision_cycle=None, campaign=None, title="Act"):
    a = Activity(
        title=title, activity_type=ActivityType.CALL, status=status,
        account=account, owner=owner, decision_cycle=decision_cycle, campaign=campaign,
    )
    a.save(user=owner, client_id=ca.id)
    return a


def _campaign(owner, ca, *, ctype=CampaignType.OUTBOUND,
              cstatus=CampaignStatus.ACTIVE, name="Camp"):
    today = timezone.now().date()
    c = Campaign(
        name=name, campaign_type=ctype, owner=owner, status=cstatus,
        planned_start_date=today, planned_end_date=today + timedelta(days=30),
    )
    c.save(user=owner, client_id=ca.id)
    return c


# ============================================================================
# Deals
# ============================================================================

def test_non_terminal_deal_transferred(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Deal Co")
    deal = _deal(leaver, ca, acc, "Open deal", outcome=None)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    deal.refresh_from_db()
    assert deal.owner_id == successor.id


@pytest.mark.parametrize("outcome", [
    CycleOutcome.WON, CycleOutcome.LOST, CycleOutcome.NOT_QUALIFIED,
])
def test_terminal_deal_not_transferred(api, ca, admin, leaver, successor, outcome):
    acc = _account(leaver, ca, f"Won Co {outcome}")
    deal = _deal(leaver, ca, acc, "Closed deal", outcome=outcome)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    deal.refresh_from_db()
    assert deal.owner_id == leaver.id  # terminal deals are history


def test_on_hold_deal_is_transferred(api, ca, admin, leaver, successor):
    # ON_HOLD is non-terminal (paused, alive) -> must transfer.
    acc = _account(leaver, ca, "Paused Co")
    deal = _deal(leaver, ca, acc, "Paused deal", outcome=CycleOutcome.ON_HOLD)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    deal.refresh_from_db()
    assert deal.owner_id == successor.id


# ============================================================================
# Accounts
# ============================================================================

def test_prospect_account_transferred(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Prospect Co", atype=AccountType.PROSPECT)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    acc.refresh_from_db()
    assert acc.account_owner_id == successor.id


def test_client_account_not_transferred(api, ca, admin, leaver, successor):
    # Product decision: only PROSPECT accounts transfer; CLIENT accounts keep
    # their owner. (Flagged for confirmation.)
    acc = _account(leaver, ca, "Client Co", atype=AccountType.CLIENT)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    acc.refresh_from_db()
    assert acc.account_owner_id == leaver.id


# ============================================================================
# Activities
# ============================================================================

def test_open_deal_activity_transferred(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Deal Co")
    deal = _deal(leaver, ca, acc, "Open deal")
    act = _activity(leaver, ca, acc, status=ActivityStatus.PLANNED, decision_cycle=deal)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    act.refresh_from_db()
    assert act.owner_id == successor.id
    assert act.status == ActivityStatus.PLANNED  # still open, just re-owned


def test_completed_activity_not_touched(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Deal Co")
    deal = _deal(leaver, ca, acc, "Open deal")
    act = _activity(leaver, ca, acc, status=ActivityStatus.COMPLETED, decision_cycle=deal)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    act.refresh_from_db()
    assert act.owner_id == leaver.id           # history, not re-owned
    assert act.status == ActivityStatus.COMPLETED


def test_free_activity_cancelled(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Free Co")
    # neither a deal nor a campaign
    act = _activity(leaver, ca, acc, status=ActivityStatus.PLANNED)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    act.refresh_from_db()
    assert act.status == ActivityStatus.CANCELLED
    assert act.owner_id == leaver.id  # cancelled, not transferred


# ============================================================================
# Campaigns
# ============================================================================

def test_outbound_campaign_cancelled_activities_split(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Camp Co")
    campaign = _campaign(leaver, ca, ctype=CampaignType.OUTBOUND, cstatus=CampaignStatus.ACTIVE)
    deal = _deal(leaver, ca, acc, "Deal in campaign")

    # A pending NON-deal campaign activity -> should be CANCELLED by cancel().
    non_deal = _activity(leaver, ca, acc, status=ActivityStatus.PLANNED, campaign=campaign)
    # A pending DEAL activity in the campaign -> spared and transferred (rule 3).
    deal_act = _activity(leaver, ca, acc, status=ActivityStatus.PLANNED,
                         campaign=campaign, decision_cycle=deal)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    campaign.refresh_from_db()
    assert campaign.status == CampaignStatus.CANCELLED  # CANCEL path, not COMPLETE
    non_deal.refresh_from_db()
    assert non_deal.status == ActivityStatus.CANCELLED
    deal_act.refresh_from_db()
    assert deal_act.owner_id == successor.id            # spared + transferred
    assert deal_act.status == ActivityStatus.PLANNED


def test_targeted_emptied_not_cancelled(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Targeted Co")
    # Each user is auto-provisioned one perpetual TARGETED campaign (unique per
    # user); reuse it, or create one if the bootstrap did not run.
    targeted = Campaign.objects.filter(
        owner=leaver, campaign_type=CampaignType.TARGETED, client_id=ca.id,
    ).first() or _campaign(leaver, ca, ctype=CampaignType.TARGETED,
                           cstatus=CampaignStatus.ACTIVE, name="My Targeted")
    camp_acc = CampaignAccount(campaign=targeted, account=acc)
    camp_acc.save(user=leaver, client_id=ca.id)
    contact = Contact(account=acc, first_name="C", last_name="One")
    contact.save(user=leaver, client_id=ca.id)
    camp_acc.target_contacts.add(contact)
    cc = CampaignContact(campaign_account=camp_acc, contact=contact,
                         status=CampaignContactStatus.IN_PROGRESS)
    cc.save(user=leaver, client_id=ca.id)
    cc_activity = _activity(leaver, ca, acc, status=ActivityStatus.PLANNED, campaign=targeted)
    cc_activity.campaign_contact = cc
    cc_activity.save(user=leaver, client_id=ca.id)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code == status.HTTP_200_OK
    targeted.refresh_from_db()
    # TARGETED is a perpetual invariant: never cancelled.
    assert targeted.status != CampaignStatus.CANCELLED
    # Its contacts are removed.
    assert not CampaignContact.objects.filter(campaign_account__campaign=targeted).exists()
    assert camp_acc.target_contacts.count() == 0
    # The contact's open activity is cancelled but KEPT (never deleted).
    cc_activity.refresh_from_db()
    assert cc_activity.status == ActivityStatus.CANCELLED


# ============================================================================
# Successor validation
# ============================================================================

def test_successor_inactive_refused(api, ca, admin, leaver, roles):
    inactive = User.objects.create(
        email="inactive@a.test", client_account=ca, role=roles["individual"], is_active=False
    )
    acc = _account(leaver, ca, "Deal Co")
    deal = _deal(leaver, ca, acc, "Open deal")

    _authenticate(api, admin, ca.id)
    resp = _patch_user(api, leaver, ca.id, {
        "is_active": False, "successor_id": str(inactive.id),
    })

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    leaver.refresh_from_db()
    deal.refresh_from_db()
    assert leaver.is_active is True          # nothing happened
    assert deal.owner_id == leaver.id


def test_successor_self_refused(api, ca, admin, leaver):
    acc = _account(leaver, ca, "Deal Co")
    deal = _deal(leaver, ca, acc, "Open deal")

    _authenticate(api, admin, ca.id)
    resp = _patch_user(api, leaver, ca.id, {
        "is_active": False, "successor_id": str(leaver.id),
    })

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    leaver.refresh_from_db()
    assert leaver.is_active is True


def test_successor_missing_refused(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Deal Co")
    deal = _deal(leaver, ca, acc, "Open deal")

    _authenticate(api, admin, ca.id)
    resp = _patch_user(api, leaver, ca.id, {"is_active": False})

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    leaver.refresh_from_db()
    deal.refresh_from_db()
    assert leaver.is_active is True
    assert deal.owner_id == leaver.id


def test_successor_other_tenant_refused(api, ca, admin, leaver):
    other_ca = ClientAccount.objects.create(name="Other", is_b2b=True, max_users=10)
    other_role = UserRole.objects.create(client_account=other_ca, name="I", is_individual=True)
    other_user = User.objects.create(
        email="other@b.test", client_account=other_ca, role=other_role, is_active=True
    )

    _authenticate(api, admin, ca.id)
    resp = _patch_user(api, leaver, ca.id, {
        "is_active": False, "successor_id": str(other_user.id),
    })

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    leaver.refresh_from_db()
    assert leaver.is_active is True


# ============================================================================
# Atomicity + reactivation
# ============================================================================

def test_transfer_is_atomic(api, ca, admin, leaver, successor, monkeypatch):
    """A failure mid-transfer (step 6, emptying TARGETED) rolls EVERYTHING back:
    the deal stays with the leaver and the user stays active."""
    from end_users.views.user_view import UserViewSet

    acc = _account(leaver, ca, "Deal Co")
    deal = _deal(leaver, ca, acc, "Open deal")

    def _boom(self, *a, **k):
        raise RuntimeError("boom mid-transfer")

    monkeypatch.setattr(UserViewSet, "_empty_targeted_campaign", _boom)

    _authenticate(api, admin, ca.id)
    resp = _deactivate(api, leaver, successor, ca)

    assert resp.status_code >= 400  # request failed
    leaver.refresh_from_db()
    deal.refresh_from_db()
    assert leaver.is_active is True            # flip rolled back
    assert deal.owner_id == leaver.id          # step-1 transfer rolled back


def test_reactivation_restores_nothing(api, ca, admin, leaver, successor):
    acc = _account(leaver, ca, "Deal Co")
    deal = _deal(leaver, ca, acc, "Open deal")

    _authenticate(api, admin, ca.id)
    assert _deactivate(api, leaver, successor, ca).status_code == status.HTTP_200_OK
    deal.refresh_from_db()
    assert deal.owner_id == successor.id

    # Reactivate: no successor required, nothing is restored.
    resp = _patch_user(api, leaver, ca.id, {"is_active": True})
    assert resp.status_code == status.HTTP_200_OK
    leaver.refresh_from_db()
    deal.refresh_from_db()
    assert leaver.is_active is True
    assert deal.owner_id == successor.id  # stays with successor
