# backend/end_users/views/role_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Prefetch
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from ..models.user_model import UserRole, User
from ..serializers.role_serializers import (
    RoleSerializer,
    RoleUpdateSerializer,
    RoleListSerializer,
    RolePermissionsMatrixSerializer
)


class UserRoleViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing user roles with client scoping.
    
    Features:
    - CRUD complet avec permissions admin-only
    - Mapping synonymes write→create, modify→update
    - PATCH contraint aux permissions uniquement
    - Format canonique API : name, read, create, update, delete
    - Client scoping automatique via ClientScopeManager
    """
    
    queryset = UserRole.objects.all()
    serializer_class = RoleSerializer  # Par défaut
    entity_name = 'user_role'
    permission_classes = [IsAuthenticated]
    
    # Configuration des filtres
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['read', 'write', 'modify', 'delete']  # Champs internes pour filtres
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        """
        Sélection du serializer selon l'action pour optimiser les performances
        et implémenter les contraintes PATCH.
        """
        if self.action == 'list':
            return RoleListSerializer  # Optimisé, moins de champs
        elif self.action == 'partial_update':
            return RoleUpdateSerializer  # Contrainte PATCH + mapping synonymes
        elif self.action == 'permissions_matrix':
            return RolePermissionsMatrixSerializer  # Format spécialisé UI
        else:
            return RoleSerializer  # Complet (create, retrieve, update, destroy)
    
    def get_queryset(self):
        """
        Get user roles for the current client with optimized queries.
        Performance: select_related + prefetch_related pour éviter N+1.
        """
        queryset = UserRole.objects.all()
        
        # Apply client scoping automatique
        queryset = self.filter_queryset_by_client(queryset)
        
        # Optimisations performance selon l'action
        if self.action in ['list', 'permissions_matrix']:
            # Liste : optimiser les compteurs users_count
            queryset = queryset.select_related('client_account').prefetch_related(
                Prefetch(
                    'users', 
                    queryset=User.objects.filter(is_active=True),
                    to_attr='active_users'  # Cache pour get_users_count()
                )
            )
        elif self.action in ['retrieve', 'update', 'partial_update']:
            # Détail : charger les relations utiles
            queryset = queryset.select_related('client_account')
        
        return queryset
    
    def get_serializer_context(self):
        """
        Ajouter le client_id au contexte pour ClientScopeManager.SerializerMixin.
        Nécessaire pour la validation unicité du nom par client.
        """
        context = super().get_serializer_context()
        context['client_id'] = self.get_client_id()
        return context
    
    def perform_create(self, serializer):
        """
        Création avec client_account automatique depuis JWT.
        Validation admin-only appliquée.
        """
        # Vérifier les droits admin avant création
        if not self.request.user.has_admin_rights():
            raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
        
        # Le client_account sera automatiquement ajouté par ClientScopeManager
        serializer.save()
    
    def perform_update(self, serializer):
        """
        Mise à jour avec vérification admin + contraintes métier.
        """
        # Vérifier les droits admin
        if not self.request.user.has_admin_rights():
            raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
        
        # Vérification métier : ne pas supprimer le rôle Admin s'il est le dernier
        instance = self.get_object()
        if (instance.name == 'Admin' and 
            hasattr(serializer, 'validated_data') and 
            serializer.validated_data.get('name') != 'Admin'):
            
            # Compter les autres rôles Admin dans ce client
            other_admin_roles = UserRole.objects.filter(
                client_account=instance.client_account,
                name='Admin'
            ).exclude(id=instance.id).count()
            
            if other_admin_roles == 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED
                )
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """
        Suppression avec protection du rôle Admin et utilisateurs assignés.
        """
        # Vérifier les droits admin
        if not self.request.user.has_admin_rights():
            raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
        
        # Protection : ne pas supprimer le rôle Admin s'il est le dernier
        if instance.name == 'Admin':
            other_admin_roles = UserRole.objects.filter(
                client_account=instance.client_account,
                name='Admin'
            ).exclude(id=instance.id).count()
            
            if other_admin_roles == 0:
                raise StandardizedValidationError(CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED)
        
        # Protection : vérifier qu'aucun utilisateur n'a ce rôle
        users_count = instance.users.filter(is_active=True).count()
        if users_count > 0:
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_IN_USE.format(fields=f'role "{instance.name}"')
            )
        
        # Suppression sécurisée
        instance.delete()
    
    @action(detail=False, methods=['get'])
    def permissions_matrix(self, request):
        """
        Matrix des permissions par rôle avec format canonique.
        
        Retourne la matrice complète des permissions pour l'UI admin.
        Format de sortie : permissions en format canonique (create/update).
        """
        roles = self.get_queryset()
        
        # Utiliser le serializer spécialisé pour format uniforme
        serializer = self.get_serializer(roles, many=True)
        matrix_data = serializer.data
        
        # Ajout de métadonnées utiles
        total_roles = len(matrix_data)
        total_users_with_roles = sum(role['users_count'] for role in matrix_data)
        
        return Response({
            'success': True,
            'data': matrix_data,
            'metadata': {
                'total_roles': total_roles,
                'total_users_with_roles': total_users_with_roles,
                'client_id': str(self.get_client_id()),
                'generated_at': timezone.now().isoformat()
            }
        })
    
    @action(detail=True, methods=['get'])
    def assigned_users(self, request, pk=None):
        """
        Liste des utilisateurs assignés à ce rôle.
        Utile pour l'UI admin et la validation avant suppression.
        """
        role = self.get_object()
        
        # Utilisateurs actifs avec ce rôle
        active_users = role.users.filter(is_active=True).select_related('team', 'organization')
        
        users_data = []
        for user in active_users:
            users_data.append({
                'id': str(user.id),
                'email': user.email,
                'full_name': user.get_full_name(),
                'team': user.team.name if user.team else None,
                'organization': user.organization.name if user.organization else None,
                'is_superuser': user.is_superuser,
                'last_login': user.last_login
            })
        
        return Response({
            'success': True,
            'data': {
                'role': {
                    'id': str(role.id),
                    'name': role.name
                },
                'users': users_data,
                'total_users': len(users_data)
            }
        })
    
    def list(self, request, *args, **kwargs):
        """
        Override list pour ajouter métadonnées utiles.
        Format de réponse cohérent avec permissions_matrix.
        """
        response = super().list(request, *args, **kwargs)
        
        # Ajouter métadonnées si succès
        if response.status_code == 200:
            response.data = {
                'success': True,
                'data': response.data.get('results', response.data),
                'count': response.data.get('count', len(response.data.get('results', response.data))),
                'client_id': str(self.get_client_id())
            }
        
        return response
    
    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve pour format de réponse cohérent.
        """
        response = super().retrieve(request, *args, **kwargs)
        
        if response.status_code == 200:
            response.data = {
                'success': True,
                'data': response.data
            }
        
        return response