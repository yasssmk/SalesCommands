# apps/campaign/views/campaign_views.py 

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, date
from django.utils import timezone
from django.db.models import Q, Prefetch
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
    
        
        # Apply filters using helper methods - CONSERVÉ (logique métier)
        queryset = self._apply_ownership_filters(queryset)
        queryset = self._apply_campaign_attribute_filters(queryset)
        queryset = self._apply_date_filters(queryset)
        
        # ✅ Optimisation queries automatique
        if self.action in ['retrieve', 'dashboard', 'summary']:
            # Optimisation spécialisée pour vues détail
            return self._optimize_for_detail_view(queryset)
        elif self.action == 'list':
            # Optimisation légère pour vue liste
            return CampaignQueryOptimizer.optimize_campaigns_queryset(queryset, 'standard')
        else:
            # Optimisation automatique par action
            return CampaignQueryOptimizer.apply_optimization(
                queryset, 'Campaign', getattr(self, 'action', 'list')
            )
    
    def _optimize_for_detail_view(self, queryset):
        """
        ✅ OPTIMISATION SPÉCIALISÉE pour CampaignDetailSerializer
        Combine l'optimiseur existant avec des optimisations spécifiques
        """
        # Base optimization via CampaignQueryOptimizer
        optimized_queryset = CampaignQueryOptimizer.optimize_campaigns_queryset(queryset, 'standard')
        
        # ✅ AJOUTS SPÉCIFIQUES pour les nouveaux champs du DetailSerializer
        return optimized_queryset.select_related(
            # Relations essentielles pour result_tracking
            'result_tracking'
        ).prefetch_related(
            # ✅ CORRIGÉ: Utiliser la même relation que CampaignAnalyticsService
            # Pas de prefetch direct car relation inversée complexe - on laissera le service faire ses queries
        )
    
    
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
        # campaign_type = self.request.query_params.get('campaign_type')
        # if campaign_type:
        #     queryset = queryset.filter(campaign_type=campaign_type)
        
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
        return CampaignCoreService.start_campaign(campaign, user=request.user)
    
    @action(detail=True, methods=['post'])
    def pause_campaign(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(require_ownership=True)
        
        pause_until = request.data.get('pause_until', None)
        if pause_until:
            pause_until = datetime.strptime(pause_until, '%Y-%m-%d').date()
        
        return CampaignCoreService.pause_campaign(campaign, pause_until=pause_until, user=request.user)
    
    @action(detail=True, methods=['post'])
    def resume_campaign(self, request, pk=None):
        """CONSERVÉ - Logique métier essentielle"""
        campaign = self.get_validated_campaign(require_ownership=True)
        return CampaignCoreService.resume_campaign(campaign, user=request.user)
    
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
                'current_value': obj.get_current_value(),  
                'progress_percentage': obj.get_progress_percentage()
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
        ✅ CORRIGÉ - Dashboard unifié avec gestion d'erreurs standardisée
        """
        try:
            # ✅ TENTATIVE PRINCIPALE: Utiliser queryset optimisé pour dashboard
            campaign = Campaign.objects.filter(pk=pk, client_id=self.get_client_id())
            
            try:
                optimized_campaign = CampaignQueryOptimizer.get_dashboard_optimized_queryset(
                    campaign
                ).first()
            except StandardizedValidationError as optimizer_error:
                # ✅ FALLBACK GÉRÉ: Si l'optimiseur échoue, utiliser queryset standard
                print(f"Dashboard optimizer failed, using standard queryset: {optimizer_error}")
                
                optimized_campaign = campaign.select_related('owner').prefetch_related(
                    'objectives'
                ).first()
                
                if optimized_campaign:
                    # ✅ AJOUTER ATTRIBUTS MANQUANTS pour compatibilité
                    optimized_campaign.total_targets = optimized_campaign.targets.count()
                    optimized_campaign.active_targets = optimized_campaign.targets.filter(status='ACTIVE').count()
                    optimized_campaign.completed_targets = optimized_campaign.targets.filter(status='COMPLETED').count()
                    optimized_campaign.total_activities = 0  # Valeur par défaut sécurisée
                    optimized_campaign.completed_activities = 0
                    optimized_campaign.pending_activities = 0
                    
                    # Calculer les vraies valeurs d'activités si possible
                    try:
                        from apps.activities.models import Activity
                        activity_qs = Activity.objects.filter(
                            campaign_info__campaign_target__campaign=optimized_campaign
                        )
                        optimized_campaign.total_activities = activity_qs.count()
                        optimized_campaign.completed_activities = activity_qs.filter(status='COMPLETED').count()
                        optimized_campaign.pending_activities = activity_qs.filter(status='PLANNED').count()
                    except Exception:
                        # Si le calcul échoue, garder les valeurs par défaut (0)
                        pass
            
            if not optimized_campaign:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # ✅ VALIDATION PERMISSIONS avec mixin amélioré
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
            
            # ✅ BUILD DASHBOARD DATA avec gestion d'erreurs robuste
            try:
                dashboard_data = self._build_optimized_dashboard_data(
                    optimized_campaign, included_sections, format_param
                )
            except Exception as dashboard_error:
                # ✅ FALLBACK DASHBOARD: Données minimales mais fonctionnelles
                print(f"Dashboard data building failed, using minimal data: {dashboard_error}")
                
                dashboard_data = self._build_minimal_dashboard_data(
                    optimized_campaign, included_sections, format_param
                )
            
            meta = {
                'operation': 'unified_campaign_dashboard',
                'campaign_id': optimized_campaign.id,
                'format': format_param,
                'included_sections': included_sections,
                'query_optimized': hasattr(optimized_campaign, 'total_targets'),
                'data_timestamp': timezone.now().isoformat(),
                'fallback_used': not hasattr(optimized_campaign, 'total_targets'),
                'services_used': ['CampaignTrackingService']  # ✅ NOUVEAU: Indiquer les services utilisés
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Dashboard data retrieved for campaign '{optimized_campaign.name}' ({format_param} format)",
                data=dashboard_data,
                meta=meta
            )
            
        except StandardizedValidationError:
            # ✅ Re-raise standardized validation errors
            raise
        except Exception as e:
            # ✅ GESTION D'ERREURS STANDARDISÉE
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Failed to generate campaign dashboard: {str(e)}")
            )
    
    def _build_minimal_dashboard_data(self, campaign, included_sections, format_param):
        """
        ✅ NOUVEAU: Construit dashboard avec données minimales sécurisées
        Utilisé comme fallback quand l'optimisation échoue
        """
        dashboard_data = {}
        
        # ✅ CORRIGÉ: Basic campaign information - utilise la méthode helper
        dashboard_data['campaign_info'] = {
            'id': campaign.id,
            'name': campaign.name,
            'sequence_type': getattr(campaign, 'sequence_type', None),
            'sequence_type_display': self._get_safe_sequence_type_display(campaign),  # ✅ UTILISE LA MÉTHODE HELPER
            'status': campaign.status,
            'start_date': campaign.start_date.isoformat() if campaign.start_date else None,
            'end_date': campaign.end_date.isoformat() if campaign.end_date else None,
            'has_sequence': getattr(campaign, 'sequence_type', None) is not None,
            'is_call_list': getattr(campaign, 'sequence_type', None) is None
        }
        
        # ✅ SIMPLIFIÉ: METRICS SECTION - utilise le service existant
        if 'metrics' in included_sections or 'basic' in included_sections:
            try:
                # ✅ UTILISER CampaignTrackingService.get_campaign_metrics() 
                dashboard_data['metrics'] = CampaignTrackingService.get_campaign_metrics(campaign)
                
                # Ajouter les compteurs de targets calculés manuellement
                dashboard_data['metrics']['total_targets'] = campaign.targets.count()
                dashboard_data['metrics']['active_targets'] = campaign.targets.filter(status='ACTIVE').count()
                dashboard_data['metrics']['completed_targets'] = campaign.targets.filter(status='COMPLETED').count()
                
            except Exception as e:
                print(f"Warning: Could not get metrics for campaign {campaign.id}: {e}")
                # Fallback ultime avec calculs manuels
                dashboard_data['metrics'] = {
                    'total_targets': campaign.targets.count() if hasattr(campaign, 'targets') else 0,
                    'active_targets': campaign.targets.filter(status='ACTIVE').count() if hasattr(campaign, 'targets') else 0,
                    'completed_targets': campaign.targets.filter(status='COMPLETED').count() if hasattr(campaign, 'targets') else 0,
                    'total_activities': 0,
                    'completed_activities': 0,
                    'pending_activities': 0,
                    'leads_created': 0,
                    'meetings_secured': 0,
                    'opportunities_created': 0,
                    'deals_closed': 0,
                    'pipeline_value': 0.0,
                    'revenue_generated': 0.0,
                    'last_updated': timezone.now().isoformat()
                }
        
        
        # ✅ AUTRES SECTIONS - Simplifiées avec gestion d'erreurs robuste
        if 'objectives' in included_sections:
            try:
                objectives = list(campaign.objectives.all())
                dashboard_data['objectives'] = [
                    {
                        'id': obj.id,
                        'name': obj.name,
                        'progress_percentage': self._safe_get_progress_percentage(obj),
                        'is_primary': getattr(obj, 'is_primary', False)
                    } for obj in objectives
                ]
            except Exception as e:
                print(f"Warning: Could not get objectives for campaign {campaign.id}: {e}")
                dashboard_data['objectives'] = []
        
        if 'targets' in included_sections:
            try:
                if hasattr(campaign, 'get_target_summary') and callable(campaign.get_target_summary):
                    dashboard_data['targets'] = campaign.get_target_summary()
                else:
                    # Fallback simple
                    dashboard_data['targets'] = {'total': campaign.targets.count(), 'by_status': {}}
            except Exception as e:
                print(f"Warning: Could not get targets for campaign {campaign.id}: {e}")
                dashboard_data['targets'] = {'total': 0, 'by_status': {}}
        
        if 'tracking' in included_sections:
            try:
                # ✅ UTILISER le service existant pour les données de tracking
                tracking_metrics = CampaignTrackingService.get_campaign_metrics(campaign)
                dashboard_data['tracking'] = {
                    'activities_completed': tracking_metrics.get('completed_activities', 0),
                    'activities_pending': tracking_metrics.get('pending_activities', 0),
                    'leads_created': tracking_metrics.get('leads_created', 0),
                    'meetings_secured': tracking_metrics.get('meetings_secured', 0),
                    'opportunities_created': tracking_metrics.get('opportunities_created', 0),
                    'deals_closed': tracking_metrics.get('deals_closed', 0),
                    'pipeline_value': tracking_metrics.get('pipeline_value', 0.0),
                    'revenue_generated': tracking_metrics.get('revenue_generated', 0.0),
                    'note': 'Minimal tracking data provided'
                }
            except Exception as e:
                print(f"Warning: Could not get tracking data for campaign {campaign.id}: {e}")
                dashboard_data['tracking'] = {
                    'activities_completed': 0,
                    'activities_pending': 0,
                    'leads_created': 0,
                    'meetings_secured': 0,
                    'opportunities_created': 0,
                    'deals_closed': 0,
                    'pipeline_value': 0.0,
                    'revenue_generated': 0.0,
                    'error': 'Analytics data unavailable - minimal tracking provided'
                }
        
        if 'activities' in included_sections:
            try:
                # ✅ UTILISER les métriques déjà calculées
                metrics = dashboard_data.get('metrics', {})
                dashboard_data['activities'] = {
                    'total_count': metrics.get('total_activities', 0),
                    'completed_count': metrics.get('completed_activities', 0),
                    'pending_count': metrics.get('pending_activities', 0),
                    'recent_activities': []  # Vide pour éviter les erreurs en mode minimal
                }
            except Exception as e:
                print(f"Warning: Could not get activities data for campaign {campaign.id}: {e}")
                dashboard_data['activities'] = {
                    'total_count': 0,
                    'completed_count': 0,
                    'pending_count': 0,
                    'recent_activities': []
                }
        
        return dashboard_data
    
    def _safe_get_progress_percentage(self, obj):
        """
        ✅ CORRIGÉ: Obtient le pourcentage de progression de manière sécurisée
        """
        try:
            # ✅ UTILISER LA MÉTHODE CORRECTE du modèle
            if hasattr(obj, 'get_progress_percentage') and callable(obj.get_progress_percentage):
                return obj.get_progress_percentage()
            
            # Fallback : calculer manuellement si nécessaire
            if hasattr(obj, 'get_current_value') and hasattr(obj, 'target_value'):
                print(f"Warning: Using fallback for progress percentage for {obj.__class__.__name__}")
                current = obj.get_current_value()
                target = float(obj.target_value) if obj.target_value else 0
                if target == 0:
                    return 0
                return min(100, (current / target) * 100)
            
            return 0
        except Exception:
            return 0
    
    def _get_safe_sequence_type_display(self, campaign):
        """
        ✅ NOUVEAU: Méthode helper centralisée pour obtenir l'affichage du type de séquence
        Évite les erreurs de sérialisation JSON et centralise la logique
        
        Args:
            campaign: Instance Campaign
            
        Returns:
            str: Affichage sécurisé du type de séquence
        """
        try:
            # Vérifier si la campagne existe
            if not campaign:
                return 'Unknown Campaign'
                
            # Vérifier si sequence_type existe
            if not hasattr(campaign, 'sequence_type'):
                return 'No Sequence Type'
                
            # Obtenir le sequence_type
            sequence_type = getattr(campaign, 'sequence_type', None)
            
            if sequence_type is None:
                return 'Call List'
            
            # Essayer d'utiliser la méthode du modèle
            if hasattr(campaign, 'get_sequence_type_display') and callable(campaign.get_sequence_type_display):
                return campaign.get_sequence_type_display()
            
            # Fallback : formater manuellement
            if isinstance(sequence_type, str):
                return sequence_type.replace('_', ' ').title()
            
            # Fallback ultime
            return str(sequence_type)
            
        except Exception as e:
            # Log l'erreur en mode debug
            if hasattr(self, 'request') and self.request:
                print(f"Warning: _get_safe_sequence_type_display failed for campaign {getattr(campaign, 'id', 'unknown')}: {e}")
            
            # Retourner une valeur par défaut
            return 'Unknown'
    
    
    def _build_optimized_dashboard_data(self, campaign, included_sections, format_param):
        """
        ✅ CORRIGÉ - Construit dashboard avec données pré-chargées
        Utilise les annotations du CampaignQueryOptimizer pour éviter N+1 queries
        """
        dashboard_data = {}
        
        # Basic campaign information (always included)
        dashboard_data['campaign_info'] = {
            'id': campaign.id,
            'name': campaign.name,
            'sequence_type': campaign.sequence_type,  
            'sequence_type_display': self._get_safe_sequence_type_display(campaign),  # ✅ UTILISE HELPER
            'status': campaign.status,
            'start_date': campaign.start_date.isoformat(),
            'end_date': campaign.end_date.isoformat(),
            'has_sequence': campaign.sequence_type is not None,
            'is_call_list': campaign.sequence_type is None  # ✅ AJOUTÉ: information utile
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
                        'progress_percentage': primary_obj.get_progress_percentage()  # ✅ CORRIGÉ: méthode correcte
                    } if primary_obj else None
                }
            else:
                # Standard optimization - all objectives (already prefetched)
                objectives = list(campaign.objectives.all())
                dashboard_data['objectives'] = [
                    {
                        'id': obj.id,
                        'name': obj.name,
                        'progress_percentage': obj.get_progress_percentage(),  # ✅ CORRIGÉ: méthode correcte
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
        
        # Activities section - ✅ CORRIGÉ: Utilise la bonne relation
        if 'activities' in included_sections:
            if format_param == 'summary':
                dashboard_data['activities'] = {
                    'total_count': getattr(campaign, 'total_activities', 0),
                    'completed_count': getattr(campaign, 'completed_activities', 0),
                    'pending_count': getattr(campaign, 'pending_activities', 0)
                }
            else:
                # ✅ CORRIGÉ: Utiliser la relation correcte via ActivityCampaign
                recent_activities = Activity.objects.filter(
                    campaign_info__campaign=campaign  # ✅ CORRIGÉ: Relation correcte
                ).select_related('campaign_info').order_by('-created_at')[:10]
                
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
                'sequence_type': campaign.sequence_type,
                'sequence_type_display': campaign.get_sequence_type_display(),
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


