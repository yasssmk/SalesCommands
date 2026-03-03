# app_modules/campaigns/services/campaign_execution_service.py
"""
CampaignExecutionService — activity generation and queue management.

Responsibilities:
    - Generate activities from CampaignAccount entries (contacts extraction)
    - Build prioritized playlist for executors
    - Track activity generation per CampaignAccount
    - Handle callback scheduling and no-answer tracking

Follows legacy campaign_activity_service.py + campaign_queue_service.py
patterns, simplified for new CampaignAccount pivot architecture.
"""

from django.db import transaction
from django.db.models import Q, Count, F
from django.utils import timezone
from datetime import timedelta

from core.logging import get_logger
from core.logging.audit import audit_log
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityType, ActivityStatus
from app_modules.contacts.models import Contact

from ..models import (
    Campaign,
    CampaignStatus,
    CampaignAccount,
    CampaignAccountStatus,
    CampaignMember,
)
from ..config.settings import CONFIG

logger = get_logger(__name__)


class CampaignExecutionService:
    """
    Service for generating and managing campaign activities.

    Usage:
        service = CampaignExecutionService(user=request.user, client_id=client_id)
        result = service.generate_activities(campaign)
        playlist = service.get_playlist(campaign, executor=request.user)
    """

    def __init__(self, user, client_id):
        self.user = user
        self.client_id = str(client_id)

    # ======================================================================
    # PUBLIC — ACTIVITY GENERATION
    # ======================================================================

    @transaction.atomic
    def generate_activities(self, campaign, activity_type=None):
        """
        Generate activities for all eligible CampaignAccounts.

        Only generates for accounts that:
            - Are IN_PROGRESS
            - Have not yet had activities generated (activities_generated=False)

        Args:
            campaign: Campaign instance (must be ACTIVE)
            activity_type: Override activity type (default: CALL)

        Returns:
            dict: {
                'activities_created': int,
                'accounts_processed': int,
                'accounts_skipped': int,
                'errors': [str],
            }
        """
        # Validate campaign is active
        if campaign.status != CampaignStatus.ACTIVE:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_NOT_ACTIVE
            )

        default_type = activity_type or ActivityType.CALL

        # Get eligible accounts
        eligible_accounts = CampaignAccount.objects.filter(
            campaign=campaign,
            status=CampaignAccountStatus.IN_PROGRESS,
            activities_generated=False,
        ).select_related('account').prefetch_related(
            'target_contacts',
            'target_departments',
        )

        activities_created = 0
        accounts_processed = 0
        accounts_skipped = 0
        errors = []

        for ca in eligible_accounts:
            try:
                count = self._generate_for_account(campaign, ca, default_type)
                activities_created += count
                accounts_processed += 1

                # Mark as generated
                ca.mark_activities_generated(user=self.user)

            except Exception as e:
                accounts_skipped += 1
                errors.append(f"Account {ca.account_id}: {str(e)}")
                logger.warning("activity_generation_failed_for_account", extra={
                    'campaign_id': str(campaign.id),
                    'campaign_account_id': str(ca.id),
                    'error': str(e),
                })

        audit_log(
            event='campaign_activities_generated',
            action='create',
            actor_id=str(self.user.id),
            client_id=self.client_id,
            target_type='campaign',
            target_id=str(campaign.id),
            outcome='success',
            extra={
                'activities_created': activities_created,
                'accounts_processed': accounts_processed,
                'accounts_skipped': accounts_skipped,
            }
        )

        logger.info("campaign_activities_generated", extra={
            'campaign_id': str(campaign.id),
            'activities_created': activities_created,
            'accounts_processed': accounts_processed,
        })

        return {
            'activities_created': activities_created,
            'accounts_processed': accounts_processed,
            'accounts_skipped': accounts_skipped,
            'errors': errors,
        }

    # ======================================================================
    # PUBLIC — PLAYLIST (PRIORITIZED QUEUE)
    # ======================================================================

    def get_playlist(self, campaign, executor=None, limit=None):
        """
        Get prioritized activity playlist for a campaign.

        Priority scoring (from CONFIG.priorities):
            - Activity type weight (CALL=20, MEETING=15, EMAIL=10...)
            - Callback boost (+50 for callback-pending accounts)
            - Overdue penalty (+15 per overdue day)

        Args:
            campaign: Campaign instance
            executor: Optional User to filter by owner
            limit: Max activities to return (default: CONFIG playlist_limit)

        Returns:
            dict: {
                'activities': queryset,
                'total_count': int,
            }
        """
        limit = limit or CONFIG.limits.playlist_limit

        queryset = Activity.objects.filter(
            campaign=campaign,
            status=ActivityStatus.PLANNED,
        ).select_related(
            'account',
            'owner',
            'campaign_account',
        ).prefetch_related(
            'contacts',
        )

        # Filter by executor if provided
        if executor:
            queryset = queryset.filter(owner=executor)

        total_count = queryset.count()

        # Sort by priority (Python-side scoring for flexibility)
        activities = list(queryset[:CONFIG.limits.queue_batch_size])
        scored = [(a, self._calculate_priority(a)) for a in activities]
        scored.sort(key=lambda x: x[1], reverse=True)

        sorted_activities = [item[0] for item in scored[:limit]]

        return {
            'activities': sorted_activities,
            'total_count': total_count,
        }

    def get_playlist_for_executor(self, campaign, executor, limit=None):
        """
        Convenience wrapper for executor-specific playlist.

        Returns only activities owned by this executor.
        """
        return self.get_playlist(campaign, executor=executor, limit=limit)

    # ======================================================================
    # PUBLIC — ACTIVITY RESULT PROCESSING
    # ======================================================================

    def process_result(self, activity, result_data):
        """
        Process activity result and update CampaignAccount accordingly.

        Args:
            activity: Activity instance (must be linked to campaign)
            result_data: dict {
                'outcome': str (ActivityOutcome value),
                'outcome_notes': str,
                'callback_date': date (optional),
                'next_activity_type': str (optional),
            }

        Returns:
            dict: {
                'activity': Activity,
                'campaign_account': CampaignAccount or None,
                'next_activity': Activity or None,
            }
        """
        if not activity.campaign_id:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.EXECUTION_FAILED.format(
                    reason="Activity is not linked to a campaign"
                )
            )

        outcome = result_data.get('outcome')
        outcome_notes = result_data.get('outcome_notes')

        # Complete the activity
        activity.complete(outcome=outcome, notes=outcome_notes, user=self.user)

        # Update CampaignAccount based on outcome
        campaign_account = activity.campaign_account
        next_activity = None

        if campaign_account:
            next_activity = self._handle_outcome(
                campaign_account, activity, result_data
            )

        logger.info("campaign_activity_result_processed", extra={
            'campaign_id': str(activity.campaign_id),
            'activity_id': str(activity.id),
            'outcome': outcome,
            'has_next': next_activity is not None,
        })

        return {
            'activity': activity,
            'campaign_account': campaign_account,
            'next_activity': next_activity,
        }

    # ======================================================================
    # PRIVATE — ACTIVITY GENERATION PER ACCOUNT
    # ======================================================================

    def _generate_for_account(self, campaign, campaign_account, activity_type):
        """
        Generate activities for a single CampaignAccount.

        Logic:
            - Extract contacts (from target_contacts M2M, or fallback to account contacts)
            - Filter by target_departments if set
            - Create one Activity per contact
            - Assign to executor (round-robin from campaign executors)

        Returns:
            int: number of activities created
        """
        contacts = self._extract_contacts(campaign_account)

        if not contacts:
            # Create one account-level activity (no specific contact)
            self._create_activity(
                campaign=campaign,
                campaign_account=campaign_account,
                account=campaign_account.account,
                contact=None,
                activity_type=activity_type,
                position=1,
            )
            return 1

        # Determine executor
        executor = self._get_executor(campaign, campaign_account)

        created = 0
        for i, contact in enumerate(contacts, start=1):
            self._create_activity(
                campaign=campaign,
                campaign_account=campaign_account,
                account=campaign_account.account,
                contact=contact,
                activity_type=activity_type,
                position=i,
                owner=executor,
            )
            created += 1

        return created

    def _extract_contacts(self, campaign_account):
        """
        Extract contacts for a CampaignAccount.

        Priority:
            1. Explicit target_contacts (if set)
            2. Account contacts filtered by target_departments (if set)
            3. All account contacts

        Filters out contacts without phone/email (safety check from legacy).
        """
        # 1. Explicit target contacts
        if campaign_account.target_contacts.exists():
            return list(
                campaign_account.target_contacts
                .filter(is_active=True)
                .select_related('standard_department')
            )

        # Base: all contacts for this account
        queryset = Contact.objects.filter(
            account=campaign_account.account,
            client_id=self.client_id,
            is_active=True,
        ).select_related('standard_department')

        # 2. Filter by target departments if set
        if campaign_account.target_departments.exists():
            dept_ids = campaign_account.target_departments.values_list('id', flat=True)
            queryset = queryset.filter(standard_department_id__in=dept_ids)

        # Safety: exclude contacts with no reachable channel
        queryset = queryset.filter(
            Q(email__isnull=False) | Q(phone_number__isnull=False)
        ).exclude(
            Q(email='') & Q(phone_number='')
        )

        return list(queryset)

    def _create_activity(self, campaign, campaign_account, account, contact,
                         activity_type, position, owner=None):
        """Create a single Activity linked to campaign."""
        owner = owner or self.user

        # Build title
        contact_name = ""
        if contact:
            contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()

        title = f"{activity_type} - {account.company_name}"
        if contact_name:
            title += f" - {contact_name}"

        activity = Activity(
            title=title,
            activity_type=activity_type,
            status=ActivityStatus.PLANNED,
            account=account,
            owner=owner,
            campaign=campaign,
            campaign_account=campaign_account,
            sequence_position=position,
            scheduled_date=campaign.start_date,
            due_date=campaign.end_date,
        )
        activity.save(user=self.user, client_id=self.client_id)

        # Link contact via M2M
        if contact:
            activity.contacts.add(contact)

        return activity

    # ======================================================================
    # PRIVATE — EXECUTOR ASSIGNMENT
    # ======================================================================

    def _get_executor(self, campaign, campaign_account):
        """
        Determine the executor for activities on this account.

        Logic:
            1. Account owner if they are EXECUTOR or RECEIVER on campaign
            2. First EXECUTOR on campaign
            3. Fallback: campaign primary owner
        """
        # Try account owner
        account_owner = getattr(campaign_account.account, 'account_owner', None)
        if account_owner:
            is_campaign_member = CampaignMember.objects.filter(
                campaign=campaign,
                user=account_owner,
                role__in=[
                    CampaignMember.MemberRole.EXECUTOR,
                    CampaignMember.MemberRole.RECEIVER,
                ],
            ).exists()
            if is_campaign_member:
                return account_owner

        # First executor
        first_executor = CampaignMember.objects.filter(
            campaign=campaign,
            role=CampaignMember.MemberRole.EXECUTOR,
        ).select_related('user').first()
        if first_executor:
            return first_executor.user

        # Fallback: primary owner
        primary_owner = campaign.get_primary_owner()
        return primary_owner or self.user

    # ======================================================================
    # PRIVATE — OUTCOME HANDLING
    # ======================================================================

    def _handle_outcome(self, campaign_account, activity, result_data):
        """
        Handle activity outcome and update CampaignAccount state.

        Returns:
            Activity or None: next activity if one was created
        """
        outcome = result_data.get('outcome', '')
        callback_date = result_data.get('callback_date')
        next_activity_type = result_data.get('next_activity_type')

        # Callback requested
        if callback_date:
            campaign_account.request_callback(
                callback_date=callback_date,
                user=self.user,
                notes=f"Callback from activity: {activity.title}",
            )
            # Create follow-up activity
            return self._create_followup(
                activity,
                activity_type=next_activity_type or activity.activity_type,
                scheduled_date=callback_date,
            )

        # No answer — increment counter
        if outcome in CONFIG.validation.call_results and outcome == 'NO_ANSWER':
            campaign_account.increment_no_answer(user=self.user)

            # Auto-retry if under threshold (3 attempts)
            if campaign_account.no_answer_count < 3:
                retry_date = timezone.now().date() + timedelta(days=1)
                return self._create_followup(
                    activity,
                    activity_type=activity.activity_type,
                    scheduled_date=retry_date,
                )

        # Not interested or terminal outcome → complete account
        terminal_outcomes = {'NOT_INTERESTED', 'UNSUBSCRIBE_OPTOUT', 'WRONG_EMAIL', 'INVALID_PHONE_NUMBER'}
        if outcome in terminal_outcomes:
            campaign_account.mark_stopped(
                reason=f"Contact outcome: {outcome}",
                user=self.user,
            )
            return None

        # Successful outcome → complete account
        successful_outcomes = {'SUCCESSFUL', 'POSITIVE_RESPONSE'}
        if outcome in successful_outcomes:
            campaign_account.mark_completed(
                notes=f"Successful: {outcome}",
                user=self.user,
            )
            return None

        # Default: create next activity if next_activity_type specified
        if next_activity_type:
            next_date = timezone.now().date() + timedelta(days=1)
            return self._create_followup(
                activity,
                activity_type=next_activity_type,
                scheduled_date=next_date,
            )

        return None

    def _create_followup(self, source_activity, activity_type, scheduled_date):
        """
        Create a follow-up activity from a completed one.

        Copies campaign context (campaign, campaign_account, account, contacts)
        and increments sequence_position.
        """
        position = (source_activity.sequence_position or 0) + 1

        followup = Activity(
            title=f"{activity_type} - {source_activity.account.company_name} (Follow-up)",
            activity_type=activity_type,
            status=ActivityStatus.PLANNED,
            account=source_activity.account,
            owner=source_activity.owner,
            campaign=source_activity.campaign,
            campaign_account=source_activity.campaign_account,
            sequence_position=position,
            scheduled_date=scheduled_date,
            due_date=source_activity.campaign.end_date if source_activity.campaign else None,
        )
        followup.save(user=self.user, client_id=self.client_id)

        # Copy contacts from source
        contacts = source_activity.contacts.all()
        if contacts.exists():
            followup.contacts.set(contacts)

        logger.info("campaign_followup_created", extra={
            'source_activity_id': str(source_activity.id),
            'followup_activity_id': str(followup.id),
            'activity_type': activity_type,
            'scheduled_date': str(scheduled_date),
        })

        return followup

    # ======================================================================
    # PRIVATE — PRIORITY SCORING
    # ======================================================================

    def _calculate_priority(self, activity):
        """
        Calculate priority score for playlist ordering.

        Factors (from CONFIG.priorities):
            - Activity type weight (CALL=20, MEETING=15, EMAIL=10...)
            - Callback boost (+50 if account is CALLBACK_PENDING)
            - Overdue penalty (+15 per day overdue)
        """
        score = 0
        weights = CONFIG.priorities.weights
        type_priorities = CONFIG.priorities.activity_type_priorities

        # Activity type score
        type_score = type_priorities.get(activity.activity_type, 1)
        score += type_score * weights.get('activity_type_weight', 0.5)

        # Sequence position (lower position = higher priority)
        if activity.sequence_position:
            step_bonus = CONFIG.priorities.sequence_step_priority_bonus
            score += (step_bonus / activity.sequence_position) * weights.get('step_weight', 1.0)

        # Callback boost
        if activity.campaign_account and activity.campaign_account.status == CampaignAccountStatus.CALLBACK_PENDING:
            score += CONFIG.priorities.callback_priority_boost * weights.get('callback_weight', 2.0)

        # Overdue penalty (positive = higher priority)
        if activity.due_date:
            days_overdue = (timezone.now().date() - activity.due_date).days
            if days_overdue > 0:
                score += days_overdue * CONFIG.priorities.overdue_penalty_per_day * weights.get('overdue_weight', 1.5)

        return score