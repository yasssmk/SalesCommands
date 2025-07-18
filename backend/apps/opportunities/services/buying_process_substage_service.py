# backend/apps/opportunities/services/buying_process_substage_service.py

from django.db import transaction
from django.utils import timezone
from django.db.models import Max
from rest_framework.response import Response
from apps.opportunities.models import PipelineSubStage, PipelineStage
from apps.opportunities.config.pipeline_stages import PipelineStagesConfig
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages




class SubstageService:
    """
    Service pour la gestion des sous-étapes de pipeline.
    Renommé de ProcessSubStageService pour plus de clarté.
    """
    
    @classmethod
    def get_substages_for_stage(cls, stage_id: int, client_id: str) -> dict:
        """
        Récupère les substages d'un stage avec leurs métadonnées
        
        Args:
            stage_id: ID du stage parent
            client_id: ID du client
            
        Returns:
            dict: Substages avec leurs données complètes
        """
        try:
            # ✅ Import différé pour éviter l'import circulaire
            from ..serializers.pipeline_substage_serializer import PipelineSubStageSerializer
            
            # Récupérer le stage
            stage = PipelineStage.objects.get(id=stage_id, client_id=client_id)
            
            # Récupérer les substages avec optimisations
            substages = stage.substages.filter(
                is_active=True,
                client_id=client_id
            ).select_related(
                'stage'
            ).prefetch_related(
                'metadata__stakeholders',
                'activity_links__activity'
            ).order_by('order')
            
            # Sérialiser les substages
            substages_serializer = PipelineSubStageSerializer(substages, many=True)
            
            return {
                'substages': substages_serializer.data,
                'substages_count': substages.count(),
                'stage_id': stage.id,
                'stage_name': stage.name
            }
            
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get substages: {str(e)}"
                )
            )
    
    @classmethod
    def create_substage_with_metadata(cls, validated_data: dict, metadata_data: dict, 
                                    user, client_id: str) -> 'PipelineSubStage':
        """
        Crée une substage avec ses métadonnées
        
        Args:
            validated_data: Données validées de la substage
            metadata_data: Données des métadonnées (stakeholders, etc.)
            user: Utilisateur créateur
            client_id: ID du client
            
        Returns:
            PipelineSubStage: Instance créée
        """

        # ✅ Import différé pour éviter l'import circulaire
        from ..serializers.pipeline_substage_serializer import PipelineSubStageSerializer
        from ..models.substage_metadata import SubStageMetadata
        
        with transaction.atomic():
            # Créer la substage
            substage_serializer = PipelineSubStageSerializer(
                data=validated_data,
                context={'client_id': client_id}
            )
            substage_serializer.is_valid(raise_exception=True)

            substage = substage_serializer.save(
                client_id=client_id,
                created_by=user,
                updated_by=user
            )
            
            # Créer les métadonnées si fournies
            if metadata_data:
                cls._create_substage_metadata(substage, metadata_data, user, client_id)
            
            return substage
                

    
    @classmethod
    def update_substage_with_metadata(cls, substage: 'PipelineSubStage', substage_data: dict,
                                    metadata_data: dict, user, client_id: str) -> 'PipelineSubStage':
        """
        Met à jour une substage avec ses métadonnées
        
        Args:
            substage: Instance de la substage à mettre à jour
            substage_data: Nouvelles données de la substage
            metadata_data: Nouvelles données des métadonnées
            user: Utilisateur qui effectue la mise à jour
            client_id: ID du client
            
        Returns:
            PipelineSubStage: Instance mise à jour
        """

        # ✅ Import différé pour éviter l'import circulaire
        from ..serializers.pipeline_substage_serializer import PipelineSubStageSerializer
        
        with transaction.atomic():
            # Mettre à jour la substage
            substage_serializer = PipelineSubStageSerializer(
                substage,
                data=substage_data,
                partial=True,
                context={'client_id': client_id}
            )
            substage_serializer.is_valid(raise_exception=True)
            updated_substage = substage_serializer.save(updated_by=user)
            
            # Mettre à jour les métadonnées si fournies
            if metadata_data:
                cls._update_substage_metadata(updated_substage, metadata_data, user, client_id)
            
            return updated_substage
                

    
    @classmethod
    def _create_substage_metadata(cls, substage: 'PipelineSubStage', metadata_data: dict, 
                                user, client_id: str):
        """
        Crée les métadonnées pour une substage
        
        Args:
            substage: Instance de la substage
            metadata_data: Données des métadonnées
            user: Utilisateur créateur
            client_id: ID du client
        """
        try:
            from ..models.substage_metadata import SubStageMetadata
            from apps.accounts.models import Contact
            
            # Créer les métadonnées de base
            metadata = SubStageMetadata.objects.create(
                substage=substage,
                department=metadata_data.get('department', ''),
                objective=metadata_data.get('objective', ''),
                validation_criteria=metadata_data.get('validation_criteria', ''),
                notes=metadata_data.get('notes', ''),
                client_id=client_id,
                created_by=user,
                updated_by=user
            )
            
            # Ajouter les stakeholders si fournis
            stakeholder_ids = metadata_data.get('stakeholder_ids', [])
            if stakeholder_ids:
                stakeholders = Contact.objects.filter(
                    id__in=stakeholder_ids,
                    client_id=client_id
                )
                metadata.stakeholders.set(stakeholders)
                
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to create metadata: {str(e)}"
                )
            )
    
    @classmethod
    def _update_substage_metadata(cls, substage: 'PipelineSubStage', metadata_data: dict,
                                user, client_id: str):
        """
        Met à jour les métadonnées d'une substage
        
        Args:
            substage: Instance de la substage
            metadata_data: Nouvelles données des métadonnées
            user: Utilisateur qui effectue la mise à jour
            client_id: ID du client
        """
        try:
            from ..models.substage_metadata import SubStageMetadata
            from apps.accounts.models import Contact
            
            # Récupérer ou créer les métadonnées
            metadata, created = SubStageMetadata.objects.get_or_create(
                substage=substage,
                client_id=client_id,
                defaults={
                    'created_by': user,
                    'updated_by': user
                }
            )
            
            # Mettre à jour les champs
            metadata.department = metadata_data.get('department', metadata.department)
            metadata.objective = metadata_data.get('objective', metadata.objective)
            metadata.validation_criteria = metadata_data.get('validation_criteria', metadata.validation_criteria)
            metadata.notes = metadata_data.get('notes', metadata.notes)
            metadata.updated_by = user
            metadata.save()
            
            # Mettre à jour les stakeholders si fournis
            stakeholder_ids = metadata_data.get('stakeholder_ids')
            if stakeholder_ids is not None:
                stakeholders = Contact.objects.filter(
                    id__in=stakeholder_ids,
                    client_id=client_id
                )
                metadata.stakeholders.set(stakeholders)
                
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to update metadata: {str(e)}"
                )
            )
    
    @classmethod
    def mark_substage_as_started(cls, substage_id: int, client_id: str, user) -> 'PipelineSubStage':
        """
        Marque une substage comme commencée
        
        Args:
            substage_id: ID de la substage
            client_id: ID du client
            user: Utilisateur qui démarre la substage
            
        Returns:
            PipelineSubStage: Instance mise à jour
        """
        try:
            substage = PipelineSubStage.objects.get(
                id=substage_id,
                client_id=client_id
            )
            
            substage.mark_as_started()
            substage.updated_by = user
            substage.save()
            
            return substage
            
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
            )
    
    @classmethod
    def mark_substage_as_completed(cls, substage_id: int, client_id: str, user) -> 'PipelineSubStage':
        """
        Marque une substage comme terminée
        
        Args:
            substage_id: ID de la substage
            client_id: ID du client
            user: Utilisateur qui termine la substage
            
        Returns:
            PipelineSubStage: Instance mise à jour
        """
        try:
            substage = PipelineSubStage.objects.get(
                id=substage_id,
                client_id=client_id
            )
            
            substage.mark_as_completed()
            substage.updated_by = user
            substage.save()
            
            return substage
            
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
            )
    
    @classmethod
    def mark_substage_as_blocked(cls, substage_id: int, blocked_reason: str, 
                               client_id: str, user) -> 'PipelineSubStage':
        """
        Marque une substage comme bloquée
        
        Args:
            substage_id: ID de la substage
            blocked_reason: Raison du blocage
            client_id: ID du client
            user: Utilisateur qui bloque la substage
            
        Returns:
            PipelineSubStage: Instance mise à jour
        """
        try:
            substage = PipelineSubStage.objects.get(
                id=substage_id,
                client_id=client_id
            )
            
            substage.mark_as_blocked()
            substage.notes = f"BLOCKED: {blocked_reason}\n{substage.notes or ''}"
            substage.updated_by = user
            substage.save()
            
            return substage
            
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
            )
    
    @classmethod
    def reorder_substages(cls, stage_id: int, substage_orders: list, client_id: str, user):
        """
        Réordonne les substages d'un stage
        
        Args:
            stage_id: ID du stage parent
            substage_orders: Liste de tuples (substage_id, new_order)
            client_id: ID du client
            user: Utilisateur qui effectue le réordonnement
        """
        try:
            with transaction.atomic():
                stage = PipelineStage.objects.get(id=stage_id, client_id=client_id)
                
                for substage_id, new_order in substage_orders:
                    substage = stage.substages.get(
                        id=substage_id,
                        client_id=client_id
                    )
                    substage.order = new_order
                    substage.updated_by = user
                    substage.save()
                    
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
            )
    
    @classmethod
    def get_substage_analytics(cls, stage_id: int, client_id: str) -> dict:
        """
        Récupère les analytics d'un stage (substages)
        
        Args:
            stage_id: ID du stage
            client_id: ID du client
            
        Returns:
            dict: Métriques des substages
        """
        try:
            stage = PipelineStage.objects.get(id=stage_id, client_id=client_id)
            substages = stage.substages.filter(is_active=True, client_id=client_id)
            
            total_count = substages.count()
            completed_count = substages.filter(
                status=PipelineStagesConfig.SubStageStatus.COMPLETED
            ).count()
            in_progress_count = substages.filter(
                status=PipelineStagesConfig.SubStageStatus.IN_PROGRESS
            ).count()
            blocked_count = substages.filter(
                status=PipelineStagesConfig.SubStageStatus.BLOCKED
            ).count()
            overdue_count = sum(1 for substage in substages if cls._is_substage_overdue(substage))
            
            return {
                'stage_id': stage.id,
                'stage_name': stage.name,
                'total_substages': total_count,
                'completed_substages': completed_count,
                'in_progress_substages': in_progress_count,
                'blocked_substages': blocked_count,
                'overdue_substages': overdue_count,
                'completion_percentage': round((completed_count / total_count * 100), 2) if total_count > 0 else 0,
                'average_duration': cls._calculate_average_duration(substages)
            }
            
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
    
    @classmethod
    def _calculate_average_duration(cls, substages_queryset) -> float:
        """
        Calcule la durée moyenne des substages terminées
        
        Args:
            substages_queryset: QuerySet des substages
            
        Returns:
            float: Durée moyenne en jours
        """
        completed_substages = substages_queryset.filter(
            status=PipelineStagesConfig.SubStageStatus.COMPLETED,
            actual_start_date__isnull=False,
            actual_end_date__isnull=False
        )
        
        if not completed_substages.exists():
            return 0.0
        
        total_duration = 0
        count = 0
        
        for substage in completed_substages:
            duration = (substage.actual_end_date.date() - substage.actual_start_date.date()).days
            total_duration += duration
            count += 1
        
        return round(total_duration / count, 2) if count > 0 else 0.0
    
    @classmethod
    def _is_substage_overdue(cls, substage: 'PipelineSubStage') -> bool:
        """
        ✅ Méthode unique pour vérifier si une substage est en retard
        Cette méthode reste uniquement dans SubstageService
        
        Args:
            substage: Instance de PipelineSubStage
            
        Returns:
            bool: True si la substage est en retard
        """
        # Ne pas considérer comme en retard si déjà terminée
        if substage.status == PipelineStagesConfig.SubStageStatus.COMPLETED:
            return False
        
        # Vérifier avec end_date si disponible
        if substage.end_date:
            return timezone.now().date() > substage.end_date
        
        # Vérifier avec start_date + estimated_duration_days
        if substage.actual_start_date and substage.estimated_duration_days:
            expected_end = substage.actual_start_date.date() + timezone.timedelta(
                days=substage.estimated_duration_days
            )
            return timezone.now().date() > expected_end
        
        # Vérifier avec start_date + estimated_duration_days (planifié)
        if substage.start_date and substage.estimated_duration_days:
            expected_end = substage.start_date + timezone.timedelta(
                days=substage.estimated_duration_days
            )
            return timezone.now().date() > expected_end
        
        return False
    
    @classmethod
    def get_overdue_substages(cls, client_id: str) -> list:
        """
        Récupère toutes les substages en retard pour un client
        
        Args:
            client_id: ID du client
            
        Returns:
            list: Liste des substages en retard
        """
        substages = PipelineSubStage.objects.filter(
            client_id=client_id,
            is_active=True
        ).exclude(
            status=PipelineStagesConfig.SubStageStatus.COMPLETED
        ).select_related('stage', 'stage__template')
        
        overdue_substages = []
        for substage in substages:
            if cls._is_substage_overdue(substage):
                overdue_substages.append({
                    'substage_id': substage.id,
                    'substage_name': substage.name,
                    'stage_name': substage.stage.name,
                    'template_name': substage.stage.template.name if substage.stage.template else None,
                    'days_overdue': (timezone.now().date() - substage.end_date).days if substage.end_date else None,
                    'status': substage.status
                })
        
        return overdue_substages