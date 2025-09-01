# backend/end_users/views/role_views.py

from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Prefetch, F
from django.db import transaction, models
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError, StandardizedPermissionDenied
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from ..models.user_model import UserRole, User
from ..serializers.role_serializers import (
    RoleSerializer,
    RoleCreateSerializer,
    RoleUpdateSerializer,
    RoleListSerializer,
    RoleBulkCreateSerializer
)


class UserRoleViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    ViewSet complet pour la gestion des rôles utilisateurs.
    
    Endpoints:
        - GET    /client/roles/           - Liste tous les rôles du client
        - POST   /client/roles/           - Créer un nouveau rôle
        - GET    /client/roles/{id}/      - Détails d'un rôle
        - PUT    /client/roles/{id}/      - Mettre à jour un rôle (complet)
        - PATCH  /client/roles/{id}/      - Modifier permissions uniquement
        - DELETE /client/roles/{id}/      - Supprimer un rôle
    
    Actions supplémentaires:
        - GET    /client/roles/{id}/users/     - Utilisateurs avec ce rôle
        - POST   /client/roles/bulk-create/    - Création en masse
        - GET    /client/roles/summary/        - Résumé des rôles et permissions
    
    Permissions:
        - Lecture : tous les utilisateurs authentifiés
        - Écriture/Modification/Suppression : Admin uniquement
    """
    
    queryset = UserRole.objects.all()
    serializer_class = RoleSerializer
    entity_name = 'role'
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    # Configuration des filtres
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['read', 'write', 'modify', 'delete']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        """
        Sélection du serializer selon l'action.
        Optimise les performances et applique les bonnes validations.
        """
        if self.action == 'list':
            return RoleListSerializer
        elif self.action == 'create':
            return RoleCreateSerializer
        elif self.action == 'partial_update':
            return RoleUpdateSerializer
        # Pas de serializer spécial pour bulk_create, on le gère manuellement
        return RoleSerializer
    
    def get_queryset(self):
        """
        Récupère les rôles du client avec optimisations.
        Applique le client scoping et les annotations pour performance.
        """
        # Client scoping via mixin
        queryset = super().get_queryset()
        
        # Optimisations selon l'action
        if self.action == 'list':
            # Annotate avec le nombre d'utilisateurs pour éviter N+1
            queryset = queryset.annotate(
                users_count=Count('users', filter=Q(users__is_active=True))
            )
        elif self.action in ['retrieve', 'update', 'partial_update']:
            # Prefetch les utilisateurs pour les détails
            queryset = queryset.prefetch_related(
                Prefetch(
                    'users',
                    queryset=User.objects.filter(is_active=True).select_related('team', 'organization')
                )
            )
        
        return queryset
    
    def check_admin_permission(self):
        """
        Vérifie que l'utilisateur a les droits admin.
        Centralise la logique de vérification des permissions.
        """
        user = self.request.user
        
        # Utiliser la méthode has_admin_rights() du modèle User
        # Cette méthode vérifie is_superuser OU role.name == 'Admin'
        if hasattr(user, 'has_admin_rights'):
            if not user.has_admin_rights():
                raise StandardizedPermissionDenied(
                    CoreErrorMessages.PERMISSION_DENIED + " - Admin rights required"
                )
        else:
            # Fallback si la méthode n'existe pas
            # Vérifier les droits admin manuellement
            is_admin = False
            
            # Check superuser status (c'est un attribut, pas une méthode)
            if hasattr(user, 'is_superuser') and user.is_superuser == True:
                is_admin = True
            # Check role
            elif hasattr(user, 'role') and user.role:
                if hasattr(user.role, 'name') and user.role.name == 'Admin':
                    is_admin = True
            
            if not is_admin:
                raise StandardizedPermissionDenied(
                    CoreErrorMessages.PERMISSION_DENIED + " - Admin role required"
                )
        
        return True
    
    def list(self, request, *args, **kwargs):
        """
        Liste tous les rôles du client.
        Accessible à tous les utilisateurs authentifiés.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        # Ajouter des métadonnées utiles
        return Response({
            'success': True,
            'data': serializer.data,
            'metadata': {
                'total_roles': len(serializer.data),
                'client_id': str(self.get_client_id()),
                'timestamp': timezone.now().isoformat()
            }
        })
    
    def create(self, request, *args, **kwargs):
        """
        Créer un nouveau rôle.
        Réservé aux administrateurs.
        """
        # Vérifier les permissions admin
        self.check_admin_permission()
        
        # Log les données reçues pour debug
        print(f"[DEBUG] Creating role with data: {request.data}")
        
        # Validation et création
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        
        # Transaction pour garantir l'intégrité
        with transaction.atomic():
            instance = serializer.save()
            
            # Log l'action
            user_email = request.user.email if hasattr(request.user, 'email') else str(request.user)
            print(f"[AUDIT] Role '{instance.name}' created by {user_email} at {timezone.now()}")
        
        # Retourner avec le serializer complet pour affichage
        full_serializer = RoleSerializer(instance, context=self.get_serializer_context())
        
        return Response({
            'success': True,
            'message': f"Role '{instance.name}' created successfully",
            'data': full_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Détails d'un rôle spécifique.
        Accessible à tous les utilisateurs authentifiés.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Enrichir avec des informations supplémentaires
        data = serializer.data
        
        # Ajouter la liste des utilisateurs actifs si demandé
        if request.query_params.get('include_users') == 'true':
            active_users = instance.users.filter(is_active=True).values(
                'id', 'email', 'first_name', 'last_name', 'team__name'
            )
            data['active_users'] = list(active_users)
        
        return Response({
            'success': True,
            'data': data
        })
    
    def update(self, request, *args, **kwargs):
        """
        Mise à jour complète d'un rôle (PUT).
        Réservé aux administrateurs.
        """
        # Vérifier les permissions admin
        self.check_admin_permission()
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Protection du rôle Admin système
        if instance.name == 'Admin':
            # Empêcher de renommer le rôle Admin
            new_name = request.data.get('name')
            if new_name and new_name != 'Admin':
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot rename the Admin role"
                )
            
            # Empêcher de désactiver les permissions critiques
            if request.data.get('read', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable read permission for Admin role"
                )
            if request.data.get('write', None) == False or request.data.get('create', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable write/create permission for Admin role"
                )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            instance = serializer.save()
            
            # Log l'action
            user_email = request.user.email if hasattr(request.user, 'email') else str(request.user)
            print(f"[AUDIT] Role '{instance.name}' updated by {user_email} at {timezone.now()}")
        
        return Response({
            'success': True,
            'message': f"Role '{instance.name}' updated successfully",
            'data': serializer.data
        })
    
    def partial_update(self, request, *args, **kwargs):
        """
        Mise à jour partielle (PATCH) - permissions uniquement.
        Réservé aux administrateurs.
        """
        # Vérifier les permissions admin
        self.check_admin_permission()
        
        instance = self.get_object()
        
        # Protection du rôle Admin - empêcher de désactiver des permissions critiques
        if instance.name == 'Admin':
            # Vérifier si on essaie de désactiver des permissions critiques
            if request.data.get('read', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable read permission for Admin role"
                )
            if request.data.get('write', None) == False or request.data.get('create', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable write/create permission for Admin role"
                )
            if request.data.get('modify', None) == False or request.data.get('update', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable modify/update permission for Admin role"
                )
            if request.data.get('delete', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable delete permission for Admin role"
                )
        
        # Utiliser le serializer spécialisé pour PATCH
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            instance = serializer.save()
            
            # Log l'action
            changes = ', '.join([f"{k}={v}" for k, v in request.data.items()])
            user_email = request.user.email if hasattr(request.user, 'email') else str(request.user)
            print(f"[AUDIT] Role '{instance.name}' permissions updated ({changes}) by {user_email} at {timezone.now()}")
        
        return Response({
            'success': True,
            'message': f"Role '{instance.name}' permissions updated successfully",
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """
        Supprimer un rôle.
        Réservé aux administrateurs avec validations.
        
        Note importante: Le modèle UserRole a un champ BooleanField nommé 'delete'
        qui masque la méthode delete() héritée de Model. Pour cette raison,
        nous utilisons QuerySet.delete() au lieu de instance.delete().
        """
        # Vérifier les permissions admin
        self.check_admin_permission()
        
        instance = self.get_object()
        
        # Validations métier avant suppression
        with transaction.atomic():
            # 1. Empêcher la suppression du rôle Admin s'il est unique
            if instance.name == 'Admin':
                admin_roles_count = UserRole.objects.filter(
                    client_account=instance.client_account,
                    name='Admin'
                ).count()
                
                if admin_roles_count <= 1:
                    raise StandardizedValidationError(
                        CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED + " - Cannot delete the last Admin role"
                    )
            
            # 2. Vérifier qu'aucun utilisateur actif n'a ce rôle
            active_users_count = instance.users.filter(is_active=True).count()
            if active_users_count > 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_IN_USE.format(
                        fields=f"{active_users_count} active user(s) still have this role"
                    )
                )
            
            # 3. Dissocier les utilisateurs inactifs (soft delete)
            instance.users.filter(is_active=False).update(role=None, role_name=None)
            
            # Log avant suppression
            role_name = instance.name
            role_id = instance.id
            user_email = request.user.email if hasattr(request.user, 'email') else str(request.user)
            print(f"[AUDIT] Role '{role_name}' deleted by {user_email} at {timezone.now()}")
            
            # Suppression effective - utiliser QuerySet car le champ 'delete' masque la méthode delete()
            # Le modèle UserRole a un champ BooleanField nommé 'delete' qui entre en conflit
            UserRole.objects.filter(id=role_id).delete()
        
        # HTTP 204 ne doit pas avoir de body selon la spec REST
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """
        Liste les utilisateurs ayant ce rôle.
        Accessible à tous les utilisateurs authentifiés.
        """
        role = self.get_object()
        
        # Filtres optionnels
        is_active = request.query_params.get('active', 'true').lower() == 'true'
        team_id = request.query_params.get('team_id')
        organization_id = request.query_params.get('organization_id')
        
        # Construction de la requête
        users_qs = role.users.select_related('team', 'organization')
        
        if is_active:
            users_qs = users_qs.filter(is_active=True)
        
        if team_id:
            users_qs = users_qs.filter(team_id=team_id)
        
        if organization_id:
            users_qs = users_qs.filter(organization_id=organization_id)
        
        # Format de sortie
        users_data = users_qs.values(
            'id', 'email', 'first_name', 'last_name',
            'is_active', 'last_login',
            team_name=F('team__name'),
            organization_name=F('organization__name')
        )
        
        return Response({
            'success': True,
            'role': {
                'id': str(role.id),
                'name': role.name
            },
            'users': list(users_data),
            'total_count': users_qs.count()
        })
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Création en masse de rôles.
        Réservé aux administrateurs.
        """
        # Vérifier les permissions admin
        self.check_admin_permission()
        
        # Validation des données
        if not isinstance(request.data, list):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Expected a list of roles"
                )
            )
        
        if len(request.data) > 50:  # Limite de sécurité
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Maximum 50 roles can be created at once"
                )
            )
        
        # Utiliser le serializer de masse
        context = self.get_serializer_context()
        
        # Créer une liste de serializers pour chaque rôle
        created_roles = []
        errors = []
        
        with transaction.atomic():
            for index, role_data in enumerate(request.data):
                serializer = RoleCreateSerializer(data=role_data, context=context)
                if serializer.is_valid():
                    role = serializer.save()
                    created_roles.append(role)
                else:
                    errors.append({
                        'index': index,
                        'errors': serializer.errors
                    })
            
            # Si il y a des erreurs, annuler la transaction
            if errors:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail=f"Validation errors in batch: {errors}"
                    )
                )
            
            # Log l'action
            role_names = [r.name for r in created_roles]
            user_email = request.user.email if hasattr(request.user, 'email') else str(request.user)
            print(f"[AUDIT] {len(created_roles)} roles created in bulk by {user_email}: {role_names}")
        
        # Retourner les rôles créés
        result_serializer = RoleListSerializer(created_roles, many=True)
        
        return Response({
            'success': True,
            'message': f"{len(created_roles)} roles created successfully",
            'data': result_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Résumé global des rôles et permissions du client.
        Accessible à tous les utilisateurs authentifiés.
        """
        client_id = self.get_client_id()
        
        # Statistiques générales
        roles = UserRole.objects.filter(client_account_id=client_id)
        
        # Compter les utilisateurs par permission
        stats = {
            'total_roles': roles.count(),
            'total_users_with_roles': User.objects.filter(
                client_account_id=client_id,
                role__isnull=False,
                is_active=True
            ).count(),
            'permissions_distribution': {
                'read': roles.filter(read=True).count(),
                'write': roles.filter(write=True).count(),
                'modify': roles.filter(modify=True).count(),
                'delete': roles.filter(delete=True).count()
            }
        }
        
        # Distribution des rôles
        role_distribution = roles.annotate(
            active_users=Count('users', filter=Q(users__is_active=True))
        ).values('name', 'active_users').order_by('-active_users')
        
        # Identifier les rôles critiques
        critical_roles = []
        admin_role = roles.filter(name='Admin').first()
        if admin_role:
            admin_users = admin_role.users.filter(is_active=True).count()
            critical_roles.append({
                'role': 'Admin',
                'active_users': admin_users,
                'warning': 'Only one admin user' if admin_users == 1 else None
            })
        
        return Response({
            'success': True,
            'summary': {
                'statistics': stats,
                'role_distribution': list(role_distribution),
                'critical_roles': critical_roles,
                'client_id': str(client_id),
                'generated_at': timezone.now().isoformat()
            }
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Dupliquer un rôle existant avec un nouveau nom.
        Réservé aux administrateurs.
        """
        # Vérifier les permissions admin
        self.check_admin_permission()
        
        source_role = self.get_object()
        new_name = request.data.get('name')
        
        if not new_name:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="name")
            )
        
        # Créer le nouveau rôle
        with transaction.atomic():
            # Le champ 'delete' peut être passé comme paramètre sans problème
            new_role = UserRole.objects.create(
                client_account=source_role.client_account,
                name=new_name,
                read=source_role.read,
                write=source_role.write,
                modify=source_role.modify,
                delete=source_role.delete  # C'est un paramètre, pas un appel de méthode
            )
            
            # Log l'action
            user_email = request.user.email if hasattr(request.user, 'email') else str(request.user)
            print(f"[AUDIT] Role '{new_role.name}' duplicated from '{source_role.name}' by {user_email}")
        
        serializer = RoleSerializer(new_role)
        
        return Response({
            'success': True,
            'message': f"Role '{new_role.name}' created as duplicate of '{source_role.name}'",
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)