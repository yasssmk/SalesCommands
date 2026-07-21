# backend/tests/campaigns/test_campaign_bulk_delete.py
"""
Campaign bulk-delete endpoint tests — DELETE /campaigns/bulk-delete/.

Mirrors the guarantees of the Territory bulk-delete viewset and adds the
Campaign-specific ones:

  - partial vs strict mode semantics
  - TARGETED singleton protection in BOTH modes (mirrors Territory's
    is_system guard: strict rejects the whole request, partial skips and
    reports)
  - client-scope isolation: a cross-tenant id is never deleted
  - max-ids (500) guard
  - permission denial for an ANONYMOUS caller AND for an authenticated
    same-tenant user that has no delete right on campaigns
  - activity cascade: Activity.campaign is on_delete=SET_NULL, so the
    endpoint must delete linked activities explicitly (like
    CampaignViewSet.destroy) instead of orphaning them

Permission-resolution note (why the no-delete user is a no-tier role):
    `bulk_delete` has NO custom action_policy, so ScopedPermission resolves
    it through the registry: normalize_action('bulk_delete') -> 'delete'
    (permissions/constants.py ACTION_TO_CRUD) and get_scope() re-normalises
    the same way (permissions/registry/__init__.py). CAMPAIGNS_REGISTRY maps
    campaigns.delete to a non-'none' scope for every tier (individual ->
    'mine'), so the only way to build an authenticated same-tenant user that
    is refused delete is a role carrying no tier flag at all — check_permission
    then returns None ("No valid tier found - DENY"). That path proves the
    action genuinely goes through the delete permission gate rather than being
    allowed by default.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.models import Campaign
from app_modules.campaigns.constants import CampaignType
from app_modules.activities.models import Activity

# Tenant-B fixtures are not re-exported by tests/campaigns/conftest.py (which
# only wires tenant A). Import them here for the cross-tenant isolation test,
# mirroring the re-export pattern the conftest itself uses.
from tests.signals.conftest import (  # noqa: F401
    tenant_b_id,
    client_account_b,
    role_individual_b,
    user_b,
)


BULK_DELETE_URL = '/campaigns/bulk-delete/'


# =============================================================================
# HELPERS
# =============================================================================

def _make_campaign(owner, client_id, name='Extra Outbound',
                   campaign_type=CampaignType.OUTBOUND):
    """Persist a campaign with the standard save(user=, client_id=) pattern."""
    today = timezone.now().date()
    c = Campaign(
        name=name,
        campaign_type=campaign_type,
        owner=owner,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
    )
    c.save(user=owner, client_id=client_id)
    return c


@pytest.fixture
def no_delete_user_a(db, client_account_a):
    """
    Authenticated tenant-A user whose role carries NO tier flag, so the
    registry resolves campaigns.delete to a denial for them (see module
    docstring). Used to prove ScopedPermission enforces delete on the
    bulk_delete action.
    """
    from end_users.models import User, UserRole

    role = UserRole.objects.create(
        client_account=client_account_a,
        name='No Delete',
        is_admin=False,
        is_manager=False,
        is_individual=False,
        read=True,
        write=False,
        modify=False,
        can_delete=False,
    )
    return User.objects.create(
        email='nodelete-a@tenant-a.test',
        client_account=client_account_a,
        role=role,
        is_active=True,
    )


# =============================================================================
# PARTIAL / STRICT MODE — HAPPY PATHS
# =============================================================================

class TestBulkDeleteModes:
    @pytest.mark.django_db
    def test_partial_mode_deletes_all_selected(self, authed_api_a, campaign, user_a, account):
        second = _make_campaign(user_a, account.client_id, name='Second Outbound')

        resp = authed_api_a.delete(
            BULK_DELETE_URL,
            data={'ids': [str(campaign.id), str(second.id)], 'mode': 'partial'},
            format='json',
        )

        assert resp.status_code == 200, resp.content
        assert not Campaign.objects.filter(id__in=[campaign.id, second.id]).exists()

    @pytest.mark.django_db
    def test_strict_mode_deletes_all_when_all_valid(self, authed_api_a, campaign, user_a, account):
        second = _make_campaign(user_a, account.client_id, name='Second Outbound')

        resp = authed_api_a.delete(
            BULK_DELETE_URL,
            data={'ids': [str(campaign.id), str(second.id)], 'mode': 'strict'},
            format='json',
        )

        assert resp.status_code == 200, resp.content
        assert not Campaign.objects.filter(id__in=[campaign.id, second.id]).exists()


# =============================================================================
# TARGETED SINGLETON PROTECTION — BOTH MODES
# =============================================================================

class TestTargetedProtection:
    @pytest.mark.django_db
    def test_partial_mode_skips_targeted_and_reports_it(self, authed_api_a, campaign, user_a, account):
        targeted = _make_campaign(
            user_a, account.client_id, name='My Targeted',
            campaign_type=CampaignType.TARGETED,
        )

        resp = authed_api_a.delete(
            BULK_DELETE_URL,
            data={'ids': [str(campaign.id), str(targeted.id)], 'mode': 'partial'},
            format='json',
        )

        # 207 Multi-Status: one deleted, one failed (protected).
        assert resp.status_code == 207, resp.content
        body = resp.json()
        assert str(campaign.id) in body['results']['success']
        assert str(targeted.id) in body['results']['failed']

        # Deletable one gone, targeted singleton preserved.
        assert not Campaign.objects.filter(id=campaign.id).exists()
        assert Campaign.objects.filter(id=targeted.id).exists()

    @pytest.mark.django_db
    def test_strict_mode_rejects_whole_batch_when_targeted_present(self, authed_api_a, campaign, user_a, account):
        targeted = _make_campaign(
            user_a, account.client_id, name='My Targeted',
            campaign_type=CampaignType.TARGETED,
        )

        resp = authed_api_a.delete(
            BULK_DELETE_URL,
            data={'ids': [str(campaign.id), str(targeted.id)], 'mode': 'strict'},
            format='json',
        )

        # Strict mode: nothing is deleted, not even the otherwise-deletable one.
        assert resp.status_code == 400, resp.content
        assert Campaign.objects.filter(id=campaign.id).exists()
        assert Campaign.objects.filter(id=targeted.id).exists()


# =============================================================================
# CLIENT-SCOPE ISOLATION
# =============================================================================

class TestClientScopeIsolation:
    @pytest.mark.django_db
    def test_cross_tenant_id_is_not_deleted(self, authed_api_a, user_b, client_account_b):
        # Campaign living on tenant B.
        foreign = _make_campaign(user_b, client_account_b.id, name='Tenant B Campaign')

        # Tenant-A rep tries to bulk-delete the tenant-B campaign.
        resp = authed_api_a.delete(
            BULK_DELETE_URL,
            data={'ids': [str(foreign.id)], 'mode': 'partial'},
            format='json',
        )

        # The id is invisible to tenant A (client-filtered base queryset), so it
        # is reported as not-found and never deleted.
        assert resp.status_code == 400, resp.content
        assert Campaign.objects.filter(id=foreign.id).exists()
        assert str(foreign.id) not in resp.json()['results']['success']


# =============================================================================
# INPUT GUARDS
# =============================================================================

class TestInputGuards:
    @pytest.mark.django_db
    def test_more_than_500_ids_rejected(self, authed_api_a):
        import uuid
        too_many = [str(uuid.uuid4()) for _ in range(501)]

        resp = authed_api_a.delete(
            BULK_DELETE_URL,
            data={'ids': too_many, 'mode': 'partial'},
            format='json',
        )

        assert resp.status_code == 400, resp.content

    @pytest.mark.django_db
    def test_empty_ids_rejected(self, authed_api_a):
        resp = authed_api_a.delete(
            BULK_DELETE_URL,
            data={'ids': [], 'mode': 'partial'},
            format='json',
        )
        assert resp.status_code == 400, resp.content


# =============================================================================
# PERMISSION DENIAL
# =============================================================================

class TestPermissionDenial:
    @pytest.mark.django_db
    def test_anonymous_is_denied(self, api, campaign):
        resp = api.delete(
            BULK_DELETE_URL,
            data={'ids': [str(campaign.id)], 'mode': 'partial'},
            format='json',
        )

        assert resp.status_code in (401, 403), resp.content
        assert Campaign.objects.filter(id=campaign.id).exists()

    @pytest.mark.django_db
    def test_same_tenant_user_without_delete_right_is_denied(
        self, api, authenticate, no_delete_user_a, client_account_a, campaign
    ):
        # Authenticated on the correct tenant, but the role resolves
        # campaigns.delete to a denial (no tier). Proves the default
        # ScopedPermission resolution of bulk_delete requires delete rights.
        authenticate(api, no_delete_user_a, client_account_a.id)

        resp = api.delete(
            BULK_DELETE_URL,
            data={'ids': [str(campaign.id)], 'mode': 'partial'},
            format='json',
        )

        assert resp.status_code == 403, resp.content
        assert Campaign.objects.filter(id=campaign.id).exists()


# =============================================================================
# CASCADE — Activity.campaign is SET_NULL, must be deleted explicitly
# =============================================================================

class TestActivityCascade:
    @pytest.mark.django_db
    def test_linked_activities_are_deleted_not_orphaned(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity
    ):
        today = timezone.now().date()
        cc = make_campaign_contact()
        activity = make_campaign_activity(cc, scheduled_date=today, sequence_position=1)

        assert Activity.objects.filter(id=activity.id).exists()

        resp = authed_api_a.delete(
            BULK_DELETE_URL,
            data={'ids': [str(campaign.id)], 'mode': 'partial'},
            format='json',
        )

        assert resp.status_code == 200, resp.content
        assert not Campaign.objects.filter(id=campaign.id).exists()
        # The activity must be gone — NOT left behind with campaign_id=NULL.
        assert not Activity.objects.filter(id=activity.id).exists()
