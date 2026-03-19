# app_modules/campaigns/services/campaign_lifecycle_service.py
"""
CampaignLifecycleService — state machine transitions for campaigns.

Responsibilities:
    - start: DRAFT → ACTIVE (+ enroll accounts, generate activities)
    - pause: ACTIVE → PAUSED (+ PLANNED activities → ON_HOLD)
    - resume: PAUSED → ACTIVE (+ ON_HOLD → PLANNED with recalculated dates)
    - complete: ACTIVE/PAUSED → COMPLETED (+ collect open contacts)
    - cancel: any non-final → CANCELLED (+ stop accounts, cancel activities)

Each method validates the transition, updates Campaign status,
and cascades status changes to CampaignAccount and Activity entries.
"""


from django.db import transaction
from django.utils import timezone

from core.logging import get_logger
from core.logging.audit import audit_log
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages, CoreErrorMessages

from ..models import (
    CampaignAccount,
    CampaignAccountStatus,
)

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

        # Record actual start date
        campaign.actual_start_date = timezone.now().date()
        campaign.save(update_fields=['actual_start_date', 'updated_at'])

        accounts_enrolled = 0
        from ..models import CampaignType
        if campaign.campaign_type != CampaignType.TARGETED and campaign.campaign_accounts.count() == 0:
            from .campaign_creation_service import CampaignCreationService
            creation_service = CampaignCreationService(user=self.user, client_id=self.client_id)
            accounts_enrolled = creation_service._enroll_from_territories(campaign)


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

        # Transition pre-created CampaignContacts from PENDING → IN_PROGRESS
        from ..models import CampaignContact, CampaignContactStatus
        CampaignContact.objects.filter(
            campaign_account__campaign=campaign,
            status=CampaignContactStatus.PENDING,
        ).update(
            status=CampaignContactStatus.IN_PROGRESS,
            updated_at=timezone.now(),
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
            - PLANNED activities → ON_HOLD
            - Activity generation is halted (checked by execution service)

        Returns:
            dict: {campaign, activities_paused}
        """
        self._validate_ownership(campaign)
        campaign.pause(user=self.user)

        # Put PLANNED activities on hold
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus

        activities_paused = Activity.objects.filter(
            campaign=campaign,
            status=ActivityStatus.PLANNED,
            client_id=self.client_id,
        ).update(
            status=ActivityStatus.ON_HOLD,
            updated_at=timezone.now(),
        )

        # Pause IN_PROGRESS contacts — they will resume when campaign resumes
        from ..models.campaign_contact import CampaignContact, CampaignContactStatus
        contacts_paused = CampaignContact.objects.filter(
            campaign_account__campaign=campaign,
            status=CampaignContactStatus.IN_PROGRESS,
        ).update(
            status=CampaignContactStatus.ON_HOLD,
            notes="Campaign paused",
            updated_at=timezone.now(),
        )

        self._audit('campaign_paused', campaign, extra={
            'activities_paused': activities_paused,
            'contacts_paused': contacts_paused,
        })

        logger.info("campaign_paused", extra={
            'campaign_id': str(campaign.id),
            'activities_paused': activities_paused,
            'contacts_paused': contacts_paused,
        })

        return {
            'campaign': campaign,
            'activities_paused': activities_paused,
            'contacts_paused': contacts_paused,
        }


    @transaction.atomic
    def resume(self, campaign):
        """
        Resume a campaign: PAUSED → ACTIVE.

        Side effects:
            - ON_HOLD activities → PLANNED with recalculated scheduled_dates
            - Callback-pending accounts with past callback_date → IN_PROGRESS

        Returns:
            dict: {campaign, activities_resumed, callbacks_resumed}
        """
        self._validate_ownership(campaign)
        campaign.resume(user=self.user)

        # Resume ON_HOLD activities with recalculated dates
        activities_resumed = self._resume_on_hold_activities(campaign)

        # Resume callbacks that are due
        callbacks_resumed = self._resume_due_callbacks(campaign)

        # Restore ON_HOLD contacts → IN_PROGRESS (CALLBACK_PENDING untouched)
        from ..models.campaign_contact import CampaignContact, CampaignContactStatus
        contacts_resumed = CampaignContact.objects.filter(
            campaign_account__campaign=campaign,
            status=CampaignContactStatus.ON_HOLD,
        ).update(
            status=CampaignContactStatus.IN_PROGRESS,
            notes="Campaign resumed",
            updated_at=timezone.now(),
        )

        self._audit('campaign_resumed', campaign, extra={
            'activities_resumed': activities_resumed,
            'callbacks_resumed': callbacks_resumed,
            'contacts_resumed': contacts_resumed,
        })

        logger.info("campaign_resumed", extra={
            'campaign_id': str(campaign.id),
            'activities_resumed': activities_resumed,
            'callbacks_resumed': callbacks_resumed,
            'contacts_resumed': contacts_resumed,
        })

        return {
            'campaign': campaign,
            'activities_resumed': activities_resumed,
            'callbacks_resumed': callbacks_resumed,
            'contacts_resumed': contacts_resumed,
        }


    @transaction.atomic
    def complete(self, campaign):
        """
        Complete a campaign: ACTIVE/PAUSED → COMPLETED.

        Does NOT auto-cancel remaining PLANNED activities.
        Returns open contacts so the caller can offer a follow-up transfer
        to the TARGETED campaign.

        Returns:
            dict: {campaign, open_contacts}
                open_contacts: list of dicts {
                    campaign_contact_id, contact_id, contact_name,
                    account_id, account_name, callback_date
                }
        """
        self._validate_ownership(campaign)
        campaign.complete(user=self.user)

        # Record actual end date
        campaign.actual_end_date = timezone.now().date()
        campaign.save(update_fields=['actual_end_date', 'updated_at'])

        open_contacts = self._collect_open_contacts(campaign)

        self._audit('campaign_completed', campaign, extra={
            'open_contacts_count': len(open_contacts),
        })

        logger.info("campaign_completed", extra={
            'campaign_id': str(campaign.id),
            'open_contacts_count': len(open_contacts),
        })

        return {
            'campaign': campaign,
            'open_contacts': open_contacts,
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
    
    def _resume_on_hold_activities(self, campaign):
        """
        Resume ON_HOLD activities → PLANNED with recalculated scheduled_dates.

        Date recalculation uses base_date = today, then applies cumulative
        min_delay_days from the sequence chain (same logic as playlist).

        Returns:
            int: number of activities resumed
        """
        from datetime import timedelta
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus

        today = timezone.now().date()

        on_hold_activities = list(
            Activity.objects.filter(
                campaign=campaign,
                status=ActivityStatus.ON_HOLD,
                client_id=self.client_id,
            ).select_related('campaign_contact', 'previous_activity')
        )

        if not on_hold_activities:
            return 0

        by_id = {a.id: a for a in on_hold_activities}

        for activity in on_hold_activities:
            base_date = today
            cumulative_delay = self._cumulative_delay_from_root(activity, by_id)

            if cumulative_delay > 0:
                scheduled = self._next_business_day(base_date + timedelta(days=cumulative_delay))
            else:
                scheduled = self._next_business_day(base_date)

            activity.status = ActivityStatus.PLANNED
            activity.scheduled_date = scheduled
            activity.save(update_fields=['status', 'scheduled_date', 'updated_at'])

        return len(on_hold_activities)

    def _cumulative_delay_from_root(self, activity, by_id, _visited=None):
        """Walk previous_activity chain, summing min_delay_days."""
        if _visited is None:
            _visited = set()
        if activity.id in _visited:
            return 0
        _visited.add(activity.id)

        prev = activity.previous_activity
        if prev is None:
            return 0

        prev_delay = self._cumulative_delay_from_root(prev, by_id, _visited)
        own_delay = activity.min_delay_days or 0
        return prev_delay + own_delay

    def _next_business_day(self, date):
        """Advance date past weekends (Mon-Fri only)."""
        from datetime import timedelta
        while date.weekday() >= 5:
            date += timedelta(days=1)
        return date



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
        Resume CALLBACK_PENDING contacts where callback_date <= today.

        Returns:
            int: number of contacts resumed
        """
        from ..models.campaign_contact import CampaignContact, CampaignContactStatus

        today = timezone.now().date()
        due_callbacks = CampaignContact.objects.filter(
            campaign_account__campaign=campaign,
            status=CampaignContactStatus.CALLBACK_PENDING,
            callback_date__lte=today,
        )
        count = due_callbacks.update(
            status=CampaignContactStatus.IN_PROGRESS,
            callback_date=None,
            notes="Resumed from callback (campaign resumed)",
            updated_at=timezone.now(),
        )
        return count

    
    def _collect_open_contacts(self, campaign):
        """
        Return contacts that still have PLANNED activities in this campaign.

        Used after completion to offer transfer to the TARGETED campaign.

        Returns:
            list[dict]: each dict has keys:
                campaign_contact_id, contact_id, contact_name,
                account_id, account_name, callback_date
        """
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus

        planned_qs = (
            Activity.objects
            .filter(campaign=campaign, status=ActivityStatus.PLANNED, client_id=self.client_id)
            .select_related(
                'campaign_contact',
                'campaign_contact__contact',
                'account',
            )
            .values(
                'campaign_contact_id',
                'campaign_contact__contact_id',
                'campaign_contact__contact__first_name',
                'campaign_contact__contact__last_name',
                'campaign_contact__callback_date',
                'account_id',
                'account__company_name',
            )
            .distinct()
        )

        # Deduplicate by (campaign_contact_id, account_id) pair
        seen = set()
        result = []
        for row in planned_qs:
            cc_id = row['campaign_contact_id']
            account_id = row['account_id']

            # Dedup key: prefer campaign_contact_id, fallback to account_id
            dedup_key = (str(cc_id) if cc_id else None, str(account_id) if account_id else None)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            first = row['campaign_contact__contact__first_name'] or ''
            last = row['campaign_contact__contact__last_name'] or ''
            contact_name = f"{first} {last}".strip()

            result.append({
                'campaign_contact_id': str(cc_id) if cc_id else None,
                'contact_id': str(row['campaign_contact__contact_id']) if row['campaign_contact__contact_id'] else None,
                'contact_name': contact_name or row['account__company_name'] or 'Unknown',
                'account_id': str(account_id) if account_id else None,
                'account_name': row['account__company_name'] or '',
                'callback_date': (
                    row['campaign_contact__callback_date'].isoformat()
                    if row['campaign_contact__callback_date'] else None
                ),
            })

        return result

    # ======================================================================
    # PRIVATE — ACTIVITY CASCADE
    # ======================================================================

    def _cancel_planned_activities(self, campaign):
        """
        Cancel all PLANNED and ON_HOLD activities linked to this campaign.

        Returns:
            int: number of activities cancelled
        """
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus

        pending = Activity.objects.filter(
            campaign=campaign,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
        )
        count = pending.update(
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
                CoreErrorMessages.OBJECT_NOT_FOUND
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