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
from app_modules.sequences.sequence_dispatcher import SequenceDispatcher

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

        Gating rules (sequence campaigns):
            - Step 1 activities (previous_activity IS NULL) are always visible.
            - Steps 2..N are visible only when their previous activity is COMPLETED
            AND the min_delay_days since its completion has elapsed.

        Priority scoring:
            - Activity type weight
            - Sequence position (earlier step → higher score)
            - Callback boost
            - Overdue penalty
        """
        limit = limit or CONFIG.limits.playlist_limit
        today = timezone.now().date()

        # ------------------------------------------------------------------
        # Base queryset: PLANNED activities for this campaign
        # ------------------------------------------------------------------
        queryset = Activity.objects.filter(
            campaign=campaign,
            status=ActivityStatus.PLANNED,
        ).select_related(
            'account',
            'owner',
            'campaign_account',
            'previous_activity',          # needed for gating check
        ).prefetch_related(
            'contacts',
        )

        if executor:
            queryset = queryset.filter(owner=executor)

        # No gating filter — all PLANNED activities are returned.
        # The frontend splits them into "due now" vs "upcoming" sections.
        # Gating (previous step must be COMPLETED + min_delay elapsed) is
        # enforced separately when an activity is actually opened/executed.

        total_count = queryset.count()

        # ------------------------------------------------------------------
        # Fetch batch for Python-side scoring
        # ------------------------------------------------------------------
        activities = list(queryset[:CONFIG.limits.queue_batch_size])

        # ------------------------------------------------------------------
        # Dynamic date recalculation — sequence campaigns only.
        #
        # Stored scheduled_date is stale the moment a rep doesn't complete
        # a step on time. We recompute from today forward:
        #
        #   Step 1 → always today  (never overdue by design)
        #   Step N → next_business_day(today + cumulative min_delay_days)
        #            where cumulative is the sum of delays from step 1 to N,
        #            assuming every prior step is completed today.
        # ------------------------------------------------------------------
        if campaign.sequence_type:
            activities = self._recalculate_scheduled_dates(activities, today)

        # ------------------------------------------------------------------
        # Score and sort
        # ------------------------------------------------------------------
        scored = [(a, self._calculate_priority(a)) for a in activities]
        scored.sort(key=lambda x: x[1], reverse=True)

        return {
            'activities': [item[0] for item in scored[:limit]],
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

        # Assign campaign_account FIRST — used in all branches below.
        campaign_account = activity.campaign_account
        next_activity = None

        # Complete the activity before handling outcome side-effects.
        activity.complete(outcome=outcome, notes=outcome_notes, user=self.user)

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
    
    def generate_activities_for_contact(self, campaign, campaign_account, contact):
        """
        Generate activities for a single contact added to an active campaign account.

        Handles both campaign types:
        - No sequence (CALL_LIST): creates one flat activity.
        - With sequence: creates all N chained steps, identical to
          the per-contact loop in _generate_for_account().

        Args:
            campaign: Campaign instance.
            campaign_account: CampaignAccount the contact was added to.
            contact: Contact to generate activities for.

        Returns:
            int: Number of activities created.
        """
        executor = self._get_executor(campaign, campaign_account)

        # --------------------------------------------------------------
        # No-sequence campaign: one flat activity
        # --------------------------------------------------------------
        if not campaign.sequence_type:
            self._create_activity(
                campaign=campaign,
                campaign_account=campaign_account,
                account=campaign_account.account,
                contact=contact,
                activity_type=ActivityType.CALL,
                position=1,
                owner=executor,
            )
            logger.info("campaign_activity_generated_for_contact", extra={
                'campaign_id': str(campaign.id),
                'campaign_account_id': str(campaign_account.id),
                'contact_id': str(contact.id),
                'created_count': 1,
            })
            return 1

        # --------------------------------------------------------------
        # Sequence campaign: generate all steps, chained
        # --------------------------------------------------------------
        has_phone = bool(getattr(contact, 'phone_number', None))
        has_email = bool(getattr(contact, 'email', None))
        has_linkedin = bool(getattr(contact, 'linkedin_url', None))

        try:
            sequence_dict, variant_name = SequenceDispatcher.get_sequence_with_variant(
                sequence_type=campaign.sequence_type,
                has_phone=has_phone,
                has_email=has_email,
                has_linkedin=has_linkedin,
            )
        except ValueError:
            logger.warning("sequence_type_invalid_for_contact", extra={
                'campaign_id': str(campaign.id),
                'sequence_type': campaign.sequence_type,
                'contact_id': str(contact.id),
            })
            return 0

        created = 0
        previous_activity = None
        cumulative_delay = 0
        for step_number, step_config in sequence_dict.items():
            cumulative_delay += step_config.get('min_delay', 0)
            step_date = self._next_business_day(
                    campaign.start_date + timedelta(days=cumulative_delay)
                )
            activity = self._create_activity(
                campaign=campaign,
                campaign_account=campaign_account,
                account=campaign_account.account,
                contact=contact,
                activity_type=step_config['type'],
                position=step_number,
                owner=executor,
                step_config=step_config,
                sequence_variant=variant_name,
                previous_activity=previous_activity,
                scheduled_date=step_date,
            )
            if previous_activity is not None:
                previous_activity.next_activity = activity
                previous_activity.save(user=self.user, client_id=self.client_id)

            previous_activity = activity
            created += 1

        logger.info("campaign_activities_generated_for_contact", extra={
            'campaign_id': str(campaign.id),
            'campaign_account_id': str(campaign_account.id),
            'contact_id': str(contact.id),
            'created_count': created,
            'variant': variant_name,
        })

        return created
    
    def delete_activities_for_contact(self, campaign, campaign_account, contact):
        """
        Delete all PLANNED activities for a specific contact within a campaign account.

        Called when a contact is removed from a CampaignAccount's target_contacts.
        Repairs the previous_activity/next_activity chain before deletion so that
        remaining activities stay correctly linked.

        Activities that are COMPLETED or IN_PROGRESS are left untouched.

        Args:
            campaign: Campaign instance (kept for API symmetry with generate_).
            campaign_account: CampaignAccount the contact is being removed from.
            contact: Contact being removed.
        """
        planned_activities = Activity.objects.filter(
            campaign_account=campaign_account,
            contacts=contact,
            status=ActivityStatus.PLANNED,
        ).select_related('previous_activity', 'next_activity')

        if not planned_activities.exists():
            return

        activity_ids = []

        for activity in planned_activities:
            prev_act = activity.previous_activity
            next_act = activity.next_activity

            # Reconnect the chain around this activity
            if prev_act and prev_act.id not in activity_ids:
                prev_act.next_activity = next_act
                prev_act.save(user=self.user, client_id=self.client_id)

            if next_act and next_act.id not in activity_ids:
                next_act.previous_activity = prev_act
                next_act.save(user=self.user, client_id=self.client_id)

            activity_ids.append(activity.id)

        deleted_count, _ = Activity.objects.filter(id__in=activity_ids).delete()

        logger.info("campaign_activities_deleted_for_contact", extra={
            'campaign_id': str(campaign.id),
            'campaign_account_id': str(campaign_account.id),
            'contact_id': str(contact.id),
            'deleted_count': deleted_count,
        })

    # ======================================================================
    # PRIVATE — ACTIVITY GENERATION PER ACCOUNT
    # ======================================================================

    def _generate_for_account(self, campaign, campaign_account, activity_type):
        """
        Generate activities for a single CampaignAccount.

        - No sequence_type (CALL_LIST): one activity per contact (legacy behavior).
        - With sequence_type: generates all N steps per contact, chained via
        previous_activity / next_activity FKs.
        """
        contacts = self._extract_contacts(campaign_account)
        executor = self._get_executor(campaign, campaign_account)

        # ------------------------------------------------------------------
        # No-sequence campaign (e.g. CALL_LIST): one flat activity per contact
        # ------------------------------------------------------------------
        if not campaign.sequence_type:
            if not contacts:
                self._create_activity(
                    campaign=campaign,
                    campaign_account=campaign_account,
                    account=campaign_account.account,
                    contact=None,
                    activity_type=activity_type,
                    position=1,
                    owner=executor,
                )
                return 1

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

        # ------------------------------------------------------------------
        # Sequence campaign: generate all steps per contact, chained
        # ------------------------------------------------------------------
        if not contacts:
            # Cannot determine channel flags without a contact — skip silently.
            return 0

        created = 0
        for contact in contacts:
            has_phone = bool(getattr(contact, 'phone_number', None))
            has_email = bool(getattr(contact, 'email', None))
            has_linkedin = bool(getattr(contact, 'linkedin_url', None))

            try:
                sequence_dict, variant_name = SequenceDispatcher.get_sequence_with_variant(
                    sequence_type=campaign.sequence_type,
                    has_phone=has_phone,
                    has_email=has_email,
                    has_linkedin=has_linkedin,
                )
            except ValueError:
                logger.warning("sequence_type_invalid_skipping_contact", extra={
                    'campaign_id': str(campaign.id),
                    'sequence_type': campaign.sequence_type,
                    'contact_id': str(contact.id),
                })
                continue

            previous_activity = None
            cumulative_delay = 0
            # Ensure the base date is itself a business day
            base_date = self._next_business_day(campaign.start_date)
            for step_number, step_config in sequence_dict.items():
                cumulative_delay += step_config.get('min_delay', 0)
                step_date = self._next_business_day(
                    base_date + timedelta(days=cumulative_delay)
                )
                activity = self._create_activity(
                    campaign=campaign,
                    campaign_account=campaign_account,
                    account=campaign_account.account,
                    contact=contact,
                    activity_type=step_config['type'],
                    position=step_number,
                    owner=executor,
                    step_config=step_config,
                    sequence_variant=variant_name,
                    previous_activity=previous_activity,
                    scheduled_date=step_date,
                )
                # Update the previous activity's next pointer now that we have the FK id.
                if previous_activity is not None:
                    previous_activity.next_activity = activity
                    previous_activity.save(user=self.user, client_id=self.client_id)

                previous_activity = activity
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
                .filter(opted_out=False)
                .select_related('standard_department')
            )

        # Base: all contacts for this account
        queryset = Contact.objects.filter(
            account=campaign_account.account,
            client_id=self.client_id,
            opted_out=False,
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
                         activity_type, position, owner=None,
                         step_config=None, sequence_variant=None,
                         previous_activity=None, scheduled_date=None):
        """
        Create a single Activity linked to a campaign.

        When step_config is provided (sequence campaigns), enriches the activity with:
            - min_delay_days   from step_config['min_delay']
            - sequence_variant
            - previous_activity FK (for gating logic in get_playlist)
            - description-based title prefix
        """
        owner = owner or self.user

        contact_name = ""
        if contact:
            contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()

        # Title format: {campaign name} - {contact name} - Step {N} - {scheduled date}
        # Gives the rep full context at a glance without opening the activity.
        campaign_name = campaign.name if campaign else ''
        step_date = scheduled_date or campaign.start_date if campaign else None
        date_str = step_date.strftime('%b %d') if step_date else ''

        if contact_name:
            title = f"{campaign_name} - {contact_name} - Step {position}"
        else:
            title = f"{campaign_name} - {account.company_name} - Step {position}"

        if date_str:
            title += f" - {date_str}"

        activity = Activity(
            title=title,
            activity_type=activity_type,
            status=ActivityStatus.PLANNED,
            account=account,
            owner=owner,
            campaign=campaign,
            campaign_account=campaign_account,
            sequence_position=position,
            scheduled_date=scheduled_date if scheduled_date is not None else campaign.start_date,
            due_date=campaign.end_date,
            # Sequence enrichment (populated only for sequence campaigns)
            min_delay_days=step_config.get('min_delay') if step_config else None,
            sequence_variant=sequence_variant,
            previous_activity=previous_activity,
        )
        activity.save(user=self.user, client_id=self.client_id)

        if contact:
            activity.contacts.add(contact)

        return activity
    
    def _next_business_day(self, date):
        """
        Shift a date forward to the nearest business day if it falls on a weekend.
        Handles chains: Saturday → Monday, Sunday → Monday.
        Applied to both start_date and each computed step_date.
        """
        while date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            date += timedelta(days=1)
        return date

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
    
    def _recalculate_scheduled_dates(self, activities, today):
        """
        Recompute scheduled_date for all PLANNED activities in a sequence.

        Rules:
            - Step 1 (previous_activity is None): always today. Never overdue.
            - Step N: next_business_day(today + cumulative min_delay_days)
              where cumulative = sum of min_delay_days from step 1 to step N,
              assuming all prior steps are completed today.

        Modifies scheduled_date in-place on each activity object (not saved to DB —
        display-only adjustment for playlist ordering and frontend rendering).
        """
        # Build a lookup: activity.id → activity
        by_id = {a.id: a for a in activities}

        # Walk each activity's chain upward to compute cumulative delay
        for activity in activities:
            cumulative_delay = self._cumulative_delay_from_root(activity, by_id)

            if cumulative_delay == 0:
                # Step 1 — always today, never overdue
                activity.scheduled_date = today
            else:
                activity.scheduled_date = self._next_business_day(
                    today + timedelta(days=cumulative_delay)
                )

        return activities

    def _cumulative_delay_from_root(self, activity, by_id, _visited=None):
        """
        Walk the previous_activity chain to sum min_delay_days from root to this step.

        Uses the in-memory by_id map (no extra DB queries).
        _visited guards against circular references.
        """
        if _visited is None:
            _visited = set()

        if activity.id in _visited:
            return 0
        _visited.add(activity.id)

        prev = activity.previous_activity
        if prev is None:
            # This is step 1 — own delay not counted (it starts at today)
            return 0

        # Try to resolve previous from in-memory map first
        prev_in_memory = by_id.get(prev.id)
        if prev_in_memory:
            return (activity.min_delay_days or 0) + self._cumulative_delay_from_root(
                prev_in_memory, by_id, _visited
            )

        # Previous step already completed (not in PLANNED list) — use its min_delay
        return activity.min_delay_days or 0

    # ======================================================================
    # PRIVATE — OUTCOME HANDLING
    # ======================================================================

    def _handle_outcome(self, campaign_account, activity, result_data):
        """
        Handle activity outcome and update CampaignAccount state.

        Sequence-aware logic:
            - Terminal outcomes (NOT_INTERESTED, WRONG_CONTACT…): cancel the entire
            remaining chain via _cancel_chain(activity).
            - Successful outcomes: let the gating in get_playlist() surface the next
            chained activity automatically — no manual followup created.
            - CALLBACK_REQUESTED: always creates a separate followup at the callback
            date (out-of-sequence, scheduled explicitly).
            - NO_ANSWER: increments counter and creates a retry followup if under
            threshold — also out-of-sequence extras on top of the chain.
            - next_activity_type (manual override on non-sequence campaigns): creates
            a followup only when no chain exists.

        Returns:
            Activity or None: the next activity to surface to the caller.
        """
        outcome = result_data.get('outcome', '')
        callback_date = result_data.get('callback_date')
        next_activity_type = result_data.get('next_activity_type')

        # ------------------------------------------------------------------
        # CALLBACK REQUESTED — always an explicit out-of-sequence followup
        # ------------------------------------------------------------------
        if callback_date:
            campaign_account.request_callback(
                callback_date=callback_date,
                user=self.user,
                notes=f"Callback from activity: {activity.title}",
            )
            return self._create_followup(
                activity,
                activity_type=next_activity_type or activity.activity_type,
                scheduled_date=callback_date,
            )

        if outcome == 'NO_ANSWER':
            campaign_account.increment_no_answer(user=self.user)
            return None

        # ------------------------------------------------------------------
        # TERMINAL OUTCOMES — stop the account and cancel remaining chain
        # ------------------------------------------------------------------
        terminal_outcomes = {
            'NOT_INTERESTED',
            'WRONG_CONTACT',
            'UNSUBSCRIBE_OPTOUT',
            'WRONG_EMAIL',
            'INVALID_PHONE_NUMBER',
        }
        if outcome in terminal_outcomes:
            campaign_account.mark_stopped(
                reason=f"Contact outcome: {outcome}",
                user=self.user,
            )
            self._cancel_chain(activity)
            return None

        # ------------------------------------------------------------------
        # SUCCESSFUL OUTCOMES — complete account, chain surfaces via gating
        # ------------------------------------------------------------------
        successful_outcomes = {'SUCCESSFUL', 'POSITIVE_RESPONSE', 'MEETING_SCHEDULED'}
        if outcome in successful_outcomes:
            campaign_account.mark_completed(
                notes=f"Successful: {outcome}",
                user=self.user,
            )
            # Chain is pre-created — get_playlist() will surface next_activity
            # automatically once previous_activity.status = COMPLETED.
            # No manual followup needed.
            return activity.next_activity if hasattr(activity, 'next_activity') else None

        # ------------------------------------------------------------------
        # DEFAULT — manual next_activity_type only on non-sequence campaigns
        # ------------------------------------------------------------------
        if next_activity_type and not activity.campaign.sequence_type:
            next_date = timezone.now().date() + timedelta(days=1)
            return self._create_followup(
                activity,
                activity_type=next_activity_type,
                scheduled_date=next_date,
            )

        return None
    
    def _cancel_chain(self, activity):
        """
        Cancel all remaining PLANNED activities in the chain after *activity*.

        Walks the next_activity linked list, collects IDs of PLANNED activities,
        and performs a single bulk update.  Activities already COMPLETED or
        CANCELLED are left untouched.

        Args:
            activity: The activity whose chain should be cancelled downstream.
        """
        ids_to_cancel = []
        current = getattr(activity, 'next_activity', None)

        while current is not None:
            if current.status == ActivityStatus.PLANNED:
                ids_to_cancel.append(current.id)
            current = getattr(current, 'next_activity', None)

        if not ids_to_cancel:
            return

        cancelled_count = Activity.objects.filter(
            id__in=ids_to_cancel,
        ).update(
            status=ActivityStatus.CANCELLED,
            outcome_notes="Chain cancelled: terminal outcome on predecessor",
            updated_at=timezone.now(),
        )

        logger.info("campaign_chain_cancelled", extra={
            'source_activity_id': str(activity.id),
            'cancelled_count': cancelled_count,
            'cancelled_ids': [str(aid) for aid in ids_to_cancel],
        })


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

        Scoring is additive. Higher score = appears earlier in playlist.

        Tiers (in order of dominance):
            1. Scheduled date gate:
               - Future activities (scheduled_date > today) receive a -10000 base penalty,
                 ensuring they always appear after every activity due today or overdue.
               - Within future activities, each additional day adds -10 pts
                 (tomorrow ranks above next week).

            2. Activity type weight:
               - CALL=20, MEETING=15, EMAIL=10, etc. (configured in CONFIG.priorities)
               - Multiplied by activity_type_weight factor.

            3. Sequence position bonus:
               - step_bonus / position → step 1 = full bonus, step 5 = 1/5 bonus.
               - Ensures earlier steps in a sequence surface before later ones.

            4. Callback boost:
               - +50 (× callback_weight) if the account is CALLBACK_PENDING.
               - These accounts have a committed follow-up date and take priority.

            5. Overdue bonus:
               - +overdue_penalty_per_day × days_overdue × overdue_weight.
               - Longer overdue = higher urgency.
        """

        score = 0
        today = timezone.now().date()
        weights = CONFIG.priorities.weights
        type_priorities = CONFIG.priorities.activity_type_priorities

        # Future activities are deprioritized below all activities due today.
        # A large penalty pushes them behind everything else regardless of type/position.
        if activity.scheduled_date and activity.scheduled_date > today:
            score -= 10000
            # Still score within future activities so same-day futures are ordered sensibly.
            days_future = (activity.scheduled_date - today).days
            score -= days_future * 10

        # Activity type score
        type_score = type_priorities.get(activity.activity_type, 1)
        score += type_score * weights.get('activity_type_weight', 0.5)

        # Sequence position: step 1 gets full bonus, later steps get proportionally less.
        # Formula: bonus / position  →  position 1 = 5pts, position 5 = 1pt, position 10 = 0.5pt
        if activity.sequence_position:
            step_bonus = CONFIG.priorities.sequence_step_priority_bonus
            score += (step_bonus / activity.sequence_position) * weights.get('step_weight', 1.0)

        # Callback boost — these accounts need attention first
        if (
            activity.campaign_account
            and activity.campaign_account.status == CampaignAccountStatus.CALLBACK_PENDING
        ):
            score += CONFIG.priorities.callback_priority_boost * weights.get('callback_weight', 2.0)
        
        # No-answer penalty — demotes CALL activities after failed attempts.
        # Each unanswered attempt pushes the activity further down the queue.
        # Uses no_answer_count from CampaignAccount (shared across all steps of the account).
        if (
            activity.activity_type == ActivityType.CALL
            and activity.campaign_account
            and activity.campaign_account.no_answer_count > 0
        ):
            score -= activity.campaign_account.no_answer_count * 50

        # Overdue bonus — longer overdue = higher urgency
        if activity.due_date:
            days_overdue = (today - activity.due_date).days
            if days_overdue > 0:
                score += (
                    days_overdue
                    * CONFIG.priorities.overdue_penalty_per_day
                    * weights.get('overdue_weight', 1.5)
                )

        return score