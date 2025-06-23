# apps/campaign/views/campaign_views.py - VERSION FINALE COMPLÈTE

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, date
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from core.exceptions import StandardizedValidationError, StandardizedAuthenticationFailed, StandardizedPermissionDenied
from core.error_messages import CampaignErrorMessages, CoreErrorMessages
from core.apps_shared_methods import BaseAPIView

from apps.campaign.models.campaign import Campaign
from apps.campaign.serializers.campaign_serializer import (
    CampaignSerializer,
    CampaignListSerializer,
    CampaignDetailSerializer
)
from apps.campaign.services.campaign_core_service import CampaignCoreService
from apps.campaign.services.campaign_tracking_service import CampaignTrackingService
from apps.campaign.services.campaign_target_service import CampaignTargetService
from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin
from apps.campaign.services.campaign_result_service import CampaignResultService
from apps.activities.models.activity import Activity

# ✅ OPTIMISATION 1: Configuration centralisée
from apps.campaign.config.settings import CONFIG
from apps.campaign.utils.query_optimizer import CampaignQueryOptimizer


class CampaignViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    Unified Campaign ViewSet - Version finale avec optimisations appliquées
    
    Optimisations appliquées:
    - Configuration centralisée (CONFIG)
    - Queries optimisées (CampaignQueryOptimizer)
    - Validation légèrement simplifiée
    - Logique métier complexe conservée intégralement
    
    Réduction réelle: ~800 lignes → ~750 lignes (-6%)
    """
    queryset = Campaign.objects.all()
    entity_name = 'campaign'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    serializer_class = CampaignSerializer
    
    # ✅ OPTIMISATION 1: Configuration centralisée
    filterset_fields = CONFIG.filters.campaign_filters
    search_fields = CONFIG.filters.campaign_search
    ordering_fields = CONFIG.filters.campaign_ordering
    ordering = CONFIG.filters.default_campaign_ordering
    
    def get_serializer_class(self):
        """Use different serializers for different actions - CONSERVÉ"""
        if self.action == 'list':
            return CampaignListSerializer
        elif self.action in ['retrieve', 'dashboard', 'summary']:
            return CampaignDetailSerializer
        return CampaignSerializer
    
    def get_queryset(self):
        """
        ✅ OPTIMISATION 2: Queries optimisées + configuration centralisée
        """
        # Base queryset avec client scoping
        queryset = Campaign.objects.all()
        queryset = self.filter_queryset_by_client(queryset)
        
        # ✅ Optimisation queries automatique
        queryset = CampaignQueryOptimizer.apply_optimization(
            queryset, 'Campaign', getattr(self, 'action', 'list')
        )
        
        # Apply filters using helper methods - CONSERVÉ (logique métier)
        queryset = self._apply_ownership_filters(queryset)
        queryset = self._apply_campaign_attribute_filters(queryset)
        queryset = self._apply_date_filters(queryset)
        
        return queryset

    def _apply_ownership_filters(self, queryset):
        """CONSERVÉ - Logique métier complexe nécessaire"""
        # Filter by owner
        owner_id = self.request.query_params.get(CONFIG.queries.owner)
        if owner_id:
            queryset = queryset.filter(owner_id=owner_id)
        
        # Filter by stakeholder role
        stakeholder_role = self.request.query_params.get(CONFIG.queries.stakeholder_role)
        if stakeholder_role:
            queryset = queryset.filter(
                stakeholder_links__user=self.request.user,
                stakeholder_links__role=stakeholder_role
            ).distinct()
        
        # My campaigns (either owner or any stakeholder)
        my_campaigns = self.request.query_params.get(CONFIG.queries.my_campaigns, None)
        if my_campaigns and my_campaigns.lower() == 'true':
            queryset = queryset.filter(
                Q(owner=self.request.user) | 
                Q(stakeholder_links__user=self.request.user)
            ).distinct()
        
        return queryset

    def _apply_campaign_attribute_filters(self, queryset):
        """CONSERVÉ - Logique métier nécessaire"""
        # Filter by campaign type
        campaign_type = self.request.query_params.get('campaign_type')
        if campaign_type:
            queryset = queryset.filter(campaign_type=campaign_type)
        
        # Filter by status
        campaign_status = self.request.query_params.get(CONFIG.queries.status)
        if campaign_status:
            queryset = queryset.filter(status=campaign_status)
        
        # Filter by sequence type
        sequence_type = self.request.query_params.get('sequence_type')
        if sequence_type:
            if sequence_type.lower() == 'none':
                queryset = queryset.filter(sequence_type__isnull=True)
            else:
                queryset = queryset.filter(sequence_type=sequence_type)
        
        return queryset

    def _apply_date_filters(self, queryset):
        """CONSERVÉ - Logique métier nécessaire"""
        start_after = self.request.query_params.get(CONFIG.queries.start_after)
        start_before = self.request.query_params.get(CONFIG.queries.start_before)
        
        if start_after:
            queryset = queryset.filter(start_date__gte=start_after)
        
        if start_before:
            queryset = queryset.filter(start_date__lte=start_before)
        
        return queryset
    
    # =========================================================================
    # CRUD OPERATIONS - Légèrement simplifiées mais conservées
    # =========================================================================
    
    def perform_create(self, serializer):
        """CONSERVÉ - Logique création spécifique"""
        try:
            client_id = self.get_client_id()
            campaign = serializer.save(
                client_id=client_id,
                owner=self.request.user
            )
            return campaign
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )
    
    def perform_update(self, serializer):
        """✅ Validation légèrement simplifiée avec mixin amélioré"""
        try:
            instance = serializer.instance
            self.validate_campaign_ownership(instance, allow_stakeholders=False)
            return serializer.save()
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state="update failed")
            )
    
    def perform_destroy(self, instance):
        """✅ Validation légèrement simplifiée avec mixin amélioré"""
        try:
            self.validate_campaign_ownership(instance, allow_stakeholders=False)
            instance.delete()
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign deletion failed")
            )
    
    # =========================================================================
    # CAMPAIGN CREATION WITH TARGETS - CONSERVÉ INTÉGRALEMENT
    # =========================================================================
    
    @action(detail=False, methods=['post'])
    def create_with_targets(self, request):
        """
        CONSERVÉ INTÉGRALEMENT - Logique métier complexe essentielle
        Create a campaign with targets and generate activities
        """
        try:
            # Extract input data
            campaign_data = request.data.get('campaign', {})
            target_account_ids = request.data.get('target_account_ids', [])
            target_contact_ids = request.data.get('target_contact_ids', [])
            target_lead_ids = request.data.get('target_lead_ids', [])
            target_opportunity_ids = request.data.get('target_opportunity_ids', [])
            objective_data = request.data.get('objective', {})

            # Validate required fields
            if not campaign_data.get('name'):
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="Campaign name")
                )
            
            if not any([target_account_ids, target_contact_ids, target_lead_ids, target_opportunity_ids]):
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_TARGETS_REQUIRED)
            
            # Validate campaign dates
            start_date = campaign_data.get('start_date')
            end_date = campaign_data.get('end_date')
            if start_date and end_date:
                try:
                    start_dt = datetime.strptime(start_date, CONFIG.time.input_date_format).date()
                    end_dt = datetime.strptime(end_date, CONFIG.time.input_date_format).date()
                    
                    if end_dt < start_dt:
                        raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_DATE_INVALID)
                    if end_dt < date.today():
                        raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_DATE_PAST)
                        
                except ValueError:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="Date format (YYYY-MM-DD expected)")
                    )
            
            # Prepare campaign targets
            target_result = CampaignTargetService.prepare_campaign_targets(
                target_account_ids=target_account_ids,
                target_contact_ids=target_contact_ids,
                target_lead_ids=target_lead_ids,
                target_opportunity_ids=target_opportunity_ids
            )
            
            # Validate that we have valid targets
            stats = target_result['stats']
            if (stats['total_accounts'] == 0 and stats['total_contacts'] == 0 and 
                stats['total_leads'] == 0 and stats['total_opportunities'] == 0):
                raise StandardizedValidationError(
                    "No valid targets found. Check the provided IDs and ensure they exist."
                )
            
            # Set client and ownership
            client_id = self.get_client_id()
            campaign_data['client_id'] = client_id
            campaign_data['owner'] = request.user.id

            if objective_data:
                campaign_data['objective'] = objective_data
            
            print(f"Creating campaign with data: {campaign_data}")

            # Create campaign and activities
            return CampaignCoreService.create_campaign_with_activities(
                request=request,
                campaign_data=campaign_data,
                target_accounts=target_result['target_accounts'],
                target_contacts=target_result['target_contacts'],
                target_leads=target_result['target_leads'],
                target_opportunities=target_result['target_opportunities'],
                targeting_stats=target_result['stats']
            )
            
        except (StandardizedValidationError, StandardizedAuthenticationFailed, StandardizedPermissionDenied):
            raise
        except ValueError as e:
            if "client_id is required" in str(e):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
            raise StandardizedValidationError(f"Campaign creation failed: {str(e)}")
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign creation failed")
            )
    
    # =========================================================================
    # CAMPAIGN LIFECYCLE MANAGEMENT - CONSERVÉ INTÉGRALEMENT
    # =========================================================================
    
    @action(detail=True, methods=['post'])
    def start_campaign(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(require_ownership=True)
        return CampaignCoreService.start_campaign(campaign)
    
    @action(detail=True, methods=['post'])
    def pause_campaign(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(require_ownership=True)
        
        pause_until = request.data.get('pause_until', None)
        if pause_until:
            pause_until = datetime.strptime(pause_until, '%Y-%m-%d').date()
        
        return CampaignCoreService.pause_campaign(campaign, pause_until=pause_until)
    
    @action(detail=True, methods=['post'])
    def resume_campaign(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(require_ownership=True)
        return CampaignCoreService.resume_campaign(campaign)
    
    # =========================================================================
    # CAMPAIGN EXECUTION - CONSERVÉ INTÉGRALEMENT
    # =========================================================================
    
    @action(detail=True, methods=['get'])
    def playlist(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(require_ownership=True, check_state=False)
        
        limit = int(request.query_params.get(CONFIG.queries.limit, CONFIG.limits.playlist_limit))
        return CampaignCoreService.get_campaign_playlist(campaign, limit=limit)
    
    @action(detail=True, methods=['get'])
    def contacts_with_responses(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        return CampaignCoreService.get_campaign_contacts_with_responses(campaign)
    
    # =========================================================================
    # CAMPAIGN MANAGEMENT - CONSERVÉ INTÉGRALEMENT
    # =========================================================================
    
    @action(detail=True, methods=['post'])
    def remove_account(self, request, pk=None):
        """CONSERVÉ INTÉGRALEMENT - Logique métier complexe"""
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True,
                check_state=True
            )
            
            account_id = request.data.get('account_id')
            notes = request.data.get('notes')
            
            if not account_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="Account ID")
                )
            
            account = self._get_validated_account(account_id)
            
            # Validate account is actually targeted by this campaign
            campaign_target = campaign.targets.filter(account=account).first()
            if not campaign_target:
                raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
            return CampaignCoreService.remove_account_from_campaign(
                campaign=campaign,
                account=account,
                notes=notes
            )
            
        except (StandardizedValidationError, StandardizedPermissionDenied):
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to remove account from campaign")
            )
    
    @action(detail=True, methods=['post'])
    def remove_contact(self, request, pk=None):
        """CONSERVÉ INTÉGRALEMENT - Logique métier complexe"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True,
            check_state=True
        )
        
        contact_id = request.data.get('contact_id')
        notes = request.data.get('notes')
        
        if not contact_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Contact ID")
            )
        
        contact = self._get_validated_contact(contact_id)
        
        return CampaignCoreService.remove_contact_from_campaign(
            campaign=campaign,
            contact=contact,
            notes=notes
        )
    
    @action(detail=True, methods=['post'], url_path='add-manual-activity')
    def add_manual_activity(self, request, pk=None):
        """CONSERVÉ INTÉGRALEMENT - Logique métier complexe"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Verify this is a non-sequence campaign
        if campaign.sequence_type:
            raise StandardizedValidationError(
                "This operation is only for campaigns without sequences"
            )
        
        # Validate required fields
        contact_id = request.data.get(CONFIG.fields.contact_id)
        activity_type = request.data.get('activity_type')
        result = request.data.get(CONFIG.fields.result)
        
        if not all([contact_id, activity_type, result]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id, activity_type, and result")
            )
        
        try:
            # Get the contact
            from apps.accounts.models import Contact
            contact = Contact.objects.get(id=contact_id)
            self.validate_client_id(contact)
            
            # Get the campaign target for this contact
            target = None
            for t in campaign.targets.all():
                if t.contact_id == contact_id:
                    target = t
                    break
                    
                # Check if contact belongs to this target's account
                if (t.account_id == contact.account_id or 
                    (t.lead and t.lead.account_id == contact.account_id) or
                    (t.target_opportunity and t.target_opportunity.account_id == contact.account_id)):
                    target = t
                    break
            
            if not target:
                raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
            # Prepare additional data
            kwargs = {}
            if request.data.get('meeting_date'):
                kwargs['meeting_date'] = datetime.strptime(
                    request.data.get('meeting_date'), '%Y-%m-%d'
                ).date()
            
            if request.data.get('callback_date'):
                kwargs['callback_date'] = datetime.strptime(
                    request.data.get('callback_date'), '%Y-%m-%d'
                ).date()
            
            return CampaignCoreService.add_manual_activity_to_campaign(
                campaign=campaign,
                contact=contact,
                activity_type=activity_type,
                result=result,
                notes=request.data.get('notes', ''),
                user=request.user,
                **kwargs
            )
            
        except Contact.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    
    # =========================================================================
    # ANALYTICS & REPORTING - CONSERVÉ INTÉGRALEMENT
    # =========================================================================
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """CONSERVÉ INTÉGRALEMENT - Logique métier complexe"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Use CampaignCoreService for base summary
        summary_response = CampaignCoreService.get_campaign_summary(campaign)
        
        # Extract and enhance data using helper methods
        if hasattr(summary_response, 'data') and 'data' in summary_response.data:
            base_data = summary_response.data['data']
            enhanced_data = self._enhance_summary_data(campaign, base_data)
            
            return StandardizedSuccessResponse.success(
                message="Campaign summary retrieved successfully",
                data=enhanced_data,
                meta=self._build_summary_meta(enhanced_data)
            )
        else:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )

    def _enhance_summary_data(self, campaign, base_data):
        """CONSERVÉ - Helper nécessaire"""
        enhanced_data = base_data.copy()
        enhanced_data['objectives'] = self._get_objectives_summary(campaign)
        enhanced_data['detailed_targets'] = self._get_targets_summary(campaign)
        enhanced_data['target_breakdown'] = campaign.get_target_summary()
        return enhanced_data

    def _get_objectives_summary(self, campaign):
        """CONSERVÉ - Helper nécessaire"""
        objectives = campaign.objectives.all()
        return [
            {
                'id': obj.id,
                'name': obj.name,
                'objective_type': obj.objective_type,
                'objective_type_display': obj.get_objective_type_display(),
                'target_value': obj.target_value,
                'current_value': obj.current_value,
                'progress_percentage': obj.progress_percentage()
            } for obj in objectives
        ]

    def _get_targets_summary(self, campaign):
        """CONSERVÉ - Helper nécessaire"""
        targets = campaign.targets.all()
        target_counts = {
            'total': targets.count(),
            'by_status': {}
        }
        
        # Count targets by status
        from apps.campaign.models.campaign_target import CampaignTarget
        for status_choice in CampaignTarget.Status.choices:
            status_code = status_choice[0]
            status_display = status_choice[1]
            count = targets.filter(status=status_code).count()
            target_counts['by_status'][status_code] = {
                'display': status_display,
                'count': count
            }
        
        return target_counts

    def _build_summary_meta(self, enhanced_data):
        """CONSERVÉ - Helper nécessaire"""
        return {
            'operation': 'campaign_summary_detailed',
            'objectives_count': len(enhanced_data.get('objectives', [])),
            'targets_count': enhanced_data.get('detailed_targets', {}).get('total', 0)
        }
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Parse status filter
        status_filter = None
        status_param = request.query_params.get('status')
        if status_param:
            status_filter = status_param.split(',')
        
        return CampaignCoreService.get_campaign_activities(
            campaign=campaign,
            status_filter=status_filter
        )

    @action(detail=True, methods=['get'])
    def account_activities(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Get account ID
        account_id = request.query_params.get('account_id')
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
            )
        
        # Parse status filter
        status_filter = None
        status_param = request.query_params.get('status')
        if status_param:
            status_filter = status_param.split(',')
        
        account = self._get_validated_account(account_id)
            
        return CampaignCoreService.get_account_activities_in_campaign(
            campaign=campaign,
            account=account,
            status_filter=status_filter
        )

    @action(detail=True, methods=['get'])
    def contact_activities(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Get contact ID
        contact_id = request.query_params.get('contact_id')
        if not contact_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id")
            )
    
        contact = self._get_validated_contact(contact_id)
        
        # Parse status filter
        status_filter = None
        status_param = request.query_params.get('status')
        if status_param:
            status_filter = status_param.split(',')
                    
        return CampaignCoreService.get_contact_activities_in_campaign(
            campaign=campaign,
            contact=contact,
            status_filter=status_filter
        )
    
    # =========================================================================
    # DASHBOARD UNIFIÉ - OPTIMISÉ 
    # =========================================================================
    
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """
        ✅ OPTIMISÉ - Dashboard unifié configurab avec queries optimisées
        """
        try:
            # ✅ Utiliser queryset optimisé pour dashboard
            campaign = Campaign.objects.filter(pk=pk, client_id=self.get_client_id())
            optimized_campaign = CampaignQueryOptimizer.get_dashboard_optimized_queryset(
                campaign
            ).first()
            
            if not optimized_campaign:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Validation permissions avec mixin amélioré
            self.validate_campaign_ownership(optimized_campaign, allow_stakeholders=True)
            
            # Parse query parameters
            include_param = request.query_params.get('include', '')
            format_param = request.query_params.get('format', 'detailed')
            
            # Parse included sections
            if include_param:
                included_sections = [s.strip() for s in include_param.split(',')]
            else:
                if format_param == 'summary':
                    included_sections = ['basic', 'metrics']
                else:
                    included_sections = ['basic', 'objectives', 'tracking', 'activities', 'targets']
            
            # Validate format parameter
            if format_param not in ['detailed', 'summary']:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="format (must be 'detailed' or 'summary')")
                )
            
            # Build dashboard data with optimized queries
            dashboard_data = self._build_optimized_dashboard_data(
                optimized_campaign, included_sections, format_param
            )
            
            meta = {
                'operation': 'unified_campaign_dashboard',
                'campaign_id': optimized_campaign.id,
                'format': format_param,
                'included_sections': included_sections,
                'query_optimized': True,
                'data_timestamp': timezone.now().isoformat()
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Dashboard data retrieved for campaign '{optimized_campaign.name}' ({format_param} format)",
                data=dashboard_data,
                meta=meta
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to generate campaign dashboard")
            )
    
    def _build_optimized_dashboard_data(self, campaign, included_sections, format_param):
        """
        ✅ OPTIMISÉ - Construit dashboard avec données pré-chargées
        Utilise les annotations du CampaignQueryOptimizer pour éviter N+1 queries
        """
        dashboard_data = {}
        
        # Basic campaign information (always included)
        dashboard_data['campaign_info'] = {
            'id': campaign.id,
            'name': campaign.name,
            'type': campaign.campaign_type,
            'type_display': campaign.get_campaign_type_display(),
            'status': campaign.status,
            'start_date': campaign.start_date.isoformat(),
            'end_date': campaign.end_date.isoformat(),
            'has_sequence': campaign.sequence_type is not None,
            'sequence_type': campaign.sequence_type
        }
        
        # Metrics section - utilise les annotations pré-calculées
        if 'metrics' in included_sections or 'basic' in included_sections:
            if format_param == 'summary':
                # Utilise les annotations du QueryOptimizer
                dashboard_data['metrics'] = {
                    'total_targets': getattr(campaign, 'total_targets', 0),
                    'active_targets': getattr(campaign, 'active_targets', 0),
                    'completed_targets': getattr(campaign, 'completed_targets', 0),
                    'total_activities': getattr(campaign, 'total_activities', 0),
                    'completed_activities': getattr(campaign, 'completed_activities', 0),
                    'pending_activities': getattr(campaign, 'pending_activities', 0),
                }
            else:
                # Detailed metrics using tracking service
                dashboard_data['metrics'] = CampaignTrackingService.get_campaign_metrics(campaign)
        
        # Objectives section - utilise les données préchargées
        if 'objectives' in included_sections:
            if hasattr(campaign, 'dashboard_objectives'):
                # Dashboard optimized - primary objective only
                primary_obj = campaign.dashboard_objectives[0] if campaign.dashboard_objectives else None
                dashboard_data['objectives'] = {
                    'primary_objective': {
                        'id': primary_obj.id,
                        'name': primary_obj.name,
                        'progress_percentage': primary_obj.progress_percentage()
                    } if primary_obj else None
                }
            else:
                # Standard optimization - all objectives (already prefetched)
                objectives = list(campaign.objectives.all())
                dashboard_data['objectives'] = [
                    {
                        'id': obj.id,
                        'name': obj.name,
                        'progress_percentage': obj.progress_percentage(),
                        'is_primary': obj.is_primary
                    } for obj in objectives
                ]
        
        # Tracking section (analytics détaillées)
        if 'tracking' in included_sections:
            if format_param == 'detailed':
                analytics_response = CampaignAnalyticsService.get_campaign_dashboard_data(campaign)
                if hasattr(analytics_response, 'data') and 'data' in analytics_response.data:
                    dashboard_data['tracking'] = analytics_response.data['data']
                else:
                    dashboard_data['tracking'] = {'error': 'Analytics data unavailable'}
            else:
                dashboard_data['tracking'] = {
                    'activities_completed': getattr(campaign, 'completed_activities', 0),
                    'activities_pending': getattr(campaign, 'pending_activities', 0)
                }
        
        # Activities et Targets sections (conservées comme avant)
        if 'activities' in included_sections:
            if format_param == 'summary':
                dashboard_data['activities'] = {
                    'total_count': getattr(campaign, 'total_activities', 0),
                    'completed_count': getattr(campaign, 'completed_activities', 0),
                    'pending_count': getattr(campaign, 'pending_activities', 0)
                }
            else:
                # Get recent activities
                recent_activities = Activity.objects.filter(
                    campaign_target__campaign=campaign
                ).order_by('-created_at')[:10]
                
                dashboard_data['activities'] = {
                    'total_count': getattr(campaign, 'total_activities', 0),
                    'completed_count': getattr(campaign, 'completed_activities', 0),
                    'pending_count': getattr(campaign, 'pending_activities', 0),
                    'recent_activities': [
                        {
                            'id': activity.id,
                            'type': activity.activity_type,
                            'status': activity.status,
                            'created_at': activity.created_at.isoformat()
                        } for activity in recent_activities
                    ]
                }
        
        # Targets section
        if 'targets' in included_sections:
            if format_param == 'summary':
                dashboard_data['targets'] = campaign.get_target_summary()
            else:
                dashboard_data['targets'] = self._get_targets_summary(campaign)
        
        return dashboard_data
    
    # =========================================================================
    # UTILITY ENDPOINTS - CONSERVÉ INTÉGRALEMENT
    # =========================================================================
    
    @action(detail=False, methods=['get'])
    def account_campaigns(self, request):
        """CONSERVÉ INTÉGRALEMENT - Logique métier complexe"""
        account_id = request.query_params.get(CONFIG.queries.account_id)
        
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
            )

        account = self._get_validated_account(account_id)
            
        # Get campaign targets for this account
        from apps.campaign.models.campaign_target import CampaignTarget
        targets = CampaignTarget.objects.filter(
                account=account
            ).select_related('campaign', 'campaign__owner')
            
        # Format response
        campaigns_data = []
        for target in targets:
            campaign = target.campaign
            campaigns_data.append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'campaign_type': campaign.campaign_type,
                'campaign_type_display': campaign.get_campaign_type_display(),
                'start_date': campaign.start_date,
                'end_date': campaign.end_date,
                'owner_name': f"{campaign.owner.first_name} {campaign.owner.last_name}",
                'status': target.status,
                'status_display': target.get_status_display()
            })
        
        # Return standardized response
        data = {
            'account_id': account.id,
            'account_name': account.company_name,
            'campaigns': campaigns_data
        }
        
        meta = {
            'operation': 'account_campaigns_retrieval',
            'campaigns_count': len(campaigns_data)
        }
        
        return StandardizedSuccessResponse.success(
            message=f"Retrieved {len(campaigns_data)} campaigns for account {account.company_name}",
            data=data,
            meta=meta
        )
    

# =========================================================================
# ACTIVITYRESULTVIEWSET - DÉJÀ OPTIMISÉ (étape 2.2)
# =========================================================================

class ActivityResultViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ViewSet):
    """
    ViewSet for handling activity results and completion
    ✅ DÉJÀ OPTIMISÉ dans étape 2.2 - Version finale
    """
    
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
        
    @action(detail=False, methods=['get'])
    def get_next_step_options(self, request):
        """
        Get available next step options based on campaign target type - Unchanged
        
        Query params:
        - campaign_target_id: ID of the campaign target
        """
        try:
            campaign_target_id = request.query_params.get('campaign_target_id')
            
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
                self.validate_campaign_ownership(campaign_target, allow_stakeholders=True)
                
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

    @action(detail=False, methods=['post'])
    def process_next_step_choice(self, request):
        """
        Process user's choice for next step after successful campaign activity
        UPDATED: Uses enhanced State Machine business result method
        """
        try:
            # Extract and validate required fields using helper
            campaign_target_id, source_activity_id, choice_type = self._validate_next_step_required_fields(request.data)
            
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
        campaign_target_id = data.get('campaign_target_id')
        source_activity_id = data.get('source_activity_id')
        choice_type = data.get('choice_type')
        
        if not all([campaign_target_id, source_activity_id, choice_type]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="campaign_target_id, source_activity_id, and choice_type"
                )
            )
        
        # Validate choice_type
        valid_choices = ['meeting', 'lead', 'opportunity', 'other']
        if choice_type not in valid_choices:
            raise StandardizedValidationError(
                f"Invalid choice_type. Must be one of: {', '.join(valid_choices)}"
            )
        
        return campaign_target_id, source_activity_id, choice_type
    
    def _get_validated_next_step_objects(self, campaign_target_id, source_activity_id):
        """Helper to get and validate campaign target and source activity"""
        # Get and validate campaign target
        try:
            from apps.campaign.models import CampaignTarget
            campaign_target = CampaignTarget.objects.get(id=campaign_target_id)
            self.validate_client_id(campaign_target)
            self.validate_campaign_ownership(campaign_target, allow_stakeholders=True)
        except CampaignTarget.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND + " (campaign target)")
        
        # Get and validate source activity
        try:
            source_activity = Activity.objects.get(id=source_activity_id)
            self.validate_client_id(source_activity)
        except Activity.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND + " (source activity)")
        
        return campaign_target, source_activity
    
    def _process_meeting_choice(self, data, campaign_target, source_activity, service):
        """Helper to process meeting choice - UPDATED: Enhanced response handling"""
        contact_id = data.get('contact_id')
        meeting_date = self._parse_date_field(data, 'meeting_date')
        
        if not all([contact_id, meeting_date]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id and meeting_date for meeting creation")
            )
        
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