# app_modules/activities/services/activity_creation_service.py
"""
Activity Creation Service.

Handles complex activity creation scenarios including inline creation
of related entities (Contact, DecisionCycle, DecisionStep) in a single
atomic transaction.

This service ensures FK-safe order:
1. Create Contact (if inline_contact provided)
2. Create DecisionCycle (if inline_cycle provided)
3. Create DecisionStep (if inline_step provided)
4. Create Activity with all relations
"""

from django.db import transaction

from core.logging import get_logger
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, ActivityErrorMessages, AccountErrorMessages

from app_modules.contacts.models import Contact
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep

from ..models import Activity
from ..constants import ActivityStatus

logger = get_logger(__name__)


class ActivityCreationService:
    """
    Service for creating activities with optional inline entity creation.
    
    Usage:
        service = ActivityCreationService(user=request.user, client_id=client_id)
        result = service.create_with_entities(
            activity_data={...},
            inline_contact={...},  # Optional
            inline_cycle={...},    # Optional
            inline_step={...},     # Optional
        )
    """
    
    def __init__(self, user, client_id):
        self.user = user
        self.client_id = client_id
    
    @transaction.atomic
    def create_with_entities(
        self,
        activity_data: dict,
        inline_contact: dict = None,
        inline_cycle: dict = None,
        inline_step: dict = None,
        inline_step_stage: str = None,
        cycle_owner_override=None,
    ) -> dict:
        """
        Create activity with optional inline entities.
        
        Args:
            activity_data: Core activity fields (title, type, status, etc.)
            inline_contact: Optional dict with {first_name, last_name, email, ...}
            inline_cycle: Optional dict with {name}
            inline_step: Optional dict with {name, stage, expected_end}
        
        Returns:
            dict with created entities: {activity, contact, cycle, step}
        
        Raises:
            StandardizedValidationError on validation failures
        """
        try:
            created_entities = {
                'activity': None,
                'contact': None,
                'cycle': None,
                'step': None,
            }
            
            account_id = activity_data.get('account_id')
            if not account_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Account')
                )
            
            # Validate account exists
            from app_modules.accounts.models import CompanyAccount
            try:
                account = CompanyAccount.objects.get(id=account_id, client_id=self.client_id)
            except CompanyAccount.DoesNotExist:
                raise StandardizedValidationError(
                    AccountErrorMessages.ACCOUNT_NOT_FOUND
                )

            # Activity owner resolution: explicit override, else the current user.
            resolved_owner = cycle_owner_override or self.user
            
            # Track IDs to link
            contact_ids = list(activity_data.get('contact_ids', []))
            cycle_id = activity_data.get('decision_cycle_id')
            step_id = activity_data.get('decision_step_id')
            source_activity_id = activity_data.get('source_activity_id')

            # The campaign this activity comes from, resolved BEFORE step 2 so a
            # cycle created below can be stamped with its origin at birth.
            # DecisionCycle.source_campaign answers "which campaign CREATED this
            # deal" and is the whole basis of the DECISION_CYCLES objective, so
            # it is written exactly once, on a cycle that did not exist before.
            # A cycle that already exists is NEVER re-parented — see _create_cycle.
            origin_campaign_id = self._campaign_of(source_activity_id)
            
            # ==================================================================
            # STEP 1: Create Contact (if inline_contact provided)
            # ==================================================================
            if inline_contact:
                contact = self._create_contact(inline_contact, account_id)
                created_entities['contact'] = contact
                contact_ids.append(str(contact.id))
                
                logger.info("inline_contact_created", extra={
                    'contact_id': str(contact.id),
                    'account_id': str(account_id),
                })

            # ==================================================================
            # STEP 2: Create DecisionCycle (if inline_cycle provided)
            # ==================================================================
            if inline_cycle:
                cycle = self._create_cycle(inline_cycle, account_id,
                                           source_campaign_id=origin_campaign_id)
                created_entities['cycle'] = cycle
                cycle_id = str(cycle.id)
                
                target_stage = inline_step_stage or 'QUALIFICATION'

                # Find the step by stage
                assigned_step = DecisionStep.objects.filter(
                    cycle_id=cycle_id,
                    stage=target_stage
                ).first()

                # Fallback to QUALIFICATION if stage not found
                if not assigned_step:
                    assigned_step = DecisionStep.objects.filter(
                        cycle_id=cycle_id,
                        order=1
                    ).first()
                    logger.warning("inline_step_stage_fallback", extra={
                        'requested_stage': target_stage,
                        'fallback_stage': 'QUALIFICATION',
                        'cycle_id': str(cycle.id),
                    })

                if assigned_step:
                    step_id = str(assigned_step.id)
                    logger.info("inline_cycle_step_assigned", extra={
                        'cycle_id': str(cycle.id),
                        'step_id': step_id,
                        'step_stage': assigned_step.stage,
                        'account_id': str(account_id),
                    })
                else:
                    # Should never happen if _create_cycle worked correctly
                    logger.error("inline_cycle_missing_qualification_step", extra={
                        'cycle_id': str(cycle.id),
                        'account_id': str(account_id),
                    })
                    raise StandardizedValidationError(
                        ActivityErrorMessages.CYCLE_CREATION_FAILED
                    )

            # ==================================================================
            # STEP 3: Validate step belongs to cycle (if both provided)
            # ==================================================================
            if cycle_id and step_id:
                step_exists = DecisionStep.objects.filter(
                    id=step_id,
                    cycle_id=cycle_id
                ).exists()
                
                if not step_exists:
                    raise StandardizedValidationError(
                        ActivityErrorMessages.STEP_MUST_BELONG_TO_CYCLE
                    )

            # ==================================================================
            # VALIDATION: If cycle is provided, step is REQUIRED
            # ==================================================================
            if cycle_id and not step_id:
                raise StandardizedValidationError(
                    ActivityErrorMessages.STEP_REQUIRES_CYCLE
                )

            # ==================================================================
            # STEP 4: Create Activity
            # ==================================================================
            activity = self._create_activity(
                activity_data=activity_data,
                contact_ids=contact_ids,
                cycle_id=cycle_id,
                step_id=step_id,
                owner=resolved_owner,
                source_activity_id=source_activity_id,
            )

            # NO BACKFILL HERE. This used to write source_campaign on whatever
            # cycle the activity pointed at, "covering both inline cycle creation
            # AND linking to an existing cycle" — so a PRE-EXISTING deal silently
            # became "created by" a campaign that had merely touched it, at
            # activity-creation time and with no completed work. Only the first
            # half was legitimate, and it now happens above, at construction.
            #
            # Campaign VALUE no longer depends on source_campaign at all
            # (campaigns/services/campaign_dc_attribution.py: money requires a
            # COMPLETED + SUCCESSFUL activity of the campaign), so a touched
            # pre-existing deal still counts in that campaign's pipeline —
            # through work, not through a rewritten origin.

            created_entities['activity'] = activity
            
            logger.info("activity_with_entities_created", extra={
                'activity_id': str(activity.id),
                'inline_contact': bool(inline_contact),
                'inline_cycle': bool(inline_cycle),
                'inline_step': bool(inline_step),
            })
            
            return created_entities
        
        except StandardizedValidationError:
            raise
        except Exception as e:
            logger.error("activity_creation_service_error", extra={
                'error': str(e),
                'account_id': str(activity_data.get('account_id')) if activity_data else None,
                'has_inline_contact': bool(inline_contact),
                'has_inline_cycle': bool(inline_cycle),
            })
            raise StandardizedValidationError(
                ActivityErrorMessages.CREATION_FAILED
            )
    
    def _create_contact(self, data: dict, account_id: str) -> Contact:
        """Create a contact with minimal required fields."""
        try:
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            
            if not first_name:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Contact First Name')
                )
            if not last_name:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Contact Last Name')
                )
            
            # Handle both 'phone_number' and 'phone' keys from frontend
            phone_value = data.get('phone_number') or data.get('phone')
            phone_number = (phone_value or '').strip() or None
            
            # Handle standard_department_id
            standard_department_id = data.get('standard_department_id')
            if not standard_department_id:
                from app_modules.core_modules.models import StandardDepartment
                default_dept = StandardDepartment.objects.filter(name='General Management').first()
                if default_dept:
                    standard_department_id = default_dept.id
            
            contact = Contact(
                client_id=self.client_id,
                account_id=account_id,
                first_name=first_name,
                last_name=last_name,
                email=(data.get('email') or '').strip() or None,
                phone_number=phone_number,
                job_title=(data.get('job_title') or '').strip() or None,
                standard_department_id=standard_department_id,
                created_by=self.user,
                updated_by=self.user,
            )
            contact.save()
            return contact
        
        except StandardizedValidationError:
            raise
        except Exception as e:
            logger.error("inline_contact_creation_failed", extra={
                'error': str(e),
                'account_id': str(account_id),
            })
            raise StandardizedValidationError(
                ActivityErrorMessages.CONTACT_CREATION_FAILED
            )
    
    def _campaign_of(self, source_activity_id):
        """The campaign of the activity this one is created FROM, or None.

        One query, and only when a source activity was named. Returns the id so
        the caller can stamp a NEW cycle without holding the instance.
        """
        if not source_activity_id:
            return None
        return (
            Activity.objects
            .filter(id=source_activity_id, client_id=self.client_id)
            .values_list('campaign_id', flat=True)
            .first()
        )

    def _create_cycle(self, data: dict, account_id: str,
                      source_campaign_id=None) -> DecisionCycle:
        """
        Create a decision cycle with auto-created pipeline steps.
        
        Pipeline steps are FIXED and auto-created (same as DecisionCycleViewSet.create).
        All 7 steps are created: Qualification → Technical Fit → Solution Validation 
        → Business Case → Closing → Implementation → Go Live
        """
        try:
            from app_modules.decision_cycles.constants import PIPELINE_STEPS_CONFIG
            
            name = data.get('name', '').strip()
            
            if not name:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Decision Cycle Name')
                )
            
            # Create the cycle. owner = the creator (same user as created_by);
            # a DecisionCycle must never be created ownerless.
            cycle = DecisionCycle(
                client_id=self.client_id,
                account_id=account_id,
                name=name,
                is_active=True,
                owner=self.user,
                # Origin, stamped at BIRTH: this cycle did not exist before the
                # campaign activity that is creating it, so the campaign really
                # did create it. None when the activity carries no campaign.
                source_campaign_id=source_campaign_id,
                created_by=self.user,
                updated_by=self.user,
            )
            cycle.save()
            
            # Auto-create all 7 pipeline steps (FIXED structure)
            self._create_pipeline_steps(cycle)
            
            logger.info("inline_cycle_created_with_steps", extra={
                'cycle_id': str(cycle.id),
                'account_id': str(account_id),
                'steps_created': len(PIPELINE_STEPS_CONFIG),
            })
            
            return cycle
        
        except StandardizedValidationError:
            raise
        except Exception as e:
            logger.error("inline_cycle_creation_failed", extra={
                'error': str(e),
                'account_id': str(account_id),
            })
            raise StandardizedValidationError(
                ActivityErrorMessages.CYCLE_CREATION_FAILED
            )

    def _create_pipeline_steps(self, cycle: DecisionCycle) -> None:
        """
        Create all fixed pipeline steps for a new cycle.
        
        Steps are created in order with linked-list relationships.
        This mirrors DecisionCycleViewSet._create_pipeline_steps().
        """
        from app_modules.decision_cycles.constants import PIPELINE_STEPS_CONFIG
        
        previous_step = None
        
        for config in PIPELINE_STEPS_CONFIG:
            step = DecisionStep(
                cycle=cycle,
                client_id=cycle.client_id,
                name=config['step'].label,
                stage=config['step'].value,
                order=config['order'],
                previous_step=previous_step,
                expected_end=None,
                created_by=self.user,
                updated_by=self.user,
            )
            step.save(user=self.user)
            
            logger.debug("pipeline_step_created", extra={
                'cycle_id': str(cycle.id),
                'step_id': str(step.id),
                'stage': config['step'].value,
                'order': config['order'],
            })
            
            previous_step = step
    
    def _create_activity(
        self,
        activity_data: dict,
        contact_ids: list,
        cycle_id: str,
        step_id: str,
        owner=None,
        source_activity_id: str = None,
    ) -> Activity:
        """Create the activity with all relations."""
        try:
            from ..constants import ActivityType
            
            title = activity_data.get('title', '').strip()
            if not title:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Activity Title')
                )
            
            activity_type = activity_data.get('activity_type')
            if not activity_type:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Activity Type')
                )
            
            # Validate activity_type
            valid_types = [choice[0] for choice in ActivityType.choices]
            if activity_type not in valid_types:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='Activity Type')
                )
            
            activity = Activity(
                client_id=self.client_id,
                account_id=activity_data.get('account_id'),
                owner=owner or self.user,
                title=title,
                activity_type=activity_type,
                status=activity_data.get('status', ActivityStatus.PLANNED),
                description=(activity_data.get('description') or '').strip() or None,
                call_to_action=(activity_data.get('call_to_action') or '').strip() or None,
                scheduled_date=activity_data.get('scheduled_date'),
                scheduled_time=activity_data.get('scheduled_time'),
                due_date=activity_data.get('due_date'),
                outcome=activity_data.get('outcome'),
                outcome_notes=(activity_data.get('outcome_notes') or '').strip() or None,
                decision_cycle_id=cycle_id,
                decision_step_id=step_id,
                source_activity_id=source_activity_id,
                created_by=self.user,
                updated_by=self.user,
            )
            activity.save()

            # Re-read the row so the instance carries DB-TYPED values.
            #
            # Every field above is assigned RAW from the JSON payload, so
            # due_date / scheduled_date / scheduled_time arrive as STRINGS.
            # save() coerces on the way OUT to SQL, but Django never re-reads,
            # so without this the returned instance keeps the strings — and the
            # view serialises THIS instance (views.py create_with_entities),
            # where ActivitySerializer.is_overdue evaluates
            # ``due_date < timezone.now().date()`` and raised
            # ``'<' not supported between instances of 'str' and 'datetime.date'``.
            # Since that view is @transaction.atomic, the TypeError rolled the
            # whole operation back: a 500 AND no activity, no inline cycle.
            #
            # One re-read rather than coercing the two known date fields: it
            # covers every field, including any added later, at the single point
            # where an unvalidated payload becomes a model instance. The cost is
            # one query on a single-object creation path.
            activity.refresh_from_db()

            # Add contacts M2M
            if contact_ids:
                contacts = Contact.objects.filter(
                    id__in=contact_ids,
                    client_id=self.client_id
                )
                activity.contacts.set(contacts)
            
            return activity
        
        except StandardizedValidationError:
            raise
        except Exception as e:
            logger.error("activity_creation_failed", extra={
                'error': str(e),
                'account_id': str(activity_data.get('account_id')),
                'activity_type': activity_data.get('activity_type'),
            })
            raise StandardizedValidationError(
                ActivityErrorMessages.CREATION_FAILED
            )
