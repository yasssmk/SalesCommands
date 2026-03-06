# app_modules/campaigns/services/campaign_lifecycle_service.py
"""
CampaignLifecycleService — state machine transitions for campaigns.

Responsibilities:
    - start: DRAFT → ACTIVE (+ enroll accounts from Territory if not done)
    - pause: ACTIVE → PAUSED (+ pause in-progress accounts)
    - resume: PAUSED → ACTIVE (+ resume paused accounts)
    - complete: ACTIVE/PAUSED → COMPLETED (+ stop remaining accounts)
    - cancel: any non-final → CANCELLED (+ stop all accounts)

Each method validates the transition, updates Campaign status,
and cascades status changes to CampaignAccount entries.
"""

from django.db import transaction
from django.utils import timezone

from core.logging import get_logger
from core.logging.audit import audit_log
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages

from ..models import (
    Campaign,
    CampaignStatus,
    CampaignAccount,
    CampaignAccountStatus,
    CAMPAIGN_ACCOUNT_TRANSITIONS,
)
from ..config.settings import CONFIG

logger = get_logger(__name__)


class CampaignLifecycleService:
    """
    Service for managing campaign state transitions.

    Usage:
        service = CampaignLifecycleService(user=request.user, client_id=client_id)
        result = service.start(campaign)
    """

    def __init__(self, user, client_id):
        self.user = user
        self.client_id = str(client_id)

    # ======================================================================
    # PUBLIC API
    # ======================================================================

    @transaction.atomic
    def start(self, campaign):
        self._validate_ownership(campaign)

        accounts_enrolled = 0
        if campaign.campaign_type == 'OUTBOUND' and campaign.campaign_accounts.count() == 0:
            from .campaign_creation_service import CampaignCreationService
            creation_service = CampaignCreationService(user=self.user, client_id=self.client_id)
            accounts_enrolled = creation_service._enroll_from_territory(campaign)

        if campaign.campaign_accounts.count() == 0:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_NO_ACCOUNTS
            )

        campaign.start(user=self.user)

        accounts_activated = self._cascade_accounts(
            campaign,
            from_status=CampaignAccountStatus.PENDING,
            to_status=CampaignAccountStatus.IN_PROGRESS,
        )

        # Generate activities — surface errors instead of swallowing them
        from .campaign_execution_service import CampaignExecutionService
        execution_service = CampaignExecutionService(user=self.user, client_id=self.client_id)

        try:
            gen_result = execution_service.generate_activities(campaign)
        except Exception as e:
            logger.error("campaign_start_activity_generation_failed", extra={
                'campaign_id': str(campaign.id),
                'error': str(e),
            })
            gen_result = {
                'activities_created': 0,
                'accounts_processed': 0,
                'accounts_skipped': 0,
                'errors': [str(e)],
            }

        activities_created = gen_result.get('activities_created', 0)
        generation_errors = gen_result.get('errors', [])

        if generation_errors:
            logger.warning("campaign_start_partial_errors", extra={
                'campaign_id': str(campaign.id),
                'activities_created': activities_created,
                'errors_count': len(generation_errors),
                'errors': generation_errors[:5],
            })

        self._audit('campaign_started', campaign, extra={
            'accounts_activated': accounts_activated,
            'accounts_enrolled': accounts_enrolled,
            'activities_created': activities_created,
            'generation_errors': len(generation_errors),
        })

        logger.info("campaign_started", extra={
            'campaign_id': str(campaign.id),
            'accounts_activated': accounts_activated,
            'accounts_enrolled': accounts_enrolled,
            'activities_created': activities_created,
        })

        return {
            'campaign': campaign,
            'accounts_activated': accounts_activated,
            'accounts_enrolled': accounts_enrolled,
            'activities_created': activities_created,
            'generation_errors': generation_errors,
        }


    @transaction.atomic
    def pause(self, campaign):
        """
        Pause a campaign: ACTIVE → PAUSED.

        Side effects:
            - No cascade on accounts (they keep their current state)
            - Activity generation is halted (checked by execution service)

        Returns:
            dict: {campaign}
        """
        self._validate_ownership(campaign)
        campaign.pause(user=self.user)

        self._audit('campaign_paused', campaign)

        logger.info("campaign_paused", extra={
            'campaign_id': str(campaign.id),
        })

        return {
            'campaign': campaign,
        }

    @transaction.atomic
    def resume(self, campaign):
        """
        Resume a campaign: PAUSED → ACTIVE.

        Side effects:
            - Callback-pending accounts with past callback_date → IN_PROGRESS

        Returns:
            dict: {campaign, callbacks_resumed}
        """
        self._validate_ownership(campaign)
        campaign.resume(user=self.user)

        # Resume callbacks that are due
        callbacks_resumed = self._resume_due_callbacks(campaign)

        self._audit('campaign_resumed', campaign, extra={
            'callbacks_resumed': callbacks_resumed,
        })

        logger.info("campaign_resumed", extra={
            'campaign_id': str(campaign.id),
            'callbacks_resumed': callbacks_resumed,
        })

        return {
            'campaign': campaign,
            'callbacks_resumed': callbacks_resumed,
        }

    @transaction.atomic
    def complete(self, campaign):
        """
        Complete a campaign: ACTIVE/PAUSED → COMPLETED.

        Side effects:
            - All non-final accounts → STOPPED (with reason)

        Returns:
            dict: {campaign, accounts_stopped}
        """
        self._validate_ownership(campaign)
        campaign.complete(user=self.user)

        # Stop remaining accounts
        accounts_stopped = self._stop_remaining_accounts(
            campaign,
            reason="Campaign completed",
        )

        self._audit('campaign_completed', campaign, extra={
            'accounts_stopped': accounts_stopped,
        })

        logger.info("campaign_completed", extra={
            'campaign_id': str(campaign.id),
            'accounts_stopped': accounts_stopped,
        })

        return {
            'campaign': campaign,
            'accounts_stopped': accounts_stopped,
        }

    @transaction.atomic
    def cancel(self, campaign):
        """
        Cancel a campaign: any non-final → CANCELLED.

        Side effects:
            - All non-final accounts → STOPPED (with reason)
            - Planned activities for this campaign → CANCELLED

        Returns:
            dict: {campaign, accounts_stopped, activities_cancelled}
        """
        self._validate_ownership(campaign)
        campaign.cancel(user=self.user)

        # Stop remaining accounts
        accounts_stopped = self._stop_remaining_accounts(
            campaign,
            reason="Campaign cancelled",
        )

        # Cancel planned activities
        activities_cancelled = self._cancel_planned_activities(campaign)

        self._audit('campaign_cancelled', campaign, extra={
            'accounts_stopped': accounts_stopped,
            'activities_cancelled': activities_cancelled,
        })

        logger.info("campaign_cancelled", extra={
            'campaign_id': str(campaign.id),
            'accounts_stopped': accounts_stopped,
            'activities_cancelled': activities_cancelled,
        })

        return {
            'campaign': campaign,
            'accounts_stopped': accounts_stopped,
            'activities_cancelled': activities_cancelled,
        }

    # ======================================================================
    # PRIVATE — ACCOUNT CASCADE
    # ======================================================================

    def _cascade_accounts(self, campaign, from_status, to_status):
        """
        Bulk transition CampaignAccounts from one status to another.

        Returns:
            int: number of accounts transitioned
        """
        accounts = CampaignAccount.objects.filter(
            campaign=campaign,
            status=from_status,
        )
        count = accounts.update(
            status=to_status,
            updated_at=timezone.now(),
        )
        return count

    def _stop_remaining_accounts(self, campaign, reason="Campaign ended"):
        """
        Stop all non-final CampaignAccounts.

        Returns:
            int: number of accounts stopped
        """
        non_final = CampaignAccount.objects.filter(
            campaign=campaign,
        ).exclude(
            status__in=[CampaignAccountStatus.COMPLETED, CampaignAccountStatus.STOPPED],
        )
        count = non_final.update(
            status=CampaignAccountStatus.STOPPED,
            notes=reason,
            updated_at=timezone.now(),
        )
        return count

    def _resume_due_callbacks(self, campaign):
        """
        Resume CALLBACK_PENDING accounts where callback_date <= today.

        Returns:
            int: number of accounts resumed
        """
        today = timezone.now().date()
        due_callbacks = CampaignAccount.objects.filter(
            campaign=campaign,
            status=CampaignAccountStatus.CALLBACK_PENDING,
            callback_date__lte=today,
        )
        count = due_callbacks.update(
            status=CampaignAccountStatus.IN_PROGRESS,
            callback_date=None,
            notes="Resumed from callback (campaign resumed)",
            updated_at=timezone.now(),
        )
        return count

    # ======================================================================
    # PRIVATE — ACTIVITY CASCADE
    # ======================================================================

    def _cancel_planned_activities(self, campaign):
        """
        Cancel all PLANNED activities linked to this campaign.

        Returns:
            int: number of activities cancelled
        """
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus

        planned = Activity.objects.filter(
            campaign=campaign,
            status=ActivityStatus.PLANNED,
        )
        count = planned.update(
            status=ActivityStatus.CANCELLED,
            outcome_notes="Campaign cancelled",
            updated_at=timezone.now(),
        )
        return count

    # ======================================================================
    # PRIVATE — VALIDATION
    # ======================================================================

    def _validate_ownership(self, campaign):
        """
        Validate the campaign belongs to the current client.

        Note: Role-based permission (OWNER only) is handled at ViewSet level
        via ScopedPermission. Service validates client scope only.
        """
        if str(campaign.client_id) != self.client_id:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_IN_FINAL_STATE.format(
                    state='access denied'
                )
            )

    # ======================================================================
    # PRIVATE — AUDIT
    # ======================================================================

    def _audit(self, event, campaign, extra=None):
        """Emit audit log for lifecycle events."""
        audit_data = {
            'campaign_name': campaign.name,
            'campaign_status': campaign.status,
        }
        if extra:
            audit_data.update(extra)

        audit_log(
            event=event,
            action='update',
            actor_id=str(self.user.id),
            client_id=self.client_id,
            target_type='campaign',
            target_id=str(campaign.id),
            outcome='success',
            extra=audit_data,
        )