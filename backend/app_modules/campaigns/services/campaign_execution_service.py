# app_modules/campaigns/services/campaign_execution_service.py
"""
CampaignExecutionService — activity generation and queue management.

Responsibilities:
    - Generate activities from CampaignAccount entries (one CampaignContact per contact)
    - Build prioritized playlist for executors
    - Track activity generation per CampaignContact
    - Handle callback scheduling and no-answer tracking at contact scope

Architecture:
    Campaign → CampaignAccount → CampaignContact → Activity (campaign_contact FK)
"""

from django.db import transaction
from django.db.models import Count, Prefetch, Q
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
    CampaignContact,
    CampaignContactStatus,
    FINAL_CONTACT_STATES,
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

        For each IN_PROGRESS account, resolves contacts, creates a
        CampaignContact row per contact (if not exists), and generates
        the activity chain linked to that CampaignContact.

        Only processes CampaignAccounts that still have contacts without
        activities_generated=True.
        """
        if campaign.status != CampaignStatus.ACTIVE:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_NOT_ACTIVE
            )

        default_type = activity_type or ActivityType.CALL

        eligible_accounts = CampaignAccount.objects.filter(
            campaign=campaign,
            status=CampaignAccountStatus.IN_PROGRESS,
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

    def generate_activities_for_contact(self, campaign, campaign_account, contact):
        """
        Generate activities for a single contact added to an active campaign account.

        Creates or retrieves the CampaignContact row, then generates the chain.

        Returns:
            int: Number of activities created.
        """
        campaign_contact, _ = CampaignContact.objects.get_or_create(
            campaign_account=campaign_account,
            contact=contact,
            defaults={
                'client_id': self.client_id,
                'status': CampaignContactStatus.IN_PROGRESS,
            },
        )

        if campaign_contact.activities_generated:
            return 0

        executor = self._get_executor(campaign, campaign_account)

        if not campaign.sequence_type:
            self._create_activity(
                campaign=campaign,
                campaign_account=campaign_account,
                campaign_contact=campaign_contact,
                account=campaign_account.account,
                contact=contact,
                activity_type=ActivityType.CALL,
                position=1,
                owner=executor,
            )
            campaign_contact.mark_activities_generated(user=self.user)
            return 1

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
                'contact_id': str(contact.id),
            })
            return 0

        created = 0
        previous_activity = None
        cumulative_delay = 0
        # TARGETED: sequence starts from today (enrollment date).
        # OUTBOUND: sequence starts from campaign planned start date.
        if campaign.is_targeted:
            base_date = self._next_business_day(timezone.now().date())
        else:
            base_date = self._next_business_day(campaign.planned_start_date)

        for step_number, step_config in sequence_dict.items():
            cumulative_delay += step_config.get('min_delay', 0)
            step_date = self._next_business_day(base_date + timedelta(days=cumulative_delay))
            activity = self._create_activity(
                campaign=campaign,
                campaign_account=campaign_account,
                campaign_contact=campaign_contact,
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

        campaign_contact.mark_activities_generated(user=self.user)
        return created

    def delete_activities_for_contact(self, campaign, campaign_account, contact):
        """
        Delete all PLANNED activities for a contact removed from a campaign account.
        Also deletes the CampaignContact row if it exists.
        """
        try:
            cc = CampaignContact.objects.get(
                campaign_account=campaign_account,
                contact=contact,
            )
            Activity.objects.filter(
                campaign=campaign,
                campaign_contact=cc,
                status=ActivityStatus.PLANNED,
            ).delete()
            cc.delete()
        except CampaignContact.DoesNotExist:
            pass

    # ======================================================================
    # PUBLIC — PLAYLIST (PRIORITIZED QUEUE)
    # ======================================================================

    def get_playlist(self, campaign, executor=None, limit=None):
        """
        Get prioritized activity playlist for a campaign.

        Gating rules (sequence campaigns):
            - Step 1 (previous_activity IS NULL): always visible.
            - Steps 2..N: visible when previous activity is COMPLETED
              AND min_delay_days has elapsed.

        Priority scoring:
            - Activity type weight
            - Sequence position (earlier = higher score)
            - Callback boost
            - Overdue penalty
        """
        limit = limit or CONFIG.limits.playlist_limit
        today = timezone.now().date()

        queryset = Activity.objects.filter(
            campaign=campaign,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
        ).select_related(
            'account',
            'owner',
            'campaign_contact',
            'campaign_contact__campaign_account',
            'previous_activity',
            'decision_step',
        ).prefetch_related(
            Prefetch(
                'contacts',
                queryset=Contact.objects.select_related('standard_department'),
            ),
        ).annotate(
            _contacts_count=Count('contacts'),
        )

        if executor:
            queryset = queryset.filter(owner=executor)

        # Single query — fetch batch then derive total from len to avoid
        # a separate COUNT(*) round-trip.
        activities = list(queryset[:CONFIG.limits.queue_batch_size])
        total_count = len(activities)

        if campaign.sequence_type:
            # Exclude ON_HOLD from date recalculation — their date is irrelevant
            planned_only = [a for a in activities if a.status == ActivityStatus.PLANNED]
            on_hold = [a for a in activities if a.status == ActivityStatus.ON_HOLD]
            planned_only = self._recalculate_scheduled_dates(planned_only, today)
            activities = planned_only + on_hold

        scored = [(a, self._calculate_priority(a)) for a in activities]
        scored.sort(key=lambda x: x[1], reverse=True)

        return {
            'activities': [item[0] for item in scored[:limit]],
            'total_count': total_count,
        }

    def get_playlist_for_executor(self, campaign, executor, limit=None):
        """Convenience wrapper — executor-scoped playlist."""
        return self.get_playlist(campaign, executor=executor, limit=limit)

    # ======================================================================
    # PUBLIC — ACTIVITY RESULT PROCESSING
    # ======================================================================

    def process_result(self, activity, result_data):
        """
        Process activity result and update CampaignContact (and account) accordingly.

        Args:
            activity: Activity instance linked to a campaign
            result_data: dict {
                'outcome': str,
                'outcome_notes': str,
                'callback_date': date (optional),
                'callback_time': str HH:MM (optional),
                'next_activity_type': str (optional),
            }

        Returns:
            dict: {activity, campaign_contact, campaign_account, next_activity}
        """
        if not activity.campaign_id:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.EXECUTION_FAILED.format(
                    reason="Activity is not linked to a campaign"
                )
            )

        outcome = result_data.get('outcome')
        outcome_notes = result_data.get('outcome_notes')

        campaign_contact = activity.campaign_contact
        campaign_account = activity.campaign_account
        next_activity = None

        activity.complete(outcome=outcome, notes=outcome_notes, user=self.user)

        if campaign_contact:
            next_activity = self._handle_outcome(campaign_contact, activity, result_data)

        logger.info("campaign_activity_result_processed", extra={
            'campaign_id': str(activity.campaign_id),
            'activity_id': str(activity.id),
            'outcome': outcome,
            'has_next': next_activity is not None,
        })

        return {
            'activity': activity,
            'campaign_contact': campaign_contact,
            'campaign_account': campaign_account,
            'next_activity': next_activity,
        }

    # ======================================================================
    # PRIVATE — GENERATION HELPERS
    # ======================================================================

    def _generate_for_account(self, campaign, campaign_account, activity_type):
        """
        Generate activities for all contacts in a CampaignAccount.

        Creates one CampaignContact per contact (get_or_create),
        skips contacts that already have activities_generated=True.
        """
        contacts = self._extract_contacts(campaign_account)
        executor = self._get_executor(campaign, campaign_account)

        if not campaign.sequence_type:
            if not contacts:
                cc, _ = CampaignContact.objects.get_or_create(
                    campaign_account=campaign_account,
                    contact=None,
                    defaults={
                        'client_id': self.client_id,
                        'status': CampaignContactStatus.IN_PROGRESS,
                    },
                )
                if not cc.activities_generated:
                    self._create_activity(
                        campaign=campaign,
                        campaign_account=campaign_account,
                        campaign_contact=cc,
                        account=campaign_account.account,
                        contact=None,
                        activity_type=activity_type,
                        position=1,
                        owner=executor,
                    )
                    cc.mark_activities_generated(user=self.user)
                return 1

            created = 0
            for i, contact in enumerate(contacts, start=1):
                cc, _ = CampaignContact.objects.get_or_create(
                    campaign_account=campaign_account,
                    contact=contact,
                    defaults={
                        'client_id': self.client_id,
                        'status': CampaignContactStatus.IN_PROGRESS,
                    },
                )
                if cc.activities_generated:
                    continue
                self._create_activity(
                    campaign=campaign,
                    campaign_account=campaign_account,
                    campaign_contact=cc,
                    account=campaign_account.account,
                    contact=contact,
                    activity_type=activity_type,
                    position=i,
                    owner=executor,
                )
                cc.mark_activities_generated(user=self.user)
                created += 1
            return created

        # Sequence campaign
        if not contacts:
            return 0

        created = 0
        for contact in contacts:
            cc, _ = CampaignContact.objects.get_or_create(
                campaign_account=campaign_account,
                contact=contact,
                defaults={
                    'client_id': self.client_id,
                    'status': CampaignContactStatus.IN_PROGRESS,
                },
            )
            if cc.activities_generated:
                continue

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
                    'contact_id': str(contact.id),
                })
                continue

            previous_activity = None
            cumulative_delay = 0
            
            # TARGETED: sequence starts from enrollment date (today).
            # OUTBOUND: sequence starts from campaign planned start date.
            if campaign.is_targeted:
                base_date = self._next_business_day(timezone.now().date())
            else:
                base_date = self._next_business_day(campaign.planned_start_date)

            for step_number, step_config in sequence_dict.items():
                cumulative_delay += step_config.get('min_delay', 0)
                step_date = self._next_business_day(
                    base_date + timedelta(days=cumulative_delay)
                )
                activity = self._create_activity(
                    campaign=campaign,
                    campaign_account=campaign_account,
                    campaign_contact=cc,
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

            cc.mark_activities_generated(user=self.user)

        return created

    def _extract_contacts(self, campaign_account):
        """
        Extract contacts for a CampaignAccount.

        Priority:
            1. Explicit target_contacts (if set)
            2. Account contacts filtered by target_departments (if set)
            3. All account contacts

        Excludes opted-out contacts and those with no reachable channel.
        """
        if campaign_account.target_contacts.exists():
            return list(
                campaign_account.target_contacts
                .filter(opted_out=False)
                .select_related('standard_department')
            )

        queryset = Contact.objects.filter(
            account=campaign_account.account,
            client_id=self.client_id,
            opted_out=False,
        ).select_related('standard_department')

        if campaign_account.target_departments.exists():
            dept_ids = campaign_account.target_departments.values_list('id', flat=True)
            queryset = queryset.filter(standard_department_id__in=dept_ids)

        queryset = queryset.filter(
            Q(email__isnull=False) | Q(phone_number__isnull=False)
        ).exclude(
            Q(email='') & Q(phone_number='')
        )

        return list(queryset)

    def _create_activity(self, campaign, campaign_account, campaign_contact,
                         account, contact, activity_type, position, owner=None,
                         step_config=None, sequence_variant=None,
                         previous_activity=None, scheduled_date=None):
        """
        Create a single Activity linked to a campaign_contact.
        """
        owner = owner or self.user

        contact_name = ""
        if contact:
            contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()

        if step_config:
            step_label = step_config.get('description', f'Step {position}')
            date_str = str(scheduled_date) if scheduled_date else ''
            title = f"{campaign.name} — {contact_name} — {step_label} — {date_str}".strip(' —')
        else:
            title = f"{campaign.name} — {contact_name}".strip(' —')

        activity = Activity(
            title=title,
            activity_type=activity_type,
            status=ActivityStatus.PLANNED,
            account=account,
            owner=owner,
            campaign=campaign,
            campaign_account=campaign_account,
            campaign_contact=campaign_contact,
            sequence_position=position,
            scheduled_date=scheduled_date or campaign.planned_start_date,
            due_date=campaign.planned_end_date,
            previous_activity=previous_activity,
            min_delay_days=step_config.get('min_delay') if step_config else None,
            sequence_variant=sequence_variant,
            description=step_config.get('description', '') if step_config else '',
        )
        activity.save(user=self.user, client_id=self.client_id)

        if contact:
            activity.contacts.add(contact)

        return activity

    # ======================================================================
    # PRIVATE — OUTCOME HANDLING
    # ======================================================================

    def _handle_outcome(self, campaign_contact, activity, result_data):
        """
        Handle activity outcome and update CampaignContact state.

        Scoping rules:
            - CALLBACK / NO_ANSWER / TERMINAL → contact scope only
            - SUCCESSFUL → contact COMPLETED, then check if account is done
        """
        outcome = result_data.get('outcome', '')
        callback_date = result_data.get('callback_date')
        callback_time = result_data.get('callback_time')
        next_activity_type = result_data.get('next_activity_type')
        campaign_account = campaign_contact.campaign_account

        # ------------------------------------------------------------------
        # CALLBACK REQUESTED
        # ------------------------------------------------------------------
        if callback_date:
            contact = activity.contacts.first()
            contact_name = (
                f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                if contact else "Contact"
            )

            campaign_contact.request_callback(
                callback_date=callback_date,
                user=self.user,
                notes=f"Callback from activity: {activity.title}",
            )
            return self._create_followup(
                activity,
                campaign_contact=campaign_contact,
                title=f"Callback — {contact_name}",
                activity_type=next_activity_type or activity.activity_type,
                scheduled_date=callback_date,
                scheduled_time=callback_time,
                is_callback_followup=True,
            )


        # ------------------------------------------------------------------
        # TERMINAL OUTCOMES — stop contact, cancel its chain
        # ------------------------------------------------------------------
        terminal_outcomes = {
            'NOT_INTERESTED',
            'WRONG_CONTACT',
            'UNSUBSCRIBE_OPTOUT',
            'WRONG_EMAIL',
            'INVALID_PHONE_NUMBER',
        }
        if outcome in terminal_outcomes:
            campaign_contact.mark_stopped(
                user=self.user,
                notes=f"Terminal outcome: {outcome}",
            )
            self._cancel_chain_for_contact(campaign_contact)
            self._check_account_completion(campaign_account)
            return None

        # ------------------------------------------------------------------
        # SUCCESSFUL OUTCOMES — complete contact + possibly account
        # ------------------------------------------------------------------
        successful_outcomes = {'SUCCESSFUL', 'POSITIVE_RESPONSE', 'MEETING_SCHEDULED'}
        if outcome in successful_outcomes:
            campaign_contact.mark_completed(
                user=self.user,
                notes=f"Successful: {outcome}",
            )
            # Cancel remaining PLANNED activities for this contact
            self._cancel_chain_for_contact(campaign_contact)
            # Cancel remaining contacts on the same account
            self._cancel_all_contacts_for_account(campaign_account, exclude=campaign_contact)
            self._check_account_completion(campaign_account)
            return None

        # ------------------------------------------------------------------
        # DEFAULT — manual followup on non-sequence campaigns
        # ------------------------------------------------------------------
        if next_activity_type and not activity.campaign.sequence_type:
            next_date = timezone.now().date() + timedelta(days=1)
            return self._create_followup(
                activity,
                campaign_contact=campaign_contact,
                activity_type=next_activity_type,
                scheduled_date=next_date,
            )

        return None

    def _cancel_chain_for_contact(self, campaign_contact):
        """
        Cancel all PLANNED activities for a given CampaignContact.
        Used for terminal outcomes — scoped to contact only.
        """
        cancelled = Activity.objects.filter(
            campaign_contact=campaign_contact,
            status=ActivityStatus.PLANNED,
        ).update(
            status=ActivityStatus.CANCELLED,
            outcome_notes="Chain cancelled: terminal outcome on contact",
            updated_at=timezone.now(),
        )
        logger.info("campaign_contact_chain_cancelled", extra={
            'campaign_contact_id': str(campaign_contact.id),
            'cancelled_count': cancelled,
        })

    def _cancel_all_contacts_for_account(self, campaign_account, exclude=None):
        """
        Cancel PLANNED activities for all contacts of an account except one.
        Used after a successful outcome — clears sibling contacts' chains.
        """
        qs = CampaignContact.objects.filter(
            campaign_account=campaign_account,
        ).exclude(status__in=FINAL_CONTACT_STATES)

        if exclude:
            qs = qs.exclude(id=exclude.id)

        for cc in qs:
            cc.mark_stopped(user=self.user, notes="Sibling contact succeeded")
            self._cancel_chain_for_contact(cc)

    def _check_account_completion(self, campaign_account):
        """
        After a contact reaches a final state, check if the whole account is done.
        If all contacts are final → mark account COMPLETED or STOPPED accordingly.
        """
        if not campaign_account.all_contacts_done():
            return

        all_contacts = campaign_account.campaign_contacts.all()
        any_completed = all_contacts.filter(
            status=CampaignContactStatus.COMPLETED
        ).exists()

        if any_completed:
            if campaign_account.status not in (
                CampaignAccountStatus.COMPLETED,
                CampaignAccountStatus.STOPPED,
            ):
                campaign_account.mark_completed(
                    user=self.user,
                    notes="All contacts resolved — at least one successful",
                )
        else:
            if campaign_account.status not in (
                CampaignAccountStatus.COMPLETED,
                CampaignAccountStatus.STOPPED,
            ):
                campaign_account.mark_stopped(
                    user=self.user,
                    notes="All contacts stopped — no successful outcome",
                )

    def _cancel_chain(self, activity):
        """
        Cancel remaining PLANNED activities after *activity* via linked list.
        Kept for backward compat — prefer _cancel_chain_for_contact() when possible.
        """
        ids_to_cancel = []
        current = getattr(activity, 'next_activity', None)
        while current is not None:
            if current.status == ActivityStatus.PLANNED:
                ids_to_cancel.append(current.id)
            current = getattr(current, 'next_activity', None)

        if not ids_to_cancel:
            return

        Activity.objects.filter(id__in=ids_to_cancel).update(
            status=ActivityStatus.CANCELLED,
            outcome_notes="Chain cancelled: terminal outcome on predecessor",
            updated_at=timezone.now(),
        )

    def _create_followup(self, source_activity, campaign_contact,
                         activity_type=None, scheduled_date=None,
                         scheduled_time=None, is_callback_followup=False,
                         title=None):
        """
        Create a follow-up activity from a completed one.
        Copies campaign context and links to the same CampaignContact.
        """
        position = (source_activity.sequence_position or 0) + 1
        activity_type = activity_type or source_activity.activity_type

        if not title:
            title = f"{activity_type} — {source_activity.account.company_name} (Follow-up)"

        followup = Activity(
            title=title,
            activity_type=activity_type,
            status=ActivityStatus.PLANNED,
            account=source_activity.account,
            owner=source_activity.owner,
            campaign=source_activity.campaign,
            campaign_account=source_activity.campaign_account,
            campaign_contact=campaign_contact,
            sequence_position=position,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            due_date=(
                source_activity.campaign.planned_end_date
                if source_activity.campaign else None
            ),
            is_callback_followup=is_callback_followup,
        )
        followup.save(user=self.user, client_id=self.client_id)

        contacts = source_activity.contacts.all()
        if contacts.exists():
            followup.contacts.set(contacts)

        logger.info("campaign_followup_created", extra={
            'source_activity_id': str(source_activity.id),
            'followup_id': str(followup.id),
            'is_callback_followup': is_callback_followup,
            'scheduled_date': str(scheduled_date),
        })

        return followup

    # ======================================================================
    # PRIVATE — SCHEDULED DATE RECALCULATION
    # ======================================================================

    def _recalculate_scheduled_dates(self, activities, today):
        """
        Recompute scheduled_date dynamically (in-memory, not saved to DB).

        Gating (sequence campaigns):
            - Step 1 (no previous_activity): always eligible.
            - Steps 2..N: eligible only when the immediate previous activity
            is COMPLETED. If not yet eligible, scheduled_date is pushed to
            tomorrow so the activity surfaces in UPCOMING, not TODAY.

        Base date per eligible activity:
            - CALLBACK_PENDING contact → base = campaign_contact.callback_date
            - Otherwise → base = today
        """
        by_id = {a.id: a for a in activities}

        for activity in activities:
            prev = activity.previous_activity

            # --- Sequence gate: immediate predecessor must be COMPLETED ---
            if prev is not None:
                # Prefer the in-memory instance (already fetched) over the
                # select_related stub to get the freshest status.
                prev_resolved = by_id.get(prev.id, prev)
                if prev_resolved.status != ActivityStatus.COMPLETED:
                    # Not yet eligible — ensure date is future so the frontend
                    # places this activity in UPCOMING, not TODAY.
                    if not activity.scheduled_date or activity.scheduled_date <= today:
                        activity.scheduled_date = today + timedelta(days=1)
                    continue

            # --- Eligible: compute base date ---
            cc = activity.campaign_contact
            if (
                cc is not None
                and getattr(cc, 'status', None) == CampaignContactStatus.CALLBACK_PENDING
                and cc.callback_date is not None
            ):
                base_date = cc.callback_date
            else:
                base_date = today

            cumulative_delay = self._cumulative_delay_from_root(activity, by_id)

            if cumulative_delay == 0:
                activity.scheduled_date = base_date
            else:
                activity.scheduled_date = self._next_business_day(
                    base_date + timedelta(days=cumulative_delay)
                )

        return activities

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

        prev_in_memory = by_id.get(prev.id)
        if prev_in_memory:
            return (activity.min_delay_days or 0) + self._cumulative_delay_from_root(
                prev_in_memory, by_id, _visited
            )

        return activity.min_delay_days or 0

    # ======================================================================
    # PRIVATE — PRIORITY SCORING
    # ======================================================================

    def _calculate_priority(self, activity):
        score = 0
        today = timezone.now().date()
        scheduled = getattr(activity, 'scheduled_date', None)
        weights = CONFIG.priorities.weights

        # Scheduled date tier
        if scheduled:
            if scheduled > today:
                days_ahead = (scheduled - today).days
                score += -10000 + (-10 * days_ahead)
            elif scheduled < today:
                days_overdue = (today - scheduled).days
                score += (
                    days_overdue
                    * CONFIG.priorities.overdue_penalty_per_day
                    * weights.get('overdue_weight', 1.5)
                )

        # Activity type weight
        type_score = CONFIG.priorities.activity_type_priorities.get(activity.activity_type, 1)
        score += type_score * weights.get('activity_type_weight', 0.5)

        # Sequence position bonus
        position = activity.sequence_position or 99
        score += int(CONFIG.priorities.sequence_step_priority_bonus / position)

        # Callback boost
        if activity.is_callback_followup:
            score += CONFIG.priorities.callback_priority_boost * weights.get('callback_weight', 2.0)

        # No-answer penalty — demotes CALL after failed attempts (per-activity counter)
        if (
            activity.activity_type == ActivityType.CALL
            and activity.no_answer_count > 0
        ):
            score -= activity.no_answer_count * 50

        return score

    # ======================================================================
    # PRIVATE — HELPERS
    # ======================================================================

    def _get_executor(self, campaign, campaign_account):
        """Return the first EXECUTOR member, falling back to campaign creator."""
        executor = CampaignMember.objects.filter(
            campaign=campaign,
            role='EXECUTOR',
        ).select_related('user').first()
        return executor.user if executor else self.user

    def _next_business_day(self, date):
        """Advance date past weekends (Mon–Fri only)."""
        while date.weekday() >= 5:
            date += timedelta(days=1)
        return date