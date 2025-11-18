# backend/end_users/views/team_view.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Prefetch, F
from django.db import transaction
from django.utils import timezone
from django.http import Http404

from core.cache_utils import (
    build_drf_cache_key,
    cache_get_set,
    get_permissions_version,
    invalidate_tag,
    _is_redis_backend,
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

from ..models import Team, User
from ..serializers.team_serializers import (
    TeamSerializer,
    TeamListSerializer,
    TeamCreateSerializer,
    TeamUpdateSerializer,
)

logger = get_logger(__name__)


class TeamViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing teams.
    
    Features:
        - Client-scoped data isolation (multi-tenant)
        - Permission-based access control
        - Caching with Redis tag versioning
        - Structured logging + SOC 2 audit trail
        - Query optimization with annotations
        - Hierarchical team structure support
    
    Endpoints:
        - GET    /teams/           - List all teams
        - POST   /teams/           - Create team
        - GET    /teams/{id}/      - Retrieve team
        - PUT    /teams/{id}/      - Update team (full)
        - PATCH  /teams/{id}/      - Update team (partial)
        - DELETE /teams/{id}/      - Delete team
    
    Custom actions:
        - GET    /teams/{id}/members/     - Team members
        - GET    /teams/summary/          - Teams summary statistics
        - POST   /teams/{id}/duplicate/   - Duplicate team
    
    Permissions:
        - Read: authenticated users (scoped to client/team/mine)
        - Write/Update/Delete: according to permission registry
    """
    
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    entity_name = 'team'
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'teams'
    
    action_policies = {
        'members': {
            'crud': 'read',
            'scope': 'client',
        },
        'summary': {
            'crud': 'read',
            'scope': 'client',
        },
        'duplicate': {
            'crud': 'create',
            'tier': 'admin',
            'scope': 'client',
        },
    }
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['manager', 'parent_team']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at', 'members_count']
    ordering = ['name']
    
    def _invalidate_all_related_caches(self, client_id):
        """
        Invalidate all caches related to teams.
        
        When a team changes, we must invalidate:
        - Team cache (list, details)
        - User cache (users cache their team)
        
        Args:
            client_id: Client UUID
        """
        if not client_id:
            return
        
        invalidate_tag(client_id, 'teams')
        invalidate_tag(client_id, 'users')
        
        logger.info('cache_invalidation_team_users', extra={
            'event': 'cache_invalidation',
            'client_id': str(client_id),
            'tags': ['teams', 'users']
        })
    
    def _serialize_list_queryset(self, queryset, client_id):
        """
        Serialize the queryset with metadata for list responses (cache friendly).
        
        Returns:
            dict: {
                'success': True,
                'data': {
                    'results': [...],
                    'count': int,
                    'next': str|null,
                    'previous': str|null
                },
                'metadata': {
                    'client_id': str,
                    'generated_at': str
                }
            }
        """
        timestamp = timezone.now().isoformat()
        metadata = {
            'client_id': str(client_id) if client_id else None,
            'generated_at': timestamp,
        }
        
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            total_count = self.paginator.page.paginator.count
            metadata['total_count'] = total_count
            
            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': total_count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                },
                'metadata': metadata,
            }
        
        serializer = self.get_serializer(queryset, many=True)
        metadata['total_count'] = len(serializer.data)
        
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            },
            'metadata': metadata,
        }
    
    def get_serializer_class(self):
        """
        Select serializer based on action.
        Optimizes performance and applies proper validations.
        """
        if self.action == 'list':
            return TeamListSerializer
        elif self.action == 'create':
            return TeamCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TeamUpdateSerializer
        return TeamSerializer
    
    def get_queryset(self):
        """
        Retrieve teams with optimizations based on action.
        Applies client scoping and annotations for performance.
        """
        queryset = super().get_queryset().select_related('client_account')
        
        # Annotations to avoid N queries in serializers
        queryset = queryset.annotate(
            members_count=Count('members', distinct=True),
            active_members_count=Count(
                'members',
                filter=Q(members__is_active=True),
                distinct=True
            ),
        )
        
        # Action-specific optimizations
        if self.action == 'list':
            # List: select_related only (performance)
            queryset = queryset.select_related('manager', 'parent_team')
            
        elif self.action in ['retrieve', 'update', 'partial_update', 'destroy', 'duplicate']:
            # Details: select_related + prefetch_related
            queryset = queryset.select_related('manager', 'parent_team')
            queryset = queryset.prefetch_related(
                Prefetch(
                    'members',
                    queryset=User.objects.filter(is_active=True).select_related('role'),
                    to_attr='prefetched_active_members'
                ),
                'direct_child_teams'
            )
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """
        List all teams for the client with cache.
        
        Cache:
            - TTL: 120s (2 minutes)
            - Tag versioning: (client_id, 'teams')
            - Skip if Redis not available
        """
        client_id = self.get_client_id()
        
        # Skip cache if no Redis
        if not _is_redis_backend():
            queryset = self.filter_queryset(self.get_queryset())
            response = self._serialize_list_queryset(queryset, client_id)
            return Response(response)
        
        # Build cache key with query params
        cache_key = build_drf_cache_key(
            view_name=self.__class__.__name__,
            action='list',
            client_id=client_id,
            query_params=request.query_params
        )
        
        # Cache producer function
        def fetch_data():
            queryset = self.filter_queryset(self.get_queryset())
            return self._serialize_list_queryset(queryset, client_id)
        
        # Cache get/set with tag versioning
        cached_response = cache_get_set(
            key=cache_key,
            producer=fetch_data,
            ttl=120,
            tag=(client_id, 'teams')
        )
        
        return Response(cached_response)
    
    def create(self, request, *args, **kwargs):
        """
        Create a new team.
        
        Features:
            - Transaction atomicity
            - Cache invalidation after commit
            - Audit log SOC 2
            - Strict validation via serializer
        """
        try:
            serializer = self.get_serializer(
                data=request.data,
                context=self.get_serializer_context()
            )
            serializer.is_valid(raise_exception=True)
            
            with transaction.atomic():
                instance = serializer.save()
                
                client_id = instance.client_account_id
                transaction.on_commit(
                    lambda: self._invalidate_all_related_caches(client_id)
                )
            
            audit_log(
                event='team_create_success',
                action='create',
                actor_id=str(request.user.id),
                client_id=str(instance.client_account_id),
                target_type='team',
                target_id=str(instance.id),
                outcome='success',
                extra={'name': instance.name}
            )
            
            ctx = ctx_from_request(request)
            ctx.update({
                'event': 'team_created',
                'team_id': str(instance.id),
                'team_name': instance.name
            })
            logger.info('team_created', extra=ctx)
            
            full_serializer = TeamSerializer(
                instance,
                context=self.get_serializer_context()
            )
            
            return Response({
                'success': True,
                'message': f"Team '{instance.name}' created successfully",
                'data': full_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return self.handle_exception(e)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve team details with cache.
        
        Cache: 300s on serialized data
        Query params: include_members=true (optional)
        """
        pk = kwargs.get('pk')
        client_id = self.get_client_id()
        
        if not _is_redis_backend():
            try:
                instance = self.get_object()
                serializer = self.get_serializer(instance)
                data = serializer.data
                
                if request.query_params.get('include_members') == 'true':
                    prefetched_members = getattr(instance, 'prefetched_active_members', None)
                    if prefetched_members is not None:
                        active_members = [
                            {
                                'id': str(user.id),
                                'email': user.email,
                                'first_name': user.first_name,
                                'last_name': user.last_name,
                                'role_name': user.role_name,
                            }
                            for user in prefetched_members
                        ]
                    else:
                        active_members = instance.members.filter(is_active=True).values(
                            'id', 'email', 'first_name', 'last_name', 'role_name'
                        )
                    data['active_members'] = list(active_members)
                
                return Response({
                    'success': True,
                    'data': data
                })
                
            except (Team.DoesNotExist, Http404):
                return Response({
                    'success': False,
                    'error': CoreErrorMessages.OBJECT_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)
        
        user_id = request.user.id
        perm_version = get_permissions_version()
        include_members = request.query_params.get('include_members') == 'true'
        
        cache_key = build_drf_cache_key(
            namespace='team_detail',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            extra=f"{pk}_members={include_members}",
            tag_namespace='teams',
        )
        
        def producer():
            try:
                instance = self.get_object()
                serializer = self.get_serializer(instance)
                data = serializer.data
                
                if include_members:
                    prefetched_members = getattr(instance, 'prefetched_active_members', None)
                    if prefetched_members is not None:
                        active_members = [
                            {
                                'id': str(user.id),
                                'email': user.email,
                                'first_name': user.first_name,
                                'last_name': user.last_name,
                                'role_name': user.role_name,
                            }
                            for user in prefetched_members
                        ]
                    else:
                        active_members = instance.members.filter(is_active=True).values(
                            'id', 'email', 'first_name', 'last_name', 'role_name'
                        )
                    data['active_members'] = list(active_members)
                
                return {"success": True, "data": data}
                
            except (Team.DoesNotExist, Http404):
                return {"success": False, "error": CoreErrorMessages.OBJECT_NOT_FOUND, "status": 404}
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=300,
            tag=(client_id, 'teams')
        )
        
        if not cached_data.get('success'):
            return Response(
                {"success": False, "error": cached_data.get('error')},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(cached_data)
    
    def update(self, request, *args, **kwargs):
        """
        Full update of a team (PUT).
        
        Permissions: Admin/Manager (enforced via ScopedPermission + REGISTRY)
        Security: TOCTOU prevention with select_for_update()
        """
        try:
            pk = kwargs.get('pk')
            client_id = self.get_client_id()
            partial = kwargs.pop('partial', False)
            
            with transaction.atomic():
                instance = Team.objects.select_for_update().filter(
                    id=pk,
                    client_account_id=client_id
                ).first()
                
                if not instance:
                    audit_log(
                        event='team_update_not_found',
                        action='update',
                        actor_id=str(request.user.id),
                        client_id=str(client_id),
                        target_type='team',
                        target_id=str(pk),
                        outcome='not_found',
                    )
                    
                    return Response({
                        'success': False,
                        'error': CoreErrorMessages.OBJECT_NOT_FOUND
                    }, status=status.HTTP_404_NOT_FOUND)
                
                serializer = self.get_serializer(instance, data=request.data, partial=partial)
                serializer.is_valid(raise_exception=True)
                
                changed_fields = sorted(serializer.validated_data.keys())
                instance = serializer.save()
                
                transaction.on_commit(lambda: self._invalidate_all_related_caches(client_id))
            
            audit_log(
                event='team_update_success',
                action='update',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='team',
                target_id=str(instance.id),
                fields_changed=changed_fields,
                outcome='success',
                extra={'team_name': instance.name}
            )
            
            return Response({
                'success': True,
                'message': f"Team '{instance.name}' updated successfully",
                'data': serializer.data
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def partial_update(self, request, *args, **kwargs):
        """
        Partial update of a team (PATCH).
        
        Permissions: Admin/Manager (enforced via ScopedPermission + REGISTRY)
        Security: TOCTOU prevention with select_for_update()
        """
        try:
            pk = kwargs.get('pk')
            client_id = self.get_client_id()
            
            with transaction.atomic():
                instance = Team.objects.select_for_update().filter(
                    id=pk,
                    client_account_id=client_id
                ).first()
                
                if not instance:
                    audit_log(
                        event='team_partial_update_not_found',
                        action='partial_update',
                        actor_id=str(request.user.id),
                        client_id=str(client_id),
                        target_type='team',
                        target_id=str(pk),
                        outcome='not_found',
                    )
                    
                    return Response({
                        'success': False,
                        'error': CoreErrorMessages.OBJECT_NOT_FOUND
                    }, status=status.HTTP_404_NOT_FOUND)
                
                serializer = self.get_serializer(instance, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                
                changed_fields = sorted(serializer.validated_data.keys())
                instance = serializer.save()
                
                transaction.on_commit(lambda: self._invalidate_all_related_caches(client_id))
            
            audit_log(
                event='team_partial_update_success',
                action='partial_update',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='team',
                target_id=str(instance.id),
                fields_changed=changed_fields,
                outcome='success',
                extra={'team_name': instance.name}
            )
            
            return Response({
                'success': True,
                'message': f"Team '{instance.name}' updated successfully",
                'data': serializer.data
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a team.
        
        Permissions: Admin only (enforced via ScopedPermission + REGISTRY)
        Security: TOCTOU prevention with select_for_update()
        
        Validations:
            - Cannot delete team with active members
            - Children teams are orphaned (parent_team → NULL) via CASCADE
            - Inactive members are orphaned (user.team → NULL)
        """
        try:
            pk = kwargs.get('pk')
            client_id = self.get_client_id()
            
            with transaction.atomic():
                instance = Team.objects.select_for_update().filter(
                    id=pk,
                    client_account_id=client_id
                ).first()
                
                if not instance:
                    audit_log(
                        event='team_delete_not_found',
                        action='delete',
                        actor_id=str(request.user.id),
                        client_id=str(client_id),
                        target_type='team',
                        target_id=str(pk),
                        outcome='not_found',
                    )
                    
                    return Response({
                        'success': False,
                        'error': CoreErrorMessages.OBJECT_NOT_FOUND
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # Check for active members
                if hasattr(instance, 'active_members_count'):
                    active_members_count = instance.active_members_count
                elif hasattr(instance, 'prefetched_active_members'):
                    active_members_count = len(instance.prefetched_active_members)
                else:
                    active_members_count = instance.members.filter(is_active=True).count()
                
                if active_members_count > 0:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_IN_USE.format(
                            fields=f"{active_members_count} active member(s) still in this team"
                        )
                    )
                
                # Orphan inactive members (soft delete)
                instance.members.filter(is_active=False).update(team=None)
                
                # Children teams are automatically orphaned via SET_NULL
                
                team_name = instance.name
                team_id = instance.id
                
                instance.delete()
                transaction.on_commit(lambda: self._invalidate_all_related_caches(client_id))
            
            audit_log(
                event='team_delete_success',
                action='delete',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='team',
                target_id=str(team_id),
                outcome='success',
                extra={'team_name': team_name}
            )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            return self.handle_exception(e)
    
    # ===== CUSTOM ACTIONS =====
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """
        List members of this team.
        
        Query params:
            - active: true/false (default: true)
            - role_name: filter by role name
        """
        try:
            team = self.get_object()
            
            is_active = request.query_params.get('active', 'true').lower() == 'true'
            role_name = request.query_params.get('role_name')
            
            members_qs = team.members.select_related('role')
            
            if is_active:
                members_qs = members_qs.filter(is_active=True)
            
            if role_name:
                members_qs = members_qs.filter(role__name=role_name)
            
            members_data = members_qs.values(
                'id', 'email', 'first_name', 'last_name',
                'is_active', 'last_login', 'role_name'
            )
            
            return Response({
                'success': True,
                'team': {
                    'id': str(team.id),
                    'name': team.name
                },
                'members': list(members_data),
                'total_count': members_qs.count()
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Global summary of teams.
        
        Returns:
            - Statistics (total teams, members, hierarchy depth)
            - Team distribution (by size)
            - Hierarchy statistics
        """
        try:
            client_id = self.get_client_id()
            
            teams = Team.objects.filter(client_account_id=client_id)
            
            annotated_teams = teams.annotate(
                active_members=Count('members', filter=Q(members__is_active=True), distinct=True)
            )
            
            stats = {
                'total_teams': teams.count(),
                'total_members': User.objects.filter(
                    client_account_id=client_id,
                    team__isnull=False,
                    is_active=True
                ).count(),
                'teams_with_manager': teams.filter(manager__isnull=False).count(),
                'root_teams': teams.filter(parent_team__isnull=True).count(),
            }
            
            team_distribution = list(
                annotated_teams.values(
                    'name', 'active_members'
                ).order_by('-active_members')
            )
            
            return Response({
                'success': True,
                'data': {
                    'statistics': stats,
                    'team_distribution': team_distribution,
                    'client_id': str(client_id),
                    'generated_at': timezone.now().isoformat()
                }
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplicate an existing team with a new name.
        
        Permissions: Admin only (enforced via ScopedPermission + REGISTRY)
        
        Body:
            {
                "name": "New Team Name"
            }
        
        Note: Children and members are NOT duplicated.
        """
        try:
            client_id = self.get_client_id()
            
            with transaction.atomic():
                source_team = Team.objects.select_for_update().filter(
                    id=pk,
                    client_account_id=client_id
                ).first()
                
                if not source_team:
                    return Response({
                        'success': False,
                        'error': CoreErrorMessages.OBJECT_NOT_FOUND
                    }, status=status.HTTP_404_NOT_FOUND)
                
                new_name = request.data.get('name')
                
                if not new_name:
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field="name")
                    )
                
                if Team.objects.filter(
                    client_account_id=client_id,
                    name__iexact=new_name
                ).exists():
                    raise StandardizedValidationError(
                        f"Team with name '{new_name}' already exists"
                    )
                
                new_team = Team.objects.create(
                    client_account=source_team.client_account,
                    name=new_name,
                    description=source_team.description,
                    manager=source_team.manager,
                    parent_team=source_team.parent_team
                )
                
                transaction.on_commit(lambda: self._invalidate_all_related_caches(client_id))
            
            audit_log(
                event='team_duplicate_success',
                action='duplicate',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='team',
                target_id=str(new_team.id),
                outcome='success',
                extra={
                    'team_name': new_team.name,
                    'source_team_id': str(source_team.id)
                }
            )
            
            serializer = TeamSerializer(new_team, context=self.get_serializer_context())
            
            return Response({
                'success': True,
                'message': f"Team '{new_team.name}' created as duplicate of '{source_team.name}'",
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return self.handle_exception(e)