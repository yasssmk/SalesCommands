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
from django.db.models import Case, Count, DateField, F, Prefetch, Q, When
from django.utils import timezone
from datetime import timedelta

from core.logging import get_logger
from core.logging.audit import audit_log
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages, CoreErrorMessages

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityType, ActivityStatus, ActivityOutcome
from app_modules.activities.todo_rules import campaign_actionable_date_expr
from app_modules.contacts.models import Contact
from app_modules.sequences.sequence_dispatcher import SequenceDispatcher

from ..models import (
    CampaignStatus,
    CampaignAccount,
    CampaignAccountStatus,
    CampaignContact,
    CampaignContactStatus,
    FINAL_CONTACT_STATES,
)
from ..config.settings import CONFIG

logger = get_logger(__name__)

# Outcomes that permanently stop a contact's sequence
TERMINAL_OUTCOMES: frozenset = frozenset({
    ActivityOutcome.NOT_INTERESTED,
    ActivityOutcome.WRONG_CONTACT,
    ActivityOutcome.UNSUBSCRIBE_OPTOUT,
    ActivityOutcome.WRONG_EMAIL,
    ActivityOutcome.INVALID_PHONE_NUMBER,
})

SUCCESSFUL_OUTCOMES: frozenset = frozenset({
    ActivityOutcome.SUCCESSFUL,
    ActivityOutcome.MEETING_SCHEDULED,
})

# Fallback title prefix for campaign activities whose campaign runs without an
# automated sequence (sequence_type is empty, so no sequence declares a prefix).
DEFAULT_CAMPAIGN_PREFIX = "CMP"

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

    def generate_activities_for_contact(self, campaign, campaign_account, contact, origin_activity=None, source_decision_cycle=None):
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
                source_activity=origin_activity,
                source_decision_cycle=source_decision_cycle,
            )
            campaign_contact.mark_activities_generated(user=self.user)
            return 1

        has_phone = bool(getattr(contact, 'phone_number', None))
        has_email = bool(getattr(contact, 'email', None))
        has_linkedin = bool(getattr(contact, 'linkedin_url', None))

        # Apply channel override — EMAIL_ONLY forces WITHOUT_PHONE variant
        # regardless of actual contact channel availability.
        if getattr(campaign, 'channel_override', 'AUTO') == 'EMAIL_ONLY':
            has_phone = False

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
        cumulative_delay = 0

        if campaign.is_targeted:
            base_date = self._next_business_day(timezone.now().date())
        else:
            # Use actual_start_date (set when campaign is launched) so step 1
            # lands on the day the rep actually started the campaign.
            base_date = self._next_business_day(
                campaign.actual_start_date or timezone.now().date()
            )

        for step_number, step_config in sequence_dict.items():
            cumulative_delay += step_config.get('min_delay', 0)
            step_date = self._next_business_day(base_date + timedelta(days=cumulative_delay))
            self._create_activity(
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
                scheduled_date=step_date,
                source_activity=origin_activity,
                source_decision_cycle=source_decision_cycle,
            )
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

    def get_playlist(self, campaign, executor=None):
        """
        Get prioritized activity playlist for a campaign.

        No limit applied — reps must see all their activities.

        Ordering:
            1. TODAY — eligible activities sorted by quality score.
            2. UPCOMING — not yet eligible or future date, sorted by scheduled_date asc.
            3. ON_HOLD — always at the end.

        Eligibility for TODAY (PLANNED only):
            - Callbacks (is_callback_followup=True): always today if scheduled_date <= today.
            - Regular steps: today if sequence_position == min PLANNED position
            for their campaign_contact AND scheduled_date <= today.
        """
        today = timezone.now().date()

        queryset = Activity.objects.filter(
            campaign=campaign,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
        ).select_related(
            'account',
            'owner',
            'campaign_contact',
            'campaign_contact__campaign_account',
            'decision_step',
        ).prefetch_related(
            Prefetch(
                'contacts',
                queryset=Contact.objects.select_related('standard_department'),
            ),
        ).annotate(
            _contacts_count=Count('contacts'),
            # Read-time actionable date for the card: PLANNED steps show
            # max(scheduled_date, today) (the shared todo clamp) so an overdue
            # step displays today instead of its frozen date. Grouping below
            # still keys off the raw scheduled_date — this annotation is
            # display-only and never written.
            _actionable_date=Case(
                When(
                    status=ActivityStatus.PLANNED,
                    then=campaign_actionable_date_expr(today),
                ),
                default=F('scheduled_date'),
                output_field=DateField(),
            ),
        )

        if executor:
            queryset = queryset.filter(owner=executor)

        # Single evaluation — the ordered result contains every matching row,
        # so the total is its length (no separate COUNT query).
        activities = list(queryset)
        total_count = len(activities)

        # Pre-compute min PLANNED sequence_position per campaign_contact (1 query).
        # Excludes callbacks — they don't block regular steps from appearing.
        from django.db.models import Min
        min_pos_qs = (
            Activity.objects.filter(
                campaign=campaign,
                status=ActivityStatus.PLANNED,
                is_callback_followup=False,
                campaign_contact__isnull=False,
            )
            .values('campaign_contact_id')
            .annotate(min_pos=Min('sequence_position'))
        )
        min_pos_map = {
            row['campaign_contact_id']: row['min_pos']
            for row in min_pos_qs
        }

        today_activities = []
        upcoming_activities = []
        on_hold_activities = []

        for a in activities:
            if a.status == ActivityStatus.ON_HOLD:
                on_hold_activities.append(a)
                continue

            scheduled = a.scheduled_date

            # Callbacks: eligible for today if scheduled_date <= today.
            if a.is_callback_followup:
                if scheduled and scheduled <= today:
                    today_activities.append(a)
                else:
                    upcoming_activities.append(a)
                continue

            # Regular steps: eligible for today if this is the first PLANNED
            # step for its contact AND scheduled_date <= today.
            cc_id = a.campaign_contact_id
            is_first_planned = (
                cc_id is not None
                and min_pos_map.get(cc_id) == a.sequence_position
            )

            if is_first_planned and (not scheduled or scheduled <= today):
                today_activities.append(a)
            else:
                upcoming_activities.append(a)

        today_activities.sort(key=lambda a: self._calculate_priority(a), reverse=True)
        upcoming_activities.sort(key=lambda a: a.scheduled_date or today)
        ordered = today_activities + upcoming_activities + on_hold_activities

        return {
            'activities': ordered,
            'total_count': total_count,
            # Size of the TODAY bucket — the "To do today" chip count. Additive:
            # 'activities' and 'total_count' are unchanged, existing consumers
            # (the playlist view / frontend) ignore the new key. It exists so the
            # campaign list's _activities_today annotation can be parity-checked
            # against this Python bucketing in a single test, guarding the two
            # implementations against silent drift.
            'today_count': len(today_activities),
        }

    def get_playlist_for_executor(self, campaign, executor):
        """Convenience wrapper — executor-scoped playlist."""
        return self.get_playlist(campaign, executor=executor)

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

        # Only persist next step's date when there is no callback pending.
        # Callback outcomes pause the sequence — the next step date will be
        # recalculated when the callback is resolved.
        has_callback = bool(result_data.get('callback_date'))
        if not has_callback:
            self._persist_next_activity_schedule(activity)

        if campaign_contact:
            next_activity = self._handle_outcome(campaign_contact, activity, result_data)

        # Logging the callback itself resolves the pause: the rep has made the
        # agreed resume call, so the sequence continues and the contact returns
        # to IN_PROGRESS. Skipped when the outcome already moved the contact to a
        # final state (SUCCESSFUL -> COMPLETED, terminal -> STOPPED) or requested
        # a fresh callback (has_callback) — those pauses/ends must stand. Carried
        # by the CALLBACK activity only; logging an ordinary step of a paused
        # contact never lifts the pause.
        if (
            activity.is_callback_followup
            and not has_callback
            and campaign_contact
            and campaign_contact.status == CampaignContactStatus.CALLBACK_PENDING
        ):
            campaign_contact.resume_from_callback(
                user=self.user,
                notes="Callback logged — sequence resumed",
            )

        # Reschedule overdue chains for this campaign now that a contact's chain
        # state has changed. This replaces the write-on-GET rescheduling that
        # used to run inside get_playlist — the playlist endpoint is read-only.
        # Scoped to this campaign only.
        self._reschedule_overdue_chains(activity.campaign, timezone.now().date())

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

        Delegates per-contact generation to generate_activities_for_contact().
        Special case: no sequence + no contacts → single account-level activity.
        """
        contacts = self._extract_contacts(campaign_account, campaign=campaign)

        # Special case: no sequence, no contacts → one account-level activity
        if not campaign.sequence_type and not contacts:
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
                    owner=self._get_executor(campaign, campaign_account),
                )
                cc.mark_activities_generated(user=self.user)
            return 1

        if not contacts:
            return 0

        created = 0
        for contact in contacts:
            created += self.generate_activities_for_contact(campaign, campaign_account, contact)
        return created

    def _extract_contacts(self, campaign_account, campaign=None):
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
                .filter(opted_out=False, client_id=self.client_id)
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

        # EMAIL_ONLY: restrict to contacts with a valid email address only.
        if campaign and getattr(campaign, 'channel_override', 'AUTO') == 'EMAIL_ONLY':
            queryset = queryset.filter(email__isnull=False).exclude(email='')
        else:
            queryset = queryset.filter(
                Q(email__isnull=False) | Q(phone_number__isnull=False)
            ).exclude(
                Q(email='') & Q(phone_number='')
            )

        return list(queryset)

    def _build_activity_title(self, campaign, account, contact, step_name):
        """
        Compose a campaign activity title — the single source of the format.

        Shape: "<PREFIX> · [<campaign> · ]<account> › <contact> — <step_name>"
        The head is common to every activity of the same campaign, so a list
        groups them visually — "<PREFIX> · <campaign>" for Outbound (an account
        may be in several), "<PREFIX> · <account>" for Targeted (one per account,
        so the campaign name is redundant and omitted). Only step_name varies
        within a contact's chain (a callback reads "… — Callback"). No date, no
        step number — both are mutable and must not be frozen into the name.

        The prefix and whether the campaign name is included are both properties
        of the sequence; a campaign without a sequence falls back to
        DEFAULT_CAMPAIGN_PREFIX and keeps its name.
        """
        seq_type = getattr(campaign, 'sequence_type', '') or ''
        prefix = SequenceDispatcher.get_prefix(seq_type) or DEFAULT_CAMPAIGN_PREFIX
        include_campaign_name = SequenceDispatcher.get_include_campaign_name(seq_type)

        contact_name = (
            f"{contact.first_name or ''} {contact.last_name or ''}".strip()
            if contact else ""
        )
        parts = [prefix]
        if include_campaign_name:
            parts.append(campaign.name)
        parts.append(account.company_name)
        head = " · ".join(parts)
        if contact_name:
            head = f"{head} › {contact_name}"
        return f"{head} — {step_name}" if step_name else head

    def _create_activity(self, campaign, campaign_account, campaign_contact,
                         account, contact, activity_type, position, owner=None,
                         step_config=None, sequence_variant=None,
                         scheduled_date=None, source_activity=None,
                         source_decision_cycle=None):
        """
        Create a single Activity linked to a campaign_contact.
        """
        owner = owner or self.user

        step_name = step_config.get('description', '') if step_config else ''
        title = self._build_activity_title(campaign, account, contact, step_name)

        # Populate call_to_action:
        # 1. Explicit step config value (sequence-defined objective)
        # 2. Fallback to campaign_account.notes for targeted campaigns (enrollment reason)
        call_to_action = None
        if step_config:
            call_to_action = step_config.get('call_to_action') or None
        if not call_to_action and campaign.is_targeted and campaign_account:
            call_to_action = campaign_account.notes or None

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
            # Stamp the contact's current chasing run (immutable after creation).
            sequence_run=campaign_contact.sequence_run,
            scheduled_date=scheduled_date or campaign.planned_start_date,
            due_date=campaign.planned_end_date,
            min_delay_days=step_config.get('min_delay') if step_config else None,
            sequence_variant=sequence_variant,
            description=step_config.get('description', '') if step_config else '',
            call_to_action=call_to_action,
            source_activity=source_activity,
            source_decision_cycle=source_decision_cycle,
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
            from datetime import date
            if isinstance(callback_date, str):
                callback_date = date.fromisoformat(callback_date)
            if callback_date < timezone.now().date():
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="callback_date (must be a future date)"
                    )
                )

            contact = activity.contacts.first()

            campaign_contact.request_callback(
                callback_date=callback_date,
                user=self.user,
                notes=f"Callback from activity: {activity.title}",
            )
            followup = self._create_followup(
                activity,
                campaign_contact=campaign_contact,
                title=self._build_activity_title(
                    activity.campaign, activity.account, contact, "Callback"
                ),
                activity_type=next_activity_type or activity.activity_type,
                scheduled_date=callback_date,
                scheduled_time=callback_time,
                is_callback_followup=True,
            )

            # No linked list manipulation needed.
            # The callback is identified via source_activity=activity + is_callback_followup=True.
            # _persist_next_activity_schedule() will find it via source_activity FK when
            # the completed activity is processed, and will use callback_date as base
            # for cascading the remaining sequence steps.
            #
            # Cascade estimated dates for the remaining chain using callback_date as anchor,
            # so Upcoming shows coherent future dates.
            next_regular = Activity.objects.filter(
                campaign_contact_id=campaign_contact.id,
                sequence_position__gt=activity.sequence_position,
                status=ActivityStatus.PLANNED,
                is_callback_followup=False,
            ).order_by('sequence_position').first()

            if next_regular:
                self._cascade_schedule_from(next_regular, base_date=callback_date)

            return followup


        # ------------------------------------------------------------------
        # TERMINAL OUTCOMES — stop contact, cancel its chain
        # ------------------------------------------------------------------

        if outcome in TERMINAL_OUTCOMES:
            campaign_contact.mark_stopped(
                user=self.user,
                notes=f"Terminal outcome: {outcome}",
            )
            self._cancel_chain_for_contact(campaign_contact)

            # Propagate opt-out to the Contact record so future campaign
            # enrollment (_extract_contacts) correctly excludes this contact.
            if outcome == ActivityOutcome.UNSUBSCRIBE_OPTOUT:
                contact = activity.contacts.first()
                if contact:
                    contact.mark_opted_out(user=self.user)
                    audit_log(
                        event='contact_opted_out',
                        action='update',
                        actor_id=str(self.user.id),
                        client_id=self.client_id,
                        target_type='contact',
                        target_id=str(contact.id),
                        outcome='success',
                        extra={
                            'source': 'campaign_outcome',
                            'activity_id': str(activity.id),
                            'campaign_id': str(activity.campaign_id),
                        }
                    )

            self._check_account_completion(campaign_account)
            return None

        # ------------------------------------------------------------------
        # SUCCESSFUL OUTCOMES — complete contact + possibly account
        # ------------------------------------------------------------------
        if outcome in SUCCESSFUL_OUTCOMES:
            campaign_contact.mark_completed(
                user=self.user,
                notes=f"Successful: {outcome}",
            )
            # Cancel remaining contacts on the same account
            self._cancel_chain_for_contact(campaign_contact)
            self._check_account_completion(campaign_account)
            return None
        
        # ------------------------------------------------------------------
        # NO_ANSWER — sequence continues to next step.
        # If no PLANNED activities remain, the sequence has run its full course:
        # the contact reached the natural end of its chasing sequence without a
        # response. That is a COMPLETED contact (sequence done), not a STOPPED one
        # (STOPPED stays reserved for genuine stops: a franc terminal outcome, a
        # manual stop, a campaign close, a bulk cancel). The causal reason is kept
        # in the notes so the completion reads as "no answer", not a commercial win.
        # ------------------------------------------------------------------
        if outcome == ActivityOutcome.NO_ANSWER:
            has_remaining = Activity.objects.filter(
                campaign_contact=campaign_contact,
                status=ActivityStatus.PLANNED,
            ).exists()
            if not has_remaining:
                campaign_contact.mark_completed(
                    user=self.user,
                    notes="No answer — sequence exhausted",
                )
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
        Delete all PLANNED and ON_HOLD activities for a given CampaignContact.

        Called on any terminal contact transition (STOPPED or COMPLETED).
        Deleting instead of cancelling keeps the activity timeline clean —
        only completed activities have historical value.

        Returns:
            int: number of activities deleted
        """
        deleted, _ = Activity.objects.filter(
            campaign_contact=campaign_contact,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
        ).delete()
        logger.info("campaign_contact_chain_deleted", extra={
            'campaign_contact_id': str(campaign_contact.id),
            'deleted_count': deleted,
        })
        return deleted

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

    def _create_followup(self, source_activity, campaign_contact,
                     activity_type=None, scheduled_date=None,
                     scheduled_time=None, is_callback_followup=False,
                     title=None):
        """
        Create a follow-up activity from a completed one.
        Copies campaign context and links to the same CampaignContact.

        Sets source_activity FK for full traceability (replaces linked list).
        Callbacks are identified via is_callback_followup=True + source_activity.
        """
        position = (source_activity.sequence_position or 0) + 1
        activity_type = activity_type or source_activity.activity_type

        if is_callback_followup:
            # Make room for the callback at `position`: shift every later step of
            # this contact up by one. Inserting the callback would otherwise
            # collide with the step that already occupies `position` (two rows at
            # the same sequence_position -> wrong "Step N" chips, disordered
            # timeline). A single set-based UPDATE — Postgres applies it as one
            # atomic statement, so no transient duplicate is ever visible; the
            # whole flow runs inside the request's transaction.
            Activity.objects.filter(
                campaign_contact=campaign_contact,
                sequence_position__gte=position,
            ).update(sequence_position=F('sequence_position') + 1)

        if not title:
            title = self._build_activity_title(
                source_activity.campaign, source_activity.account,
                source_activity.contacts.first(), "Follow-up",
            )

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
            # A follow-up belongs to the contact's current chasing run.
            sequence_run=campaign_contact.sequence_run,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            due_date=(
                source_activity.campaign.planned_end_date
                if source_activity.campaign else None
            ),
            is_callback_followup=is_callback_followup,
            source_activity=source_activity,
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
    # PRIVATE — PRIORITY SCORING
    # ======================================================================

    def _calculate_priority(self, activity):
        """
        Two-tier scoring:

        UPCOMING (previous not COMPLETED, or scheduled_date > today):
            → large negative base score offset by date proximity.
            → sorted by date ascending — closest first.
            → ON_HOLD pushed to end of upcoming.

        TODAY (scheduled_date <= today and previous COMPLETED or step 1):
            → scored by activity quality: callback boost, type weight,
              overdue days, no-answer penalty.
            → higher score = higher priority.
        """
        today = timezone.now().date()
        scheduled = getattr(activity, 'scheduled_date', None)
        weights = CONFIG.priorities.weights


        # --- TODAY bucket ---
        score = 0

        # Callback followup — highest priority
        if activity.is_callback_followup:
            score += CONFIG.priorities.callback_priority_boost * weights.get('callback_weight', 2.0)

        # Overdue bonus (step 2+ only — step 1 has no predecessor)
        if scheduled and scheduled < today and (activity.sequence_position or 1) > 1:
            days_overdue = (today - scheduled).days
            score += (
                days_overdue
                * CONFIG.priorities.overdue_penalty_per_day
                * weights.get('overdue_weight', 1.5)
            )

        # Activity type weight
        type_score = CONFIG.priorities.activity_type_priorities.get(activity.activity_type, 1)
        score += type_score * weights.get('activity_type_weight', 0.5)

        # Sequence position bonus (earlier steps first within same day)
        position = max(activity.sequence_position or 1, 1)
        score += int(CONFIG.priorities.sequence_step_priority_bonus / position)

        # No-answer penalty
        if activity.activity_type == ActivityType.CALL and activity.no_answer_count > 0:
            score -= activity.no_answer_count * 50

        return score

    # ======================================================================
    # PRIVATE — HELPERS
    # ======================================================================

    def _get_executor(self, campaign, campaign_account):
        """Return campaign executor if set, otherwise fall back to current user."""
        return campaign.executor or self.user
    
    def _persist_next_activity_schedule(self, completed_activity):
        """
        After an activity is completed, anchor the next step's scheduled_date
        to completed_at + min_delay_days, then cascade the full remaining chain.

        Uses sequence_position — no linked list traversal.

        Rules:
            - Check for a pending callback (source_activity=completed, is_callback_followup=True)
            first: if one exists, it takes priority as next step.
            - Otherwise: next regular step = lowest sequence_position > completed in same contact.
            - Skip callback followups for cascade (user-chosen dates).
            - Skip if completed_at is not set.
            - Cascades the entire remaining chain via _cascade_schedule_from().
        """
        if not completed_activity.completed_at:
            return

        if not completed_activity.campaign_contact_id:
            return

        base = completed_activity.completed_at.date()

        # Priority 1: pending callback created from this activity.
        next_act = Activity.objects.filter(
            source_activity=completed_activity,
            is_callback_followup=True,
            status=ActivityStatus.PLANNED,
        ).first()

        # Priority 2: next regular step in the sequence.
        if next_act is None:
            next_act = Activity.objects.filter(
                campaign_contact_id=completed_activity.campaign_contact_id,
                sequence_position__gt=completed_activity.sequence_position,
                status=ActivityStatus.PLANNED,
                is_callback_followup=False,
            ).order_by('sequence_position').first()

        if next_act is None:
            return

        # Callback followup date is user-chosen — never overwrite it.
        if next_act.is_callback_followup:
            return

        delay = next_act.min_delay_days or 0
        new_date = self._next_business_day(base + timedelta(days=delay))

        Activity.objects.filter(pk=next_act.pk).update(
            scheduled_date=new_date,
            updated_at=timezone.now(),
        )

        logger.info("campaign_next_activity_scheduled", extra={
            'completed_activity_id': str(completed_activity.id),
            'next_activity_id': str(next_act.id),
            'scheduled_date': str(new_date),
        })

        # Cascade the full remaining chain from next_act's confirmed date.
        subsequent = Activity.objects.filter(
            campaign_contact_id=completed_activity.campaign_contact_id,
            sequence_position__gt=next_act.sequence_position,
            status=ActivityStatus.PLANNED,
            is_callback_followup=False,
        ).order_by('sequence_position').first()

        if subsequent:
            self._cascade_schedule_from(subsequent, base_date=new_date)

    def _next_business_day(self, date):
        """Advance date past weekends (Mon–Fri only)."""
        while date.weekday() >= 5:
            date += timedelta(days=1)
        return date
    
    def _reschedule_overdue_chains(self, campaign, today):
        """
        Lazy rescheduling: for each CampaignContact with overdue PLANNED activities,
        anchor the first pending step to today and cascade the rest of the chain.

        Called from process_result() on the log-response POST flow — the playlist
        GET endpoint is read-only (Q6), so this write never runs on a read.

        Rules:
            - Only processes the first PLANNED step per CampaignContact (lowest sequence_position).
            - Skips callback followups (user-chosen dates, never auto-shifted).
            - If first PLANNED step's scheduled_date >= today: chain is fine, skip.
            - Otherwise: set first step to today, cascade remaining chain via
            _cascade_schedule_from().
        """
        # Fetch all PLANNED, non-callback activities for this campaign.
        # Exclude ON_HOLD — they are intentionally paused.
        planned = (
            Activity.objects.filter(
                campaign=campaign,
                status=ActivityStatus.PLANNED,
                is_callback_followup=False,
            )
            .exclude(campaign_contact__isnull=True)
            .order_by('campaign_contact_id', 'sequence_position')
            .only('id', 'campaign_contact_id', 'sequence_position', 'scheduled_date', 'min_delay_days')
        )

        # Group by campaign_contact_id — keep only the first (lowest position) per contact.
        first_per_contact: dict = {}
        for activity in planned:
            cc_id = activity.campaign_contact_id
            if cc_id not in first_per_contact:
                first_per_contact[cc_id] = activity

        if not first_per_contact:
            return

        for cc_id, first_activity in first_per_contact.items():
            scheduled = first_activity.scheduled_date
            if scheduled is None or scheduled >= today:
                # Chain is current — nothing to do.
                continue

            # Anchor first step to today.
            Activity.objects.filter(pk=first_activity.pk).update(
                scheduled_date=today,
                updated_at=timezone.now(),
            )

            logger.info("campaign_overdue_chain_rescheduled", extra={
                'campaign_id': str(campaign.id),
                'campaign_contact_id': str(cc_id),
                'first_activity_id': str(first_activity.id),
                'old_scheduled_date': str(scheduled),
                'new_scheduled_date': str(today),
            })

            # Cascade the rest of the chain from today via sequence_position.
            next_activity = Activity.objects.filter(
                campaign_contact_id=cc_id,
                sequence_position__gt=first_activity.sequence_position,
                status=ActivityStatus.PLANNED,
                is_callback_followup=False,
            ).order_by('sequence_position').first()

            if next_activity:
                self._cascade_schedule_from(next_activity, base_date=today)
    
    def reschedule_after_callback_date_change(self, callback_activity):
        """
        Recale a contact's chain after its callback date was edited.

        When the rep moves a callback's scheduled_date (the one editable date in
        a campaign chain), the remaining regular steps must follow the new date.
        Reuses the existing cascade from the step right after the callback, so
        nothing else in the schedule logic changes. Only scheduled_date moves —
        positions and the contact's CALLBACK_PENDING status are untouched.

        No-op for anything that is not a dated callback still linked to a contact.
        """
        if not (
            callback_activity.is_callback_followup
            and callback_activity.campaign_contact_id
            and callback_activity.scheduled_date
        ):
            return

        next_regular = Activity.objects.filter(
            campaign_contact_id=callback_activity.campaign_contact_id,
            sequence_position__gt=callback_activity.sequence_position,
            status=ActivityStatus.PLANNED,
            is_callback_followup=False,
        ).order_by('sequence_position').first()

        if next_regular:
            self._cascade_schedule_from(
                next_regular, base_date=callback_activity.scheduled_date
            )

    def _cascade_schedule_from(self, start_activity, base_date):
        """
        Cascade estimated scheduled_date for all PLANNED activities in a contact's
        chain starting at start_activity, using base_date as anchor.

        Uses sequence_position ordering — no linked list traversal.

        Rules:
            - Skips callback followups (user-chosen dates).
            - Does not touch COMPLETED or CANCELLED activities.
            - Bulk-loads the full remaining chain in 1 query, then bulk updates.
        """
        if not start_activity.campaign_contact_id:
            return

        activities = list(
            Activity.objects.filter(
                campaign_contact_id=start_activity.campaign_contact_id,
                sequence_position__gte=start_activity.sequence_position,
                status=ActivityStatus.PLANNED,
                is_callback_followup=False,
            ).order_by('sequence_position')
            .only('id', 'sequence_position', 'min_delay_days', 'scheduled_date')
        )

        if not activities:
            return

        current_base = base_date
        now = timezone.now()

        for activity in activities:
            delay = activity.min_delay_days or 0
            activity.scheduled_date = self._next_business_day(
                current_base + timedelta(days=delay)
            )
            activity.updated_at = now
            current_base = activity.scheduled_date

        # Single bulk_update — one query for the entire chain
        Activity.objects.bulk_update(activities, ['scheduled_date', 'updated_at'])

        logger.info("campaign_chain_dates_cascaded", extra={
            'campaign_contact_id': str(start_activity.campaign_contact_id),
            'start_position': start_activity.sequence_position,
            'activities_updated': len(activities),
            'base_date': str(base_date),
        })
