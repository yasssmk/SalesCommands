"""
DRF Mixins for Permission System

This module provides Django REST Framework integration:
- ScopedPermission: DRF permission class for access control
- ScopedQuerysetMixin: Automatic queryset filtering by scope

IMPORTANT: Client filtering FIRST, then scope filtering.
"""

from typing import Optional, Set, Dict, Any
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView
from django.db.models import QuerySet, Q
from django.conf import settings

from .checks import check_permission, has_permission
from .config import is_module_enabled, is_enabled
from .compat import get_auth_ctx
from .policies import (
    resolve_action_policy,
    check_action_policy_permission,
    resolve_scope_profile,
    ScopeProfiles
)
from .constants import normalize_action
from .ownership import resolve_field
import logging

# Import robuste de get_correlation_id
try:
    from backend.core.logging.context import get_correlation_id
except ImportError:
    try:
        from core.logging.context import get_correlation_id
    except ImportError:
        def get_correlation_id():
            return '-'

logger = logging.getLogger(__name__)


class ScopedPermission(permissions.BasePermission):
    """
    DRF Permission class that checks permissions using our registry.
    
    Uses role flags (is_admin/is_manager/is_individual) for decisions.
    No tier inference from names.
    
    Requires the view to have a 'module' attribute defining which
    module it belongs to.
    
    Example:
        class AccountViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, ScopedPermission]
            module = 'accounts'
    """
    
   # permissions/mixins.py

class ScopedPermission(permissions.BasePermission):
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        # Common log context (no PII)
        base_extra = {
            'correlation_id': get_correlation_id(),
            'user_id': str(getattr(request.user, 'id', '-')) if getattr(request, 'user', None) else '-',
            'client_id': getattr(request, 'client_id', '-'),
            'method': getattr(request, 'method', '-'),
            'path': getattr(request, 'path', '-'),
            'origin': request.auth.get('origin') if isinstance(getattr(request, 'auth', None), dict) else '-',
            'role_name': getattr(request.user, 'role_name', '-') if getattr(request, 'user', None) else '-',
            'event': 'permission_check',
        }

        # Skip if permissions system is disabled
        if not is_enabled():
            logger.debug("permissions_system_disabled", extra={
                **base_extra,
                'view': view.__class__.__name__,
            })
            return True

        # Get module from view
        module = getattr(view, 'module', None)
        if not module:
            logger.warning("permission_denied_no_module", extra={
                **base_extra,
                'view': view.__class__.__name__,
                'reason_code': 'missing_module',
                'event': 'permission_denied',
            })
            return False

        # Skip if module is not enabled
        if not is_module_enabled(module):
            logger.debug("module_not_enabled", extra={
                **base_extra,
                'biz_module': module,
                'view': view.__class__.__name__,
            })
            return True

        # Resolve action (normalize PATCH -> update)
        raw_action = self._get_action(view)


        logger.debug("permission_check_start", extra={
            **base_extra,
            'biz_module': module,
            'action': raw_action,
        })

        # Custom action policy first
        action_policies = getattr(view, 'action_policies', {})
        if raw_action in action_policies:
            logger.debug("using_action_policy", extra={
                **base_extra,
                'biz_module': module,
                'action': raw_action,
            })
            is_permitted, scope = check_action_policy_permission(
                action_policies, raw_action, request, module
            )

            if is_permitted:
                # Store resolved scope for downstream usage
                request._applied_scope = scope
                logger.debug("permission_granted", extra={
                    **base_extra,
                    'biz_module': module,
                    'action': raw_action,
                    'source': 'action_policy',
                })
            else:
                logger.info("permission_denied", extra={
                    **base_extra,
                    'biz_module': module,
                    'action': raw_action,
                    'reason_code': 'action_policy_denied',
                })
            return is_permitted
        
        # If no custom policy, normalize action for standard registry
        action = normalize_action(raw_action)

        logger.debug("permission_check_start", extra={
            **base_extra,
            'biz_module': module,
            'action': action,  # Action normalisée
        })

        # Standard registry check
        result = has_permission(request, module, raw_action)

        if not result:
            logger.info("permission_denied", extra={
                **base_extra,
                'biz_module': module,
                'action': action,
                'reason_code': 'policy_denied',
            })
        else:
            logger.debug("permission_granted", extra={
                **base_extra,
                'biz_module': module,
                'action': action,
            })

        return result

    
    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        """
        Check object-level permissions.
        
        For now, we rely on queryset filtering for most cases.
        This can be enhanced later for specific object checks.
        
        Args:
            request: DRF request
            view: The view being accessed
            obj: The object being accessed
            
        Returns:
            True if permission granted, False otherwise
        """
        # For now, if they passed has_permission and the object
        # is in the filtered queryset, they can access it
        return True
    
    def _get_action(self, view: APIView) -> str:
        """
        Get the current action being performed.
        
        Args:
            view: The view being accessed
            
        Returns:
            Action name (defaults to CRUD mapping)
        """
        # For ViewSets, use the action attribute (raw, no normalization)
        if hasattr(view, 'action'):
            return view.action  # Returns 'bulk_update', 'list', etc
        
        # For APIView, check request method (raw HTTP method)
        if hasattr(view, 'request'):
            return view.request.method  # Returns 'PATCH', 'GET', etc
        
        # Default fallback
        return 'read'

class ScopedQuerysetMixin:
    """
    Mixin to automatically filter querysets based on permission scopes.
    
    CRITICAL: Client filtering FIRST, then scope filtering.
    
    IMPORTANT: This mixin should be placed FIRST in the inheritance chain
    before BaseAPIView to ensure proper MRO execution.
    
    The mixin applies scope-based filtering AFTER
    BaseAPIView has already applied client-level filtering.
    
    Add this FIRST in your ViewSet inheritance:
    
        class AccountViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
            module = 'accounts'  # Required!
            queryset = Account.objects.all()
    """
    
    # Module name must be set on the view
    module: Optional[str] = None
    
    # Optional action policies
    action_policies: Dict[str, Dict[str, Any]] = {}
    
    def get_queryset(self) -> QuerySet:
        """
        Filter queryset based on user's permission scope.
        
        CRITICAL: Uses OWNERSHIP_MAP for field resolution.
        Supports both old pattern (client_account_id) and new pattern (client_id).
        
        Returns:
            Filtered queryset
        """
        # Get module name
        module = getattr(self, 'module', None)
        
        logger.debug("scoped_queryset_start", extra={
            'correlation_id': get_correlation_id(),
            'view': self.__class__.__name__,
            'action': getattr(self, 'action', 'unknown'),
            'biz_module': module or 'unknown',
            'user_id': str(self.request.user.id) if hasattr(self.request, 'user') and hasattr(self.request.user, 'id') else '-',
            'event': 'queryset_filter'
        })
        
        # CRITICAL: Call super() to get the base queryset
        # This ensures BaseAPIView applies initial filtering first
        queryset = super().get_queryset()
        
        logger.debug("queryset_after_super", extra={
            'correlation_id': get_correlation_id(),
            'event': 'queryset_filter'
        })
        
        # Skip if permissions system is disabled
        if not is_enabled():
            logger.debug("permissions_disabled_in_queryset", extra={
                'correlation_id': get_correlation_id(),
                'event': 'queryset_filter'
            })
            return queryset
        
        # Check module
        if not module:
            logger.warning("no_module_in_queryset", extra={
                'correlation_id': get_correlation_id(),
                'view': self.__class__.__name__,
                'event': 'queryset_filter'
            })
            return queryset.none()
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            logger.debug("module_disabled_in_queryset", extra={
                'correlation_id': get_correlation_id(),
                'biz_module': module,
                'event': 'queryset_filter'
            })
            return queryset
        
        # Get auth context (NO DB)
        ctx = get_auth_ctx(self.request)
        
        logger.debug("auth_context", extra={
            'correlation_id': get_correlation_id(),
            'user_id': ctx.user_id,
            'client_id': ctx.client_id,
            'roles_count': len(ctx.roles),
            'teams_count': len(ctx.teams),
            'event': 'queryset_filter'
        })
        
        # =========================================================================
        # CLIENT FILTERING (TENANT ISOLATION) - Uses OWNERSHIP_MAP
        # =========================================================================
        if ctx.client_id:
            client_field = resolve_field(module, 'client_account_fk')
            
            if client_field:
                # Handle nested fields (e.g., 'organization.client_account_id')
                if '.' in client_field:
                    # Nested field - use Django's __ lookup
                    filter_field = client_field.replace('.', '__')
                else:
                    filter_field = client_field
                
                # Check if field exists on model
                model_fields = {f.name for f in queryset.model._meta.get_fields()}
                base_field = client_field.split('.')[0]
                
                if base_field in model_fields:
                    queryset = queryset.filter(**{filter_field: ctx.client_id})
                    logger.debug("client_filter_applied", extra={
                        'correlation_id': get_correlation_id(),
                        'client_id': ctx.client_id,
                        'field_used': filter_field,
                        'event': 'queryset_filter'
                    })
                else:
                    logger.warning("client_field_not_found", extra={
                        'correlation_id': get_correlation_id(),
                        'biz_module': module,
                        'expected_field': client_field,
                        'available_fields': list(model_fields)[:10],
                        'event': 'queryset_filter'
                    })
            else:
                logger.warning("no_client_field_in_ownership_map", extra={
                    'correlation_id': get_correlation_id(),
                    'biz_module': module,
                    'event': 'queryset_filter'
                })
        
        # =========================================================================
        # USER AUTHENTICATION CHECK
        # =========================================================================
        user = self.request.user if hasattr(self, 'request') else None
        if not user or not user.is_authenticated:
            logger.warning("unauthenticated_queryset", extra={
                'correlation_id': get_correlation_id(),
                'event': 'queryset_filter'
            })
            return queryset.none()
        
        # =========================================================================
        # PERMISSION SCOPE RESOLUTION
        # =========================================================================
        action = getattr(self, 'action', 'list')
        
        # Check for action-specific policy first
        action_policies = getattr(self, 'action_policies', {})
        if action in action_policies:
            policy = action_policies[action]
            scope = policy.get('scope', 'none')
            # Admins always get client scope regardless of action_policies.
            # action_policies defines scope for non-admin users only.
            if scope != 'client':
                has_admin = ctx.is_superuser
                for role in ctx.roles:
                    if isinstance(role, dict) and role.get('is_admin'):
                        has_admin = True
                        break
                if has_admin:
                    scope = 'client'
                    
            logger.debug("using_action_policy_scope", extra={
                'correlation_id': get_correlation_id(),
                'action': action,
                'scope': scope,
                'event': 'queryset_filter'
            })
        else:
            # Use standard permission check
            scope = check_permission(self.request, module, action)
        
        logger.debug("permission_scope_resolved", extra={
            'correlation_id': get_correlation_id(),
            'biz_module': module,
            'action': action,
            'scope': scope,
            'event': 'queryset_filter'
        })
        
        # Handle 'none' scope - no access
        if scope is None or scope == 'none':
            logger.info("no_permission_empty_queryset", extra={
                'correlation_id': get_correlation_id(),
                'biz_module': module,
                'action': action,
                'user_id': str(self.request.user.id) if hasattr(self.request, 'user') and hasattr(self.request.user, 'id') else '-',
                'event': 'permission_denied'
            })
            return queryset.none()
        
        logger.debug("permission_check_returned_scope", extra={
            'correlation_id': get_correlation_id(),
            'scope': scope,
            'event': 'queryset_filter'
        })
        
        # =========================================================================
        # SCOPE FILTERING - Uses OWNERSHIP_MAP
        # =========================================================================
        
        if scope == 'client':
            # Client scope - already filtered by client above
            logger.debug("scope_client", extra={
                'correlation_id': get_correlation_id(),
                'scope': 'client',
                'event': 'queryset_filter'
            })
            
        elif scope == 'team':
            # Team scope - filter by team ownership + user ownership
            # For managers: includes items from all team members they manage
            
            # Get managed teams (teams where user is manager) + sub-teams
            from permissions.owner_scope import get_all_descendant_team_ids, get_team_member_ids
            
            managed_team_ids = set()
            user = self.request.user
            
            # Get teams where user is manager
            if hasattr(user, 'id') and ctx.client_id:
                from end_users.models import Team
                manager_teams = Team.objects.filter(
                    client_account_id=ctx.client_id,
                    manager_id=user.id
                ).values_list('id', flat=True)
                managed_team_ids = set(str(tid) for tid in manager_teams)
            
            # Include user's own team
            if ctx.team_id:
                managed_team_ids.add(str(ctx.team_id))
            
            # Get all descendant teams (sub-teams)
            all_team_ids = get_all_descendant_team_ids(managed_team_ids, ctx.client_id) if managed_team_ids else set()
            
            # Get all members of those teams
            team_member_ids = get_team_member_ids(all_team_ids, ctx.client_id) if all_team_ids else set()
            team_member_ids.add(ctx.user_id)  # Always include self
            
            logger.debug("scope_team", extra={
                'correlation_id': get_correlation_id(),
                'scope': 'team',
                'managed_teams': list(managed_team_ids),
                'all_teams': list(all_team_ids),
                'team_members_count': len(team_member_ids),
                'event': 'queryset_filter'
            })
            
            q_filter = Q()
            model_fields = {f.name for f in queryset.model._meta.get_fields()}
            
            # Helper to check if field is valid (direct or traversed)
            def is_valid_field(field_name):
                if not field_name:
                    return False
                # Traversed fields (with __) are always valid for Q filters
                if '__' in field_name:
                    return True
                # Direct fields must exist in model
                return field_name in model_fields
            
            # Check owner_team from OWNERSHIP_MAP
            team_field = resolve_field(module, 'owner_team')
            if team_field and is_valid_field(team_field) and all_team_ids:
                q_filter |= Q(**{f'{team_field}__in': all_team_ids})
                logger.debug("added_owner_team_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'field': team_field,
                    'teams_count': len(all_team_ids),
                    'event': 'queryset_filter'
                })
            
            # Also filter by owner_user IN team_member_ids (for traversed team fields)
            owner_field = resolve_field(module, 'owner_user')
            if owner_field and is_valid_field(owner_field) and team_member_ids:
                q_filter |= Q(**{f'{owner_field}__in': team_member_ids})
                logger.debug("added_owner_user_filter_team", extra={
                    'correlation_id': get_correlation_id(),
                    'field': owner_field,
                    'members_count': len(team_member_ids),
                    'event': 'queryset_filter'
                })
            
            # Also include created_by
            created_field = resolve_field(module, 'created_by')
            if created_field and is_valid_field(created_field):
                q_filter |= Q(**{f'{created_field}__in': team_member_ids})
                logger.debug("added_created_by_filter_team", extra={
                    'correlation_id': get_correlation_id(),
                    'field': created_field,
                    'event': 'queryset_filter'
                })
            
            # Also include assigned_to_user
            assigned_field = resolve_field(module, 'assigned_to_user')
            if assigned_field and is_valid_field(assigned_field):
                q_filter |= Q(**{f'{assigned_field}__in': team_member_ids})
                logger.debug("added_assigned_to_filter_team", extra={
                    'correlation_id': get_correlation_id(),
                    'field': assigned_field,
                    'event': 'queryset_filter'
                })
            
            if q_filter:
                queryset = queryset.filter(q_filter)
                logger.debug("applied_team_scope_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'event': 'queryset_filter'
                })
            else:
                logger.debug("no_team_ownership_fields", extra={
                    'correlation_id': get_correlation_id(),
                    'biz_module': module,
                    'event': 'queryset_filter'
                })
                
        elif scope == 'mine':
            # Mine scope - filter by user ownership only
            logger.debug("scope_mine", extra={
                'correlation_id': get_correlation_id(),
                'scope': 'mine',
                'user_id': ctx.user_id,
                'event': 'queryset_filter'
            })
            
            q_filter = Q()
            model_fields = {f.name for f in queryset.model._meta.get_fields()}

            def is_valid_mine_field(field_name):
                if not field_name:
                    return False
                # Traversal fields (with __) are always valid for Q filters
                if '__' in field_name:
                    return True
                return field_name in model_fields
            
            # Check owner_user from OWNERSHIP_MAP
            owner_field = resolve_field(module, 'owner_user')
            if owner_field and is_valid_mine_field(owner_field):
                q_filter |= Q(**{owner_field: ctx.user_id})
                logger.debug("added_owner_user_filter_mine", extra={
                    'correlation_id': get_correlation_id(),
                    'field': owner_field,
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            # Check created_by from OWNERSHIP_MAP
            created_field = resolve_field(module, 'created_by')
            if created_field and is_valid_mine_field(created_field):
                q_filter |= Q(**{created_field: ctx.user_id})
                logger.debug("added_created_by_filter_mine", extra={
                    'correlation_id': get_correlation_id(),
                    'field': created_field,
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            # Check assigned_to_user from OWNERSHIP_MAP
            assigned_field = resolve_field(module, 'assigned_to_user')
            if assigned_field and is_valid_mine_field(assigned_field):
                q_filter |= Q(**{assigned_field: ctx.user_id})
                logger.debug("added_assigned_to_filter_mine", extra={
                    'correlation_id': get_correlation_id(),
                    'field': assigned_field,
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })

            # Check account_owner_user from OWNERSHIP_MAP
            # Account-owner inheritance: for child entities (activities,
            # decision cycles), the owner of the parent account can act on
            # records created by anyone else on that account. The mapped
            # value is a traversal (account__account_owner_id), accepted by
            # is_valid_mine_field.
            account_owner_field = resolve_field(module, 'account_owner_user')
            if account_owner_field and is_valid_mine_field(account_owner_field):
                q_filter |= Q(**{account_owner_field: ctx.user_id})
                logger.debug("added_account_owner_filter_mine", extra={
                    'correlation_id': get_correlation_id(),
                    'field': account_owner_field,
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })

            if q_filter:
                queryset = queryset.filter(q_filter)
                logger.debug("applied_mine_scope_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'event': 'queryset_filter'
                })
            else:
                # No ownership fields configured = no access for mine scope
                logger.warning("no_mine_ownership_fields_deny", extra={
                    'correlation_id': get_correlation_id(),
                    'biz_module': module,
                    'event': 'queryset_filter'
                })
                return queryset.none()
        
        # =========================================================================
        # FINAL QUERYSET
        # =========================================================================
        logger.debug("queryset_final", extra={
            'correlation_id': get_correlation_id(),
            'biz_module': module,
            'action': action,
            'scope': scope,
            'event': 'queryset_filter'
        })
        
        return queryset

    def get_object(self):
        """
        Get single object with explicit 403 for permission denials.
        
        This override distinguishes between:
        - Object not found (404): Resource doesn't exist in tenant
        - Permission denied (403): Resource exists but user lacks permission
        
        The default DRF behavior only returns 404 when object is not in
        the scoped queryset, which is misleading for users without permission.
        
        Returns:
            Model instance if found and authorized
            
        Raises:
            Http404: If object doesn't exist in the tenant
            StandardizedPermissionDenied: If object exists but user lacks permission
        """
        from django.http import Http404
        from core.exceptions import StandardizedPermissionDenied
        from core.error_messages import CoreErrorMessages
        
        # Get the object ID from URL kwargs
        pk = self.kwargs.get('pk')
        if not pk:
            raise Http404("No object ID provided")
        
        # Get the model class
        model = self.queryset.model
        
        # Get client_id for tenant isolation
        client_id = self.get_client_id() if hasattr(self, 'get_client_id') else None
        
        # STEP 1: Check if object exists in tenant (without scope filter)
        try:
            if client_id:
                # Verify object exists in this tenant
                # Support both client_account_id (legacy) and client_id (new UUID models)
                def has_db_field(model, field_name):
                    try:
                        model._meta.get_field(field_name)
                        return True
                    except Exception:
                        return False
                
                if has_db_field(model, 'client_account_id') or has_db_field(model, 'client_account'):
                    obj = model.objects.get(pk=pk, client_account_id=client_id)
                elif has_db_field(model, 'client_id'):
                    obj = model.objects.get(pk=pk, client_id=client_id)
                else:
                    obj = model.objects.get(pk=pk)
        except model.DoesNotExist:
            # Object truly doesn't exist in tenant → 404
            raise Http404(f"No {model.__name__} matches the given query.")
        
        # STEP 2: Check if object is in scoped queryset (permission check)
        scoped_qs = self.get_queryset()
        
        if not scoped_qs.filter(pk=pk).exists():
            # Object exists in tenant but not in user's scope → 403
            raise StandardizedPermissionDenied(
                CoreErrorMessages.PERMISSION_DENIED
            )
        
        # STEP 3: Object exists and user has permission → return it
        return obj
    
    def get_objects_for_bulk(self, ids: list) -> dict:
        """
        Get multiple objects with explicit 403 for permission denials.
        
        This is the bulk equivalent of get_object().
        Same pattern: existence check THEN permission check.
        
        Distinguishes between:
        - Object not found (404): Resource doesn't exist in tenant
        - Permission denied (403): Resource exists but user lacks permission
        
        Args:
            ids: List of primary keys (UUIDs or strings)
            
        Returns:
            dict with keys:
                - 'objects': dict mapping id -> object (only accessible ones)
                - 'not_found_ids': set of IDs that don't exist in tenant
                
        Raises:
            StandardizedPermissionDenied: If ANY object exists but is out of scope
            
        Usage in bulk operations:
            result = self.get_objects_for_bulk(ids)
            objects_dict = result['objects']
            not_found_ids = result['not_found_ids']
        """
        from core.exceptions import StandardizedPermissionDenied
        from core.error_messages import CoreErrorMessages
        
        requested_ids = set(str(i) for i in ids)
        
        # =========================================================================
        # STEP 1: Check existence in tenant (without permission filtering)
        # =========================================================================
        
        # Get the base queryset with only client filtering (no scope filtering)
        # We need to bypass get_queryset() which applies scope filtering
        base_qs = super().get_queryset()
        
        # Filter by requested IDs
        tenant_qs = base_qs.filter(pk__in=ids)
        tenant_dict = {str(obj.pk): obj for obj in tenant_qs}
        existing_ids = set(tenant_dict.keys())
        
        # IDs that don't exist at all in tenant
        not_found_ids = requested_ids - existing_ids
        
        # =========================================================================
        # STEP 2: Check permission scope (same as get_object)
        # =========================================================================
        
        if existing_ids:
            # Get scoped queryset (applies permission filtering)
            scoped_qs = self.get_queryset().filter(pk__in=existing_ids)
            scoped_dict = {str(obj.pk): obj for obj in scoped_qs}
            scoped_ids = set(scoped_dict.keys())
            
            # IDs that exist but are out of user's permission scope
            out_of_scope_ids = existing_ids - scoped_ids
            
            if out_of_scope_ids:
                # 403 - Same behavior as get_object()
                logger.warning("bulk_permission_denied", extra={
                    'correlation_id': get_correlation_id(),
                    'out_of_scope_count': len(out_of_scope_ids),
                    'event': 'permission_denied'
                })
                raise StandardizedPermissionDenied(CoreErrorMessages.PERMISSION_DENIED)
            
            return {
                'objects': scoped_dict,
                'not_found_ids': not_found_ids
            }
        
        # No existing IDs found
        return {
            'objects': {},
            'not_found_ids': not_found_ids
        }
        
    def _get_action(self) -> str:
        """
        Get the current action being performed.
        
        Returns:
            Action name (defaults to CRUD mapping)
            
        Notes:
            REFACTORED: Now uses centralized normalize_action() from constants.py
            Previously had 14 lines of duplicated mapping logic
        """
        # For ViewSets, use the action attribute (raw, no normalization)
        if hasattr(self, 'action'):
            return self.action  # Returns 'bulk_update', 'list', etc
        
        # For APIView, check request method (raw HTTP method)
        if hasattr(self, 'request'):
            return self.request.method  # Returns 'PATCH', 'GET', etc
        
        # Default to read
        return 'read'