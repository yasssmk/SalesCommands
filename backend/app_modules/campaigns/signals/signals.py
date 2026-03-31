# backend/app_modules/campaigns/signals/signals.py
"""
Campaign module signals.

- Auto-creates the TARGETED singleton campaign when a new User is created.
- Auto-completes CampaignAccount when all its contacts reach a final state.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.logging import get_logger

logger = get_logger(__name__)


@receiver(post_save, sender='end_users.User')
def create_targeted_campaign_on_user_created(sender, instance, created, **kwargs):
    """
    Auto-create the TARGETED singleton campaign when a new user is created.

    Runs after transaction commit to avoid nested atomic block issues.
    Non-blocking: user creation must never fail due to campaign creation errors.
    """
    if not created:
        return

    from django.db import transaction
    transaction.on_commit(lambda: _bootstrap_targeted_campaign(instance))


def _bootstrap_targeted_campaign(user):
    """
    Create the TARGETED campaign for a newly created user.
    Isolated in a separate function so exceptions never propagate upward.
    """
    try:
        from app_modules.campaigns.services.campaign_creation_service import CampaignCreationService

        client_id = str(user.client_account_id)
        service = CampaignCreationService(user=user, client_id=client_id)
        _, created = service.get_or_create_targeted(sequence_type='TARGETED')

        logger.info(
            "targeted_campaign_bootstrap",
            extra={
                'event': 'targeted_campaign_bootstrap',
                'user_id': str(user.id),
                'client_id': client_id,
                'created': created,
            },
        )
    except Exception as exc:
        import traceback
        logger.error(
            "targeted_campaign_bootstrap_failed",
            extra={
                'event': 'targeted_campaign_bootstrap_failed',
                'user_id': str(user.id),
                'error': str(exc),
                'traceback': traceback.format_exc(),
            },
        )


@receiver(post_save, sender='module_campaigns.CampaignContact')
def auto_complete_account_on_contact_final(sender, instance, created, **kwargs):
    """
    When a CampaignContact reaches a final state, check if the parent
    CampaignAccount should be auto-completed or auto-stopped.

    Deferred to after commit to avoid nested transaction issues.
    Non-blocking: account auto-completion must never break contact save.
    """
    if created:
        return

    from app_modules.campaigns.models.campaign_contact import FINAL_CONTACT_STATES
    if instance.status not in FINAL_CONTACT_STATES:
        return

    from django.db import transaction
    campaign_account_id = instance.campaign_account_id

    transaction.on_commit(
        lambda: _check_account_completion_safe(campaign_account_id)
    )


def _check_account_completion_safe(campaign_account_id):
    """
    Safely check and auto-complete a CampaignAccount.
    Isolated so exceptions never propagate to the original save.
    """
    try:
        from app_modules.campaigns.models.campaign_account import (
            CampaignAccount,
            CampaignAccountStatus,
        )
        from app_modules.campaigns.models.campaign_contact import CampaignContactStatus

        ca = CampaignAccount.objects.select_related('campaign').get(id=campaign_account_id)

        if ca.status in (CampaignAccountStatus.COMPLETED, CampaignAccountStatus.STOPPED):
            return

        if not ca.all_contacts_done():
            return

        any_completed = ca.campaign_contacts.filter(
            status=CampaignContactStatus.COMPLETED
        ).exists()

        if any_completed:
            ca.mark_completed(notes="All contacts resolved — at least one successful")
        else:
            ca.mark_stopped(notes="All contacts stopped — no successful outcome")

        logger.info("campaign_account_auto_completed", extra={
            'campaign_account_id': str(campaign_account_id),
            'final_status': ca.status,
        })

        # Trigger campaign-level auto-completion check after account is finalized.
        from django.db import transaction
        campaign_id = ca.campaign_id
        transaction.on_commit(
            lambda: _check_campaign_completion_safe(campaign_id)
        )

    except Exception as exc:
        logger.error(
            "campaign_account_auto_completion_failed",
            extra={
                'campaign_account_id': str(campaign_account_id),
                'error': str(exc),
            },
        )


def _check_campaign_completion_safe(campaign_id):
    """
    Auto-complete a Campaign when all its CampaignAccounts reach a final state.

    Only applies to non-TARGETED ACTIVE campaigns — TARGETED campaigns are
    perpetual by design and never auto-complete.
    """
    try:
        from app_modules.campaigns.models.campaign import Campaign
        from app_modules.campaigns.models.campaign_account import (
            CampaignAccount,
            CampaignAccountStatus,
        )
        from app_modules.campaigns.constants import CampaignStatus, CampaignType, FINAL_ACCOUNT_STATES

        campaign = Campaign.objects.get(id=campaign_id)

        # TARGETED campaigns are perpetual — never auto-complete.
        if campaign.campaign_type == CampaignType.TARGETED:
            return

        # Only auto-complete ACTIVE campaigns.
        if campaign.status != CampaignStatus.ACTIVE:
            return

        # Check all accounts are in a final state.
        has_non_final = CampaignAccount.objects.filter(
            campaign=campaign,
        ).exclude(
            status__in=FINAL_ACCOUNT_STATES,
        ).exists()

        if has_non_final:
            return

        # All accounts final — auto-complete the campaign.
        from django.utils import timezone
        campaign.complete(user=None)
        campaign.actual_end_date = timezone.now().date()
        campaign.save(update_fields=['actual_end_date', 'updated_at'])

        logger.info("campaign_auto_completed", extra={
            'campaign_id': str(campaign_id),
        })

    except Exception as exc:
        logger.error(
            "campaign_auto_completion_failed",
            extra={
                'campaign_id': str(campaign_id),
                'error': str(exc),
            },
        )