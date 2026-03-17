# backend/app_modules/campaigns/signals/signals.py
"""
Campaign module signals.

Auto-creates the TARGETED singleton campaign when a new User is created.
Ensures the campaign always exists without requiring a lazy GET endpoint.
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