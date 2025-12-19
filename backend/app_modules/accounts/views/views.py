# app_modules/accounts/views/views.py
"""
ViewSet for CompanyAccount (Administration module).

Follows UserViewSet patterns with AccountAPIView business logic.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from ..filters import CompanyAccountFilter
from django.db import transaction
from django.http import Http404
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.cache_utils import (
    build_drf_cache_key, 
    cache_get_set, 
    get_permissions_version, 
    invalidate_tag,
    _is_redis_backend
)
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ...core_modules.models import StandardDepartment

from ..models import CompanyAccount, AccountType, AccountClassification
from ..serializers import (
    CompanyAccountSerializer,
    CompanyAccountListSerializer,
    CompanyAccountCreateSerializer,
    CompanyAccountUpdateSerializer,
    WorkspaceStatsSerializer,
    AccountWorkspaceSerializer,
)
from ..services.filter_service import AccountFilterService

logger = get_logger(__name__)



# ========== IMPORT FOR ERROR TESTING =========

from rest_framework.exceptions import (
    ValidationError,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    NotFound,
    MethodNotAllowed,
    Throttled,
    APIException
)

# 500 - Internal Server Error
class InternalServerError(APIException):
    status_code = 500
    default_detail = "Internal server error."
    default_code = "server_error"

# 502 - Bad Gateway
class BadGateway(APIException):
    status_code = 502
    default_detail = "Bad gateway."
    default_code = "bad_gateway"

# 503 - Service Unavailable
class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Service temporarily unavailable."
    default_code = "service_unavailable"

# 504 - Gateway Timeout
class GatewayTimeout(APIException):
    status_code = 504
    default_detail = "Gateway timeout."
    default_code = "gateway_timeout"
# =============================================


class CompanyAccountViewSet(OwnerScopeMixin,ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing company accounts with client scoping.
    
    Follows UserViewSet patterns for consistency.
    """
    
    queryset = CompanyAccount.objects.all()
    serializer_class = CompanyAccountSerializer
    entity_name = 'company_account'
    
    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CompanyAccountFilter
    search_fields = ['company_name', 'industry', 'city', 'country', 'account_owner']
    ordering_fields = [
        'company_name',
        'industry',
        'type',
        'classification',
        'country',
        'account_owner',
        'created_at',
        'updated_at',
    ]
    ordering = ['-created_at']
    
    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'accounts'
    
    # Allowed fields for mass update
    mass_update_allowed_fields = {'type', 'classification', 'account_owner_id'}
    
    # Action policies
    action_policies = {
        'workspace': {
            'crud': 'read',
            'scope': 'client'
        },
        'qualification': {
            'crud': 'read',
            'scope': 'client'
        },
        'tech_stacks': {
            'crud': 'read',
            'scope': 'client'
        },
        'hierarchy': {
            'crud': 'read',
            'scope': 'client'
        },
        'bulk_create': {
            'crud': 'create',
            'tier': 'admin',
            'scope': 'client'
        },
        'bulk_update': {
            'crud': 'update',
            'tier': 'admin',
            'scope': 'client'
        },
        'bulk_delete': {
            'crud': 'delete',
            'tier': 'admin',
            'scope': 'client'
        },
    }
    
    def get_serializer_class(self):
        """Choose serializer based on action."""
        if self.action == 'list':
            return CompanyAccountListSerializer
        elif self.action == 'create':
            return CompanyAccountCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CompanyAccountUpdateSerializer
        return CompanyAccountSerializer
    
    def get_queryset(self):
        """Get accounts with optimized queries and filtering."""
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'CompanyAccountViewSet'
        })
        
        queryset = super().get_queryset()
        
        # Optimize based on action
        if self.action == 'list':
            queryset = queryset.select_related(
                'account_owner',
                'account_owner__team',
                'parent_company'
            )
        elif self.action == 'retrieve':
            queryset = queryset.select_related(
                'account_owner',
                'account_owner__team',
                'parent_company'
            ).prefetch_related(
                'direct_child_companies',
                'partners'
            )
        else:
            queryset = queryset.select_related(
                'account_owner',
                'account_owner__team',
                'parent_company'
            )
        
        # Apply owner scope filter (mine/team/all)
        queryset = self.apply_owner_scope_filter(queryset)

        # Advanced filtering from query params
        queryset = self._apply_advanced_filters(queryset)
        
        return queryset
    
    def _apply_advanced_filters(self, queryset):
        """Apply advanced filtering from query params."""
        from app_modules.territories.models import Territory
        from uuid import UUID

        
        try:
            # =================================================================
            # TERRITORY FILTER (applies filter_definition from territory)
            # =================================================================
            territory_id = self.request.query_params.get('territory_id')
            if territory_id:
                # Validate UUID format
                try:
                    UUID(territory_id)
                except (ValueError, TypeError):
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field='territory_id (invalid UUID format)')
                    )
                
                # Apply territory filters
                try:
                    client_id = self.get_client_id()
                    queryset = AccountFilterService.apply_territory_filters(
                        queryset,
                        territory_id,
                        client_id,
                        user=self.request.user
                    )
                    logger.debug("territory_filter_applied", extra={
                        'territory_id': territory_id,
                        'client_id': str(client_id)
                    })
                except Territory.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.NOT_FOUND.format(resource=f'Territory with ID {territory_id}')
                    )
                except Exception as e:
                    logger.error("territory_filter_unexpected_error", extra={
                        'territory_id': territory_id,
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FILTER
                    )
            
            # =================================================================
            # DIRECT QUERY PARAM FILTERS (existing logic)
            # =================================================================
            
            # Filter by parent IDs
            parent_ids = self.request.query_params.get('parent_ids')
            if parent_ids:
                parent_list = [v.strip() for v in parent_ids.split(',')]
                queryset = queryset.filter(parent_company_id__in=parent_list)
            
            # Filter by types
            types = self.request.query_params.get('types')
            if types:
                type_list = [v.strip() for v in types.split(',')]
                queryset = queryset.filter(type__in=type_list)
            
            # Filter by classifications
            classifications = self.request.query_params.get('classifications')
            if classifications:
                classification_list = [v.strip() for v in classifications.split(',')]
                queryset = queryset.filter(classification__in=classification_list)
            
            # Filter by company_size
            company_size = self.request.query_params.get('company_size')
            if company_size:
                queryset = queryset.filter(company_size=company_size)
            
            # Filter by annual_revenue
            annual_revenue = self.request.query_params.get('annual_revenue')
            if annual_revenue:
                queryset = queryset.filter(annual_revenue=annual_revenue)
            
            # Filter by has_buying_decision
            has_buying_decision = self.request.query_params.get('has_buying_decision')
            if has_buying_decision is not None:
                if has_buying_decision.lower() in ['true', '1']:
                    queryset = queryset.filter(has_buying_decision=True)
                elif has_buying_decision.lower() in ['false', '0']:
                    queryset = queryset.filter(has_buying_decision=False)
            
            # =================================================================
            # FK FILTERS (Phase 2 - direct query params)
            # =================================================================
            
            # Tech stack filter (comma-separated tech names)
            has_tech_stack = self.request.query_params.get('has_tech_stack')
            if has_tech_stack:
                tech_names = [t.strip() for t in has_tech_stack.split(',')]
                queryset = AccountFilterService._filter_by_tech_stack(
                    queryset, tech_names, self.get_client_id()
                )
            
            # Buying process stage filter
            buying_process_stage = self.request.query_params.get('buying_process_stage')
            if buying_process_stage:
                stages = [s.strip() for s in buying_process_stage.split(',')]
                queryset = AccountFilterService._filter_by_buying_process(
                    queryset, stages, self.get_client_id()
                )
            
            # Has qualification filter
            has_qualification = self.request.query_params.get('has_qualification')
            if has_qualification is not None:
                has_qual_bool = has_qualification.lower() in ['true', '1']
                queryset = AccountFilterService._filter_by_qualification(
                    queryset, has_qual_bool, self.get_client_id()
                )
            
            # Signals freshness filter
            signals_since_days = self.request.query_params.get('signals_since_days')
            if signals_since_days and signals_since_days.isdigit():
                queryset = AccountFilterService._filter_by_signals_freshness(
                    queryset, int(signals_since_days), self.get_client_id()
                )
                    
        except ValueError:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FILTER)
        
        return queryset
    
    def get_serializer_context(self):
        """Add filter parameters to serializer context."""
        context = super().get_serializer_context()
        
        # Department filter
        department_id = self.request.query_params.get('department_id')
        if department_id:
            try:
                department = StandardDepartment.objects.get(id=department_id)
                context['department'] = department
            except StandardDepartment.DoesNotExist:
                pass
        
        # Source contact filter
        source_contact_id = self.request.query_params.get('source_contact_id')
        if source_contact_id:
            from apps.accounts.models import Contact
            try:
                contact = Contact.objects.get(id=source_contact_id)
                context['source_contact'] = contact
            except Contact.DoesNotExist:
                pass
        
        # Min confirmations filter
        min_confirmations = self.request.query_params.get('min_confirmations')
        if min_confirmations and min_confirmations.isdigit():
            context['min_confirmations'] = int(min_confirmations)
        
        context['many'] = self.action == 'list'
        
        return context
    
    # ==========================================================================
    # CACHE HELPERS
    # ==========================================================================
    
    def _invalidate_account_caches(self, client_id):
        """Invalidate all account-related caches."""
        invalidate_tag(client_id, 'accounts')
        invalidate_tag(client_id, 'contacts')
    
    # ==========================================================================
    # LIST / RETRIEVE
    # ==========================================================================
    
    def list(self, request, *args, **kwargs):
        """
        List company accounts with caching.
        GET /client/accounts/
        """
        if not _is_redis_backend():
            response = super().list(request, *args, **kwargs)
            return Response({
                'success': True,
                'data': response.data
            })
        
        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()
        query_string = request.META.get('QUERY_STRING', '')

        
        cache_key = build_drf_cache_key(
            namespace='accounts_list',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            query_string=query_string,
            tag_namespace='accounts',
        )
        
        def producer():
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return {
                    'success': True,
                    'data': {
                        'results': serializer.data,
                        'count': self.paginator.page.paginator.count,
                        'next': self.paginator.get_next_link(),
                        'previous': self.paginator.get_previous_link(),
                    }
                }
            
            serializer = self.get_serializer(queryset, many=True)
            return {
                'success': True,
                'data': serializer.data
            }
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, 'accounts')
        )
        
        ctx = ctx_from_request(request)
        ctx.update({
            "event": "account_list",
            "result_count": cached_data.get('data', {}).get('count', '-') if isinstance(cached_data.get('data'), dict) else '-',
        })
        logger.info("account_list", extra=ctx)
        
        return Response(cached_data)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a company account.
        GET /client/accounts/{id}/
        """
        pk = kwargs.get('pk')
        
        if not _is_redis_backend():
            try:
                account = self.get_object()
                serializer = CompanyAccountSerializer(account, context=self.get_serializer_context())
                return Response({"success": True, "data": serializer.data})
            except (CompanyAccount.DoesNotExist, Http404):
                return Response(
                    {"success": False, "error": CoreErrorMessages.OBJECT_NOT_FOUND},
                    status=status.HTTP_404_NOT_FOUND,
                )
        
        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()
        
        cache_key = build_drf_cache_key(
            namespace='account_detail',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            extra=str(pk),
            tag_namespace='accounts',
        )
        
        def producer():
            try:
                account = self.get_object()
                
                ctx = ctx_from_request(request)
                ctx.update({
                    "target_account_id": str(account.id),
                    "event": "account_retrieve",
                })
                logger.info("account_retrieve", extra=ctx)
                
                serializer = CompanyAccountSerializer(account, context=self.get_serializer_context())
                return {"success": True, "data": serializer.data}
                
            except (CompanyAccount.DoesNotExist, Http404):
                return {"success": False, "error": CoreErrorMessages.OBJECT_NOT_FOUND, "status": 404}
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, 'accounts')
        )
        
        if not cached_data.get('success'):
            return Response(
                {"success": False, "error": cached_data.get('error')},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(cached_data)
    
    # ==========================================================================
    # CREATE / UPDATE / DELETE
    # ==========================================================================
    
    def create(self, request, *args, **kwargs):
        """
        Create a new company account.
        POST /client/accounts/
        
        For 'mine' scope: Auto-assigns account_owner to current user
        to ensure creator can see the account after creation.
        """
        from permissions import check_permission
        
        with transaction.atomic():
            # Get mutable copy of request data
            data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
            
            # Check user's permission scope for create
            scope = check_permission(request, self.module, 'create')
            
            # For 'mine' scope: force ownership to current user if not specified
            if scope == 'mine':
                if not data.get('account_owner_id'):
                    data['account_owner_id'] = str(request.user.id)
                    logger.debug("auto_assign_owner_mine_scope", extra={
                        'user_id': str(request.user.id),
                        'scope': scope,
                        'event': 'account_create'
                    })
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            account = serializer.save()
            
            # Invalidate caches
            self._invalidate_account_caches(str(account.client_id))
            
            audit_log(
                event='account_create_success',
                action='create',
                actor_id=str(request.user.id),
                client_id=str(account.client_id),
                target_type='company_account',
                target_id=str(account.id),
                outcome='success',
                extra={'scope': scope, 'auto_owner': scope == 'mine'}
            )
            
            return Response(
                {
                    "success": True,
                    "message": f'Account "{account.company_name}" created successfully',
                    "data": CompanyAccountSerializer(account, context=self.get_serializer_context()).data,
                },
                status=status.HTTP_201_CREATED,
            )

    
    def partial_update(self, request, *args, **kwargs):
        """
        Partial update of a company account (PATCH).
        PATCH /client/accounts/{id}/
        """
        try:
            with transaction.atomic():
                account = self.get_object()
                serializer = self.get_serializer(account, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                updated_account = serializer.save()
                
                # Invalidate caches
                self._invalidate_account_caches(str(updated_account.client_id))
                
                changed_fields = sorted([k for k in serializer.validated_data.keys()])
                
                audit_log(
                    event='account_update_success',
                    action='partial_update',
                    actor_id=str(request.user.id),
                    client_id=str(updated_account.client_id),
                    target_type='company_account',
                    target_id=str(account.id),
                    fields_changed=changed_fields,
                    outcome='success',
                )
                
                return Response({
                    "success": True,
                    "message": f'Account "{updated_account.company_name}" updated successfully',
                    "data": CompanyAccountSerializer(updated_account, context=self.get_serializer_context()).data,
                })
                
        except (CompanyAccount.DoesNotExist, Http404):
            return Response(
                {"success": False, "error": CoreErrorMessages.OBJECT_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return self.handle_exception(e)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a single account.
        DELETE /client/accounts/{id}/
        
        Child accounts become orphans (parent_company set to NULL by Django).
        """
        try:
            with transaction.atomic():
                client_id = self.get_client_id()
                account_id = kwargs.get('pk')
                
                account = CompanyAccount.objects.select_for_update().filter(
                    id=account_id,
                    client_id=client_id
                ).first()
                
                if not account:
                    audit_log(
                        event='account_delete_not_found',
                        action='delete',
                        actor_id=str(request.user.id),
                        client_id=str(client_id),
                        target_type='company_account',
                        target_id=str(account_id or '-'),
                        outcome='not_found',
                    )
                    
                    return Response({
                        'success': False,
                        'error': CoreErrorMessages.OBJECT_NOT_FOUND
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # Validate client scoping
                self.validate_client_id(account)
                
                # Count children for audit (will become orphans)
                orphaned_count = account.direct_child_companies.count()
                
                account_name = account.company_name
                account.delete()
                
                # Invalidate caches
                self._invalidate_account_caches(str(client_id))
                
                audit_log(
                    event='account_delete_success',
                    action='delete',
                    actor_id=str(request.user.id),
                    client_id=str(client_id),
                    target_type='company_account',
                    target_id=str(account_id),
                    outcome='success',
                    extra={'orphaned_children': orphaned_count}
                )
                
                return Response({
                    'success': True,
                    'message': f'Account "{account_name}" deleted successfully'
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return self.handle_exception(e)
    
    # ==========================================================================
    # CUSTOM ACTIONS
    # ==========================================================================
    
    @action(detail=True, methods=['get'])
    def workspace(self, request, pk=None):
        """
        Get account workspace data for header display.
        
        Returns account details and basic stats.
        
        GET /company-accounts/{uuid}/workspace/
        """
        try:
            account = self.get_object()
            
            # Serialize account data
            account_data = AccountWorkspaceSerializer(account).data
            
            # Stats placeholder (will connect to legacy later)
            stats_data = {
                'contacts_count': 0,
                'activities_count': 0,
                'opportunities_count': 0,
                'signals_count': 0,
            }
            
            return Response({
                'success': True,
                'data': {
                    'account': account_data,
                    'stats': stats_data,
                }
            })
            
        except Exception as e:
            return self.handle_exception(e)
        
    @action(detail=True, methods=['get'])
    def qualification(self, request, pk=None):
        """
        Get qualification data for an account with filtering options.
        GET /client/accounts/{id}/qualification/
        """
        try:
            account = self.get_object()
            
            # Parse filter parameters
            filters = {}
            
            department_id = request.query_params.get('department_id')
            if department_id:
                try:
                    department = StandardDepartment.objects.get(id=department_id)
                    filters['department'] = department
                except StandardDepartment.DoesNotExist:
                    pass
            
            field_name = request.query_params.get('field_name')
            if field_name:
                if ',' in field_name:
                    filters['field_names'] = [name.strip() for name in field_name.split(',')]
                else:
                    filters['field_names'] = [field_name]
            
            min_confirmations = request.query_params.get('min_confirmations')
            if min_confirmations and min_confirmations.isdigit():
                filters['min_confirmations'] = int(min_confirmations)
            
            source_contact_id = request.query_params.get('source_contact_id')
            if source_contact_id:
                from apps.accounts.models import Contact
                try:
                    contact = Contact.objects.get(id=source_contact_id)
                    filters['source_contact'] = contact
                except Contact.DoesNotExist:
                    pass
            
            qualification_data = account.get_qualification_data(**filters)
            
            return Response({
                'success': True,
                'data': qualification_data
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['get'])
    def tech_stacks(self, request, pk=None):
        """
        Get tech stack data for an account with filtering options.
        GET /client/accounts/{id}/tech_stacks/
        """
        try:
            account = self.get_object()
            
            # Parse filter parameters
            filters = {}
            
            department_id = request.query_params.get('department_id')
            if department_id:
                try:
                    department = StandardDepartment.objects.get(id=department_id)
                    filters['department'] = department
                except StandardDepartment.DoesNotExist:
                    pass
            
            min_confirmations = request.query_params.get('min_confirmations')
            if min_confirmations and min_confirmations.isdigit():
                filters['min_confirmations'] = int(min_confirmations)
            
            source_contact_id = request.query_params.get('source_contact_id')
            if source_contact_id:
                from apps.accounts.models import Contact
                try:
                    contact = Contact.objects.get(id=source_contact_id)
                    filters['source_contact'] = contact
                except Contact.DoesNotExist:
                    pass
            
            tech_stacks_data = account.get_tech_stacks_data(**filters)
            
            return Response({
                'success': True,
                'data': tech_stacks_data
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['get'])
    def hierarchy(self, request, pk=None):
        """
        Get the full hierarchy (parents and children) of an account.
        GET /client/accounts/{id}/hierarchy/
        """
        try:
            account = self.get_object()
            hierarchy = account.get_full_hierarchy()
            
            # Serialize parents and children
            parents_data = [
                {
                    'id': str(parent.id),
                    'company_name': parent.company_name,
                    'type': parent.type,
                    'classification': parent.classification,
                }
                for parent in hierarchy['parents']
            ]
            
            children_data = [
                {
                    'id': str(child.id),
                    'company_name': child.company_name,
                    'type': child.type,
                    'classification': child.classification,
                }
                for child in hierarchy['children']
            ]
            
            return Response({
                'success': True,
                'data': {
                    'account': {
                        'id': str(account.id),
                        'company_name': account.company_name,
                    },
                    'parents': parents_data,
                    'children': children_data,
                }
            })
            
        except Exception as e:
            return self.handle_exception(e)


class CompanyAccountChoicesView(BaseAPIView):
    """
    API endpoint for retrieving account type and classification choices.
    No client scoping needed as these are global choices.
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return Response({
            'success': True,
            'data': {
                'types': CompanyAccount.get_account_types(),
                'classifications': CompanyAccount.get_account_classifications(),
                'industries': CompanyAccount.get_industries(),
                'countries': CompanyAccount.get_countries()
            }
        })