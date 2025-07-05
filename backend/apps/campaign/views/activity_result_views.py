from rest_framework import viewsets
from rest_framework.decorators import action
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages, CoreErrorMessages, ActivityErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.campaign.services.campaign_core_service import CampaignCoreService
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin
from apps.campaign.services.campaign_result_service import CampaignResultService
from apps.campaign.models.campaign_target import CampaignTarget
from apps.campaign.serializers.campaign_target_serializer import CampaignTargetSerializer
from apps.activities.models.activity import Activity
from datetime import datetime

class ActivityResultViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ViewSet):
    """
    ViewSet for handling activity results and completion
    ✅ DÉJÀ OPTIMISÉ dans étape 2.2 - Version finale
    """
    queryset = CampaignTarget.objects.all()
    serializer_class = CampaignTargetSerializer  
    entity_name = 'campaign_target'


    def _get_validated_activity(self, pk):
        """Helper method to get and validate activity ownership"""
        try:
            activity = Activity.objects.get(id=pk)
        except Activity.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        if activity.owner != self.request.user:
            raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
        
        return activity
    
    def _parse_date_field(self, data, field_name):
        """Helper method to parse date fields with consistent error handling"""
        date_value = data.get(field_name)
        if date_value:
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field=f"{field_name} (expected YYYY-MM-DD format)")
                )
        return None
    
    def _build_activity_kwargs(self, data):
        """Helper method to build kwargs from request data"""
        kwargs = {}
        
        callback_date = self._parse_date_field(data, 'callback_date')
        if callback_date:
            kwargs['callback_date'] = callback_date
        
        meeting_date = self._parse_date_field(data, 'meeting_date')
        if meeting_date:
            kwargs['meeting_date'] = meeting_date
        
        if 'disqualify_account' in data:
            kwargs['disqualify_account'] = data.get('disqualify_account')
        
        return kwargs
    
    @action(detail=True, methods=['post'])
    def complete_activity(self, request, pk=None):
        """Complete an activity with result - Optimized version"""
        try:
            activity = self._get_validated_activity(pk)
            
            result = request.data.get('result')
            notes = request.data.get('notes', '')
            
            if not result:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="result")
                )
            
            kwargs = self._build_activity_kwargs(request.data)
            
            return CampaignCoreService.complete_activity(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to complete activity")
            )
    
    @action(detail=True, methods=['post'])
    def add_email_response(self, request, pk=None):
        """Add a response to an already completed email/LinkedIn activity"""
        try:
            activity = self._get_validated_activity(pk)
            
            if activity.activity_type not in [Activity.ActivityType.EMAIL, Activity.ActivityType.LINKEDIN]:
                raise StandardizedValidationError(
                    "Can only add responses to email/LinkedIn activities"
                )
            
            result = request.data.get('result')
            notes = request.data.get('notes', '')
            
            if not result:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="result")
                )
            
            kwargs = self._build_activity_kwargs(request.data)
            
            return CampaignResultService.process_activity_result(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to add email response")
            )
        
    @action(detail=True, methods=['get'])
    def get_next_step_options(self, request, pk=None):
        """
        Get available next step options based on campaign target type - Unchanged
        
        Query params:
        - campaign_target_id: ID of the campaign target
        """
        try:
            campaign_target_id = pk
            
            if not campaign_target_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="campaign_target_id")
                )
            
            # Get campaign target and validate access
            try:
                from apps.campaign.models import CampaignTarget
                campaign_target = CampaignTarget.objects.get(id=campaign_target_id)
                
                # Validate client scope
                self.validate_client_id(campaign_target)
                
                # Validate campaign ownership/stakeholder access
                campaign = campaign_target.campaign
                self.validate_campaign_ownership(campaign, allow_stakeholders=True)
                
            except CampaignTarget.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Determine target type and available options
            target_type = campaign_target.get_target_type()
            target_object = campaign_target.get_target()
            
            available_options = []
            
            # Meeting is always available as next step
            available_options.append({
                'type': 'meeting',
                'label': 'Schedule Meeting',
                'description': 'Schedule a follow-up meeting',
                'requires_fields': ['meeting_date', 'notes']
            })
            
            # Lead creation (only for account/contact targets)
            if target_type in ['account', 'contact']:
                available_options.append({
                    'type': 'lead',
                    'label': 'Create Lead',
                    'description': 'Create a new lead for this prospect',
                    'requires_fields': ['lead_title', 'description', 'notes']
                })
            
            # Opportunity creation (valid for account/contact/lead targets)
            if target_type in ['account', 'contact', 'lead']:
                available_options.append({
                    'type': 'opportunity',
                    'label': 'Create Opportunity',
                    'description': 'Create a new sales opportunity',
                    'requires_fields': ['opportunity_title', 'expected_close_date', 'amount', 'notes']
                })
            
            # Opportunity advancement (only for opportunity targets)
            if target_type == 'opportunity':
                available_options.append({
                    'type': 'opportunity_advance',
                    'label': 'Advance Opportunity',
                    'description': 'Update existing opportunity (stage, amount, etc.)',
                    'requires_fields': ['notes'],  # Simple for MVP
                    'disabled': True,  # Disabled until stages are implemented
                    'disabled_reason': 'Opportunity stages not yet implemented'
                })
            
            # Other/Custom option
            available_options.append({
                'type': 'other',
                'label': 'Other Action',
                'description': 'Custom next step with notes only',
                'requires_fields': ['notes']
            })
            
            # Prepare response data
            data = {
                'campaign_target_id': campaign_target.id,
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'target_type': target_type,
                'target_info': {
                    'id': target_object.id,
                    'name': getattr(target_object, 'company_name', None) or 
                            getattr(target_object, 'title', None) or 
                            f"{getattr(target_object, 'first_name', '')} {getattr(target_object, 'last_name', '')}".strip(),
                    'type': target_type
                },
                'available_options': available_options
            }
            
            meta = {
                'operation': 'next_step_options',
                'target_type': target_type,
                'options_count': len(available_options)
            }
            
            return StandardizedSuccessResponse.success(
                message="Next step options retrieved successfully",
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to get next step options")
            )

    @action(detail=True, methods=['post'])
    def process_next_step_choice(self, request, pk=None):
        """
        Process user's choice for next step after successful campaign activity
        UPDATED: Uses enhanced State Machine business result method
        """
        try:

            campaign_target_id = pk

            # Extract and validate required fields using helper
            source_activity_id, choice_type = self._validate_next_step_required_fields(request.data)
            
            # Get and validate campaign target and source activity
            campaign_target, source_activity = self._get_validated_next_step_objects(
                campaign_target_id, source_activity_id
            )
            
            # Import service
            from apps.campaign.services.campaign_business_result_service import CampaignBusinessResultService
            
            # Route to appropriate handler based on choice_type
            if choice_type == 'meeting':
                return self._process_meeting_choice(request.data, campaign_target, source_activity, CampaignBusinessResultService)
            
            elif choice_type == 'lead':
                return self._process_lead_choice(request.data, campaign_target, source_activity, CampaignBusinessResultService)
            
            elif choice_type == 'opportunity':
                return self._process_opportunity_choice(request.data, campaign_target, source_activity, CampaignBusinessResultService)
            
            elif choice_type == 'other':
                return self._process_other_choice(request.data, campaign_target, source_activity, CampaignBusinessResultService)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to process next step choice")
            )
    
    def _validate_next_step_required_fields(self, data):
        """Helper to validate required fields for next step processing"""
        source_activity_id = data.get('source_activity_id')
        choice_type = data.get('choice_type')
        
        if not all([source_activity_id, choice_type]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="source_activity_id and choice_type"
                )
            )
        
        # Validate choice_type
        valid_choices = ['meeting', 'lead', 'opportunity', 'other']
        if choice_type not in valid_choices:
            raise StandardizedValidationError(
                f"Invalid choice_type. Must be one of: {', '.join(valid_choices)}"
            )
        
        return source_activity_id, choice_type
    
    def _get_validated_next_step_objects(self, campaign_target_id, source_activity_id):
        """Helper to get and validate campaign target and source activity"""
        # Get and validate campaign target with optimized query
        try:
            from apps.campaign.models import CampaignTarget
            campaign_target = CampaignTarget.objects.select_related(
                'campaign', 'contact', 'account', 'target_opportunity', 'lead'
            ).get(id=campaign_target_id)
            self.validate_client_id(campaign_target)
            self.validate_campaign_ownership(campaign_target.campaign, allow_stakeholders=True)
        except CampaignTarget.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND + " (campaign target)")
        
        # Get and validate source activity with optimized query
        try:
            source_activity = Activity.objects.select_related(
                'campaign_info__campaign'
            ).get(id=source_activity_id)
            self.validate_client_id(source_activity)
            
            if source_activity.status != Activity.Status.COMPLETED:
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_INVALID_STATE.format(
                        current_state=f"'{source_activity.status}' (Activity result must be COMPLETED)"
                    )
                )
            
            # ✅ CORRIGÉ: Utiliser message standardisé
            if (hasattr(source_activity, 'campaign_info') and 
                source_activity.campaign_info and 
                source_activity.campaign_info.campaign != campaign_target.campaign):
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_NOT_IN_CAMPAIGN
                )
                
        except Activity.DoesNotExist:
            raise StandardizedValidationError(ActivityErrorMessages.ACTIVITY_NOT_FOUND)
        
        return campaign_target, source_activity
    
    def _validate_meeting_date(self, meeting_date):
        """Helper method to validate meeting date (simple validation)"""
        from datetime import date
        
        if meeting_date < date.today():
            raise StandardizedValidationError(
                ActivityErrorMessages.SCHEDULED_DATE_PAST
            )
        
        return meeting_date
    
    def _process_meeting_choice(self, data, campaign_target, source_activity, service):
        """Helper to process meeting choice - UPDATED: Enhanced response handling"""
        contact_id = data.get('contact_id')
        meeting_date = self._parse_date_field(data, 'meeting_date')
        
        if not all([contact_id, meeting_date]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id and meeting_date for meeting creation")
            )
        
        meeting_date = self._validate_meeting_date(meeting_date)
        
        # Service call (already uses enhanced method)
        result = service.create_meeting_next_step(
            campaign_target=campaign_target,
            user=self.request.user,
            meeting_date=meeting_date,
            contact_id=contact_id,
            source_activity=source_activity,
            notes=data.get('notes', '')
        )
        
        if hasattr(result, 'data') and 'data' in result.data:
            result_data = result.data['data']
            if result_data.get('state_machine_used'):
                print(f"STATE_MACHINE_INTEGRATION: Meeting creation used business trigger '{result_data.get('business_trigger')}' for target {campaign_target.id}")

        
        return result
    
    def _process_lead_choice(self, data, campaign_target, source_activity, service):
        """Helper to process lead choice - UPDATED: Enhanced response handling"""
        contact_id = data.get('contact_id')
        lead_title = data.get('lead_title')
        
        if not all([contact_id, lead_title]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id and lead_title for lead creation")
            )
        
        # 🔧 UNCHANGED: Service call (already uses enhanced method)
        result = service.create_lead_next_step(
            campaign_target=campaign_target,
            user=self.request.user,
            contact_id=contact_id,
            source_activity=source_activity,
            lead_title=lead_title,
            description=data.get('description', ''),
            notes=data.get('notes', '')
        )
        
        # Log State Machine integration for audit
        if hasattr(result, 'data') and 'data' in result.data:
            result_data = result.data['data']
            if result_data.get('state_machine_used'):
                print(f"STATE_MACHINE_INTEGRATION: Lead creation used business trigger '{result_data.get('business_trigger')}' for target {campaign_target.id}")

        
        return result

    def _process_opportunity_choice(self, data, campaign_target, source_activity, service):
        """Helper to process opportunity choice - UPDATED: Enhanced response handling"""
        contact_id = data.get('contact_id')
        opportunity_title = data.get('opportunity_title')
        expected_close_date = self._parse_date_field(data, 'expected_close_date')
        
        if not all([contact_id, opportunity_title, expected_close_date]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="contact_id, opportunity_title, and expected_close_date for opportunity creation"
                )
            )
        
        # Parse amount (optional, default to 0)
        amount = 0
        if data.get('amount'):
            try:
                amount = float(data.get('amount'))
            except (ValueError, TypeError):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="amount (must be a number)")
                )
        
        # Service call (already uses enhanced method)
        result = service.create_opportunity_next_step(
            campaign_target=campaign_target,
            user=self.request.user,
            contact_id=contact_id,
            source_activity=source_activity,
            opportunity_title=opportunity_title,
            expected_close_date=expected_close_date,
            amount=amount,
            opportunity_type=data.get('opportunity_type'),
            notes=data.get('notes', '')
        )
        
        # Log State Machine integration for audit
        if hasattr(result, 'data') and 'data' in result.data:
            result_data = result.data['data']
            if result_data.get('state_machine_used'):
                print(f"STATE_MACHINE_INTEGRATION: Opportunity creation used business trigger '{result_data.get('business_trigger')}' for target {campaign_target.id}")

        
        return result

    def _process_other_choice(self, data, campaign_target, source_activity, service):
        """Helper to process other choice - UPDATED: Enhanced response handling"""
        notes = data.get('notes', '')
        if not notes:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="notes for custom action")
            )
        
        # Service call (already uses enhanced method)
        result = service.create_other_next_step(
            campaign_target=campaign_target,
            user=self.request.user,
            source_activity=source_activity,
            notes=notes
        )
        
        # Log State Machine integration for audit
        if hasattr(result, 'data') and 'data' in result.data:
            result_data = result.data['data']
            if result_data.get('state_machine_used'):
                print(f"STATE_MACHINE_INTEGRATION: Other action used business trigger '{result_data.get('business_trigger')}' for target {campaign_target.id}")
        
        return result