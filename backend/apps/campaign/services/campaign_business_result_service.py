# apps/campaign/services/campaign_business_result_service.py
from typing import Dict, Optional
from datetime import date, datetime
from django.utils import timezone
from django.db import transaction
from rest_framework.response import Response
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact, Account
from apps.activities.models import Activity, ActivityCampaign
from apps.leads.models import Lead
from apps.opportunities.models import Opportunity, OpportunitySource, OpportunityFinancialSummary
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.campaign.services.campaign_tracking_service import CampaignTrackingService


class CampaignBusinessResultService:
    """
    Service for creating business objects as next steps from successful campaign activities
    Handles meeting creation, lead generation, and opportunity creation with proper attribution
    """
    
    @classmethod
    def create_meeting_next_step(cls, campaign_target: CampaignTarget, user, 
                               meeting_date: date, contact_id: int, source_activity: Activity,
                               notes: str = None) -> Response:
        """
        Create a meeting activity as next step from successful campaign result
        """
        try:
            with transaction.atomic():
                target_object = campaign_target.get_target()
                campaign = campaign_target.campaign
                
                # Get specified contact and validate
                try:
                    contact = Contact.objects.get(id=contact_id, client_id=campaign.client_id)
                except Contact.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND + " (contact)"
                    )
                
                # Validate contact belongs to target account
                target_account = getattr(target_object, 'account', target_object)
                if contact.account != target_account:
                    raise StandardizedValidationError(
                        "Selected contact must belong to the target account"
                    )
                
                # Create meeting activity
                meeting_activity = Activity.objects.create(
                    title=f"Meeting with {contact.first_name} {contact.last_name}",
                    activity_type=Activity.ActivityType.MEETING,
                    description=f"Follow-up meeting from campaign: {campaign.name}. {notes}" if notes else f"Follow-up meeting from campaign: {campaign.name}",
                    account=target_account,
                    owner=user,
                    scheduled_start=timezone.make_aware(
                        timezone.datetime.combine(meeting_date, timezone.datetime.min.time().replace(hour=10))
                    ),
                    status=Activity.Status.PLANNED,
                    client_id=campaign.client_id
                )
                
                # Link contact to meeting
                meeting_activity.contacts.set([contact])
                
                # Link meeting to campaign for tracking origin
                ActivityCampaign.objects.create(
                    activity=meeting_activity,
                    campaign=campaign,
                    campaign_target=campaign_target,
                    client_id=campaign.client_id
                )

                from apps.campaign.services.campaign_result_service import CampaignResultService
                status_update_result = CampaignResultService.update_campaign_target_status_for_business_result(
                campaign_target=campaign_target, 
                business_result_type='meeting',
                user=user,
                notes=f"Meeting scheduled with {contact.first_name} {contact.last_name} for {meeting_date}" + 
                      (f": {notes}" if notes else "")
            )

            try:
                CampaignTrackingService.track_meeting_scheduled(meeting_activity, campaign)
            except Exception as e:
                # Silent fail pour MVP - ne pas casser la création du meeting
                print(f"Warning: Failed to track meeting {meeting_activity.id} for campaign {campaign.id}: {str(e)}")
            
            
            return StandardizedSuccessResponse.success(
                message="Meeting scheduled successfully",
                data={
                    'type': 'meeting',
                    'meeting_id': meeting_activity.id,
                    'meeting_date': meeting_date,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'account_name': target_account.company_name,
                    'campaign_id': campaign.id,
                    'target_status_updated': status_update_result.get('status_updated', False),
                    'new_target_status': status_update_result.get('new_status'),
                    'state_machine_used': status_update_result.get('state_machine_used', False),
                    'business_trigger': status_update_result.get('business_trigger_used')
                },
                meta={
                'operation': 'meeting_creation_from_campaign',
                'state_machine_integration': True 
            }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Meeting creation failed: {str(e)}")
            )
    
    @classmethod
    def create_lead_next_step(cls, campaign_target: CampaignTarget, user, contact_id: int,
                            source_activity: Activity, lead_title: str, 
                            description: str = None, notes: str = None) -> Response:
        """
        Create a lead as next step from successful campaign result
        Only valid for account/contact targets
        """
        try:
            target_type = campaign_target.get_target_type()
            if target_type not in ['account', 'contact']:
                raise StandardizedValidationError(
                    "Lead creation only available for account or contact targets"
                )
            
            with transaction.atomic():
                target_object = campaign_target.get_target()
                campaign = campaign_target.campaign
                
                # Get specified contact and validate
                try:
                    contact = Contact.objects.get(id=contact_id, client_id=campaign.client_id)
                except Contact.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND + " (contact)"
                    )
                
                # Validate contact belongs to target account
                target_account = getattr(target_object, 'account', target_object)
                if contact.account != target_account:
                    raise StandardizedValidationError(
                        "Selected contact must belong to the target account"
                    )
                
                # Create lead
                lead = Lead.objects.create(
                    title=lead_title,
                    description=description or f"Lead generated from campaign: {campaign.name}",
                    contact=contact,
                    account=target_account,
                    campaign=campaign,  # Attribution to source campaign
                    source_activity=source_activity,  # Attribution to successful activity
                    lead_source=Lead.LeadSource.CAMPAIGN,
                    assigned_to=user,
                    notes=notes,
                    client_id=campaign.client_id,
                    created_by=user,
                    updated_by=user
                )

                from apps.campaign.services.campaign_result_service import CampaignResultService
                status_update_result = CampaignResultService.update_campaign_target_status_for_business_result(
                    campaign_target=campaign_target,
                    business_result_type='lead',
                    user=user,
                    notes=f"Lead '{lead_title}' created for {contact.first_name} {contact.last_name}" +
                        (f": {notes}" if notes else "")
                )
       
                
                # Track lead creation
                try:
                    CampaignTrackingService.track_lead_created(lead, campaign)
                except Exception as e:
                    # Silent fail pour MVP - ne pas casser la création du lead
                    print(f"Warning: Failed to track lead {lead.id} for campaign {campaign.id}: {str(e)}")
            
            return StandardizedSuccessResponse.success(
                message="Lead created successfully",
                data={
                    'type': 'lead',
                    'lead_id': lead.id,
                    'lead_title': lead.title,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'account_name': target_account.company_name,
                    'campaign_id': campaign.id,
                    'target_status_updated': status_update_result.get('status_updated', False),
                    'new_target_status': status_update_result.get('new_status'),
                    # 🔧 NEW: Add State Machine integration info
                    'state_machine_used': status_update_result.get('state_machine_used', False),
                    'business_trigger': status_update_result.get('business_trigger_used')
                    # 🔧 END NEW
                },
                meta={
                    'operation': 'lead_creation_from_campaign',
                    'state_machine_integration': True  # 🔧 NEW
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Lead creation failed: {str(e)}")
            )
        
    @classmethod
    def create_opportunity_next_step(cls, campaign_target: CampaignTarget, user, contact_id: int,
                                source_activity: Activity, opportunity_title: str,
                                expected_close_date: date, amount: float = 0,
                                opportunity_type: str = None, notes: str = None) -> Response:
        """
        Create an opportunity as next step from successful campaign result
        Valid for account/contact/lead targets
        """
        try:
            target_type = campaign_target.get_target_type()
            if target_type not in ['account', 'contact', 'lead']:
                raise StandardizedValidationError(
                    "Opportunity creation only available for account, contact, or lead targets"
                )
            
            with transaction.atomic():
                target_object = campaign_target.get_target()
                campaign = campaign_target.campaign
                
                # Get specified contact and validate
                try:
                    contact = Contact.objects.get(id=contact_id, client_id=campaign.client_id)
                except Contact.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND + " (contact)"
                    )
                
                # Determine target account based on target type
                if target_type == 'lead':
                    target_account = target_object.account
                else:
                    target_account = getattr(target_object, 'account', target_object)
                
                # Validate contact belongs to target account
                if contact.account != target_account:
                    raise StandardizedValidationError(
                        "Selected contact must belong to the target account"
                    )
                
                # Set default opportunity type if not provided
                if not opportunity_type:
                    opportunity_type = Opportunity.OpportunityType.NEW_BUSINESS
                
                # Create opportunity
                opportunity = Opportunity.objects.create(
                    title=opportunity_title,
                    description=f"Opportunity generated from campaign: {campaign.name}. {notes}" if notes else f"Opportunity generated from campaign: {campaign.name}",
                    account=target_account,
                    contact=contact,
                    deal_owner=user,
                    opportunity_type=opportunity_type,
                    expected_close_date=expected_close_date,
                    notes=notes,
                    client_id=campaign.client_id,
                    created_by=user,
                    updated_by=user
                )
                
                # Create financial summary with amount if provided
                financial_summary = OpportunityFinancialSummary.objects.create(
                    opportunity=opportunity,
                    total_amount=amount,
                    client_id=campaign.client_id
                )
                
                # Create opportunity source tracking
                source_type = OpportunitySource.SourceType.CAMPAIGN
                if target_type == 'lead':
                    source_type = OpportunitySource.SourceType.LEAD
                
                OpportunitySource.objects.create(
                    opportunity=opportunity,
                    source_type=source_type,
                    source_campaign=campaign,
                    source_campaign_target=campaign_target,
                    source_lead=target_object if target_type == 'lead' else None,
                    created_by=user,
                    conversion_status=OpportunitySource.ConversionStatus.NOT_APPLICABLE,
                    client_id=campaign.client_id
                )

                from apps.campaign.services.campaign_result_service import CampaignResultService
                status_update_result = CampaignResultService.update_campaign_target_status_for_business_result(
                    campaign_target=campaign_target,
                    business_result_type='opportunity',
                    user=user,
                    notes=f"Opportunity '{opportunity_title}' created for {contact.first_name} {contact.last_name}, amount: ${amount}" +
                        (f": {notes}" if notes else "")
                )

                
                # Track opportunity creation
                try:
                    CampaignTrackingService.track_opportunity_created(opportunity, campaign, amount)
                except Exception as e:
                    # Silent fail pour MVP - ne pas casser la création de l'opportunity
                    print(f"Warning: Failed to track opportunity {opportunity.id} for campaign {campaign.id}: {str(e)}")
            
            
            return StandardizedSuccessResponse.success(
                message="Opportunity created successfully",
                data={
                    'type': 'opportunity',
                    'opportunity_id': opportunity.id,
                    'opportunity_title': opportunity.title,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'account_name': target_account.company_name,
                    'amount': amount,
                    'expected_close_date': expected_close_date,
                    'campaign_id': campaign.id,
                    'target_status_updated': status_update_result.get('status_updated', False),
                    'new_target_status': status_update_result.get('new_status'),
                    # 🔧 NEW: Add State Machine integration info
                    'state_machine_used': status_update_result.get('state_machine_used', False),
                    'business_trigger': status_update_result.get('business_trigger_used')
                    # 🔧 END NEW
                },
                meta={
                    'operation': 'opportunity_creation_from_campaign',
                    'state_machine_integration': True  # 🔧 NEW
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Opportunity creation failed: {str(e)}")
            )

    @classmethod
    def create_other_next_step(cls, campaign_target: CampaignTarget, user, 
                            source_activity: Activity, notes: str) -> Response:
        """
        Handle 'other' next step - just record the custom action with notes
        """
        try:
            campaign = campaign_target.campaign

            from apps.campaign.services.campaign_result_service import CampaignResultService
            status_update_result = CampaignResultService.update_campaign_target_status_for_business_result(
                campaign_target=campaign_target,
                business_result_type='other',
                user=user,
                notes=f"Custom next step: {notes}"
            )

            
            # Just return success with notes recorded
            # Could extend this to create a custom activity or note if needed
            
            return StandardizedSuccessResponse.success(
                message="Custom next step recorded successfully",
                data={
                    'type': 'other',
                    'notes': notes,
                    'campaign_id': campaign.id,
                    'source_activity_id': source_activity.id,
                    'target_status_updated': status_update_result.get('status_updated', False),
                    'new_target_status': status_update_result.get('new_status'),
                    # 🔧 NEW: Add State Machine integration info
                    'state_machine_used': status_update_result.get('state_machine_used', False),
                    'business_trigger': status_update_result.get('business_trigger_used')
                    # 🔧 END NEW
                },
                meta={
                    'operation': 'other_next_step_from_campaign',
                    'state_machine_integration': True  # 🔧 NEW
                }
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Custom next step failed: {str(e)}")
            )