# backend/apps/opportunities/services/buying_process_service.py

from django.db import transaction
from rest_framework.response import Response
from apps.opportunities.models import PipelineTemplate, PipelineStage
from apps.opportunities.config import PipelineStagesConfig
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages


class BuyingProcessService:
    """
    Service simple pour la gestion des templates de pipeline (MVP).
    Scalable avec dispatch pattern.
    """
    
    @classmethod  
    def create_template_with_stages(cls, validated_data: dict, request, client_id: str) -> 'PipelineTemplate':
        """
        Crée un template avec ses stages par défaut selon le template_type
        
        Args:
            validated_data: Données validées du serializer (contient client_id automatiquement)
        
        Returns:
            PipelineTemplate: L'instance créée avec ses étapes
        """

        with transaction.atomic():
            # Créer le template avec les données validées
            template = PipelineTemplate(**validated_data)
            # Sauvegarder avec client_id et user (pattern BaseModelApp)
            template.save(client_id=client_id, user=request.user)
            
            # Créer les stages selon le template_type
            stages_created = cls._create_stages_for_template(template, request)

            from ..services.opportunity_pipeline_service import OpportunityPipelineService
        
            opportunity_pipeline = OpportunityPipelineService.create_opportunity_pipeline(
                template=template, 
                request=request
            )
            
            return template
    
    @classmethod
    def _create_stages_for_template(cls, template: 'PipelineTemplate', request) -> int:
        """
        Crée les étapes par défaut selon le template_type
        Méthode privée réutilisable
        """
        from ..models.pipeline_stage import PipelineStage
        
        stages_data = []
        
        # Récupérer les stages selon le template_type
        if template.template_type == PipelineStagesConfig.TemplateType.DEFAULT:
            stages_data = PipelineStagesConfig.get_default_stages()
        elif template.template_type == PipelineStagesConfig.TemplateType.RENEWAL:
            stages_data = PipelineStagesConfig.get_renewal_stages()
        # Pour CUSTOM, pas de stages automatiques
        
        # Créer tous les stages d'abord (sans linked list)
        created_stages = []
        for stage_name, stage_description, stage_order in stages_data:
            # Créer le stage avec les champs normaux
            stage = PipelineStage(
                template=template,
                name=stage_name,
                description=stage_description,
                order=stage_order,
                is_active=True
            )
            
            # Sauvegarder en évitant la mise à jour de linked list
            stage.save(client_id=template.client_id, user=request.user, skip_linked_list_update=True)
            created_stages.append(stage)
        
        # Maintenant mettre à jour la linked list pour tous les stages en une seule fois
        if created_stages:
            cls._update_template_linked_list(template)
        
        return len(created_stages)
        
    @classmethod
    def _update_template_linked_list(cls, template: 'PipelineTemplate'):
        """
        Met à jour la linked list pour tous les stages d'un template
        Méthode optimisée qui évite la récursion
        """
        from ..models.pipeline_stage import PipelineStage
        
        # Récupérer tous les stages du template ordonnés
        stages = PipelineStage.objects.filter(
            template=template,
            is_active=True,
            client_id=template.client_id
        ).order_by('order')
        
        # Mettre à jour les relations previous/next en une seule passe
        stages_list = list(stages)
        
        for i, stage in enumerate(stages_list):
            # Définir previous_stage
            if i > 0:
                stage.previous_stage = stages_list[i - 1]
            else:
                stage.previous_stage = None
            
            # Définir next_stage
            if i < len(stages_list) - 1:
                stage.next_stage = stages_list[i + 1]
            else:
                stage.next_stage = None
            
            # Sauvegarder avec skip_linked_list_update pour éviter la récursion
            stage.save(update_fields=['previous_stage', 'next_stage'], skip_linked_list_update=True)
            
    @classmethod
    def get_template_with_stages(cls, template_id: int) -> dict:
        """
        Récupère un template avec ses étapes
        Utilise le ClientScope automatiquement via le queryset
        
        Args:
            template_id: ID du template à récupérer
        
        Returns:
            dict: Template avec ses étapes
        """
        try:
            # ✅ Import différé pour éviter l'import circulaire
            from ..serializers.pipeline_template_serializer import PipelineTemplateSerializer
            from ..serializers.pipeline_stage_serializer import PipelineStageSerializer
            
            # Le ClientScope sera géré par la vue qui appelle cette méthode
            # On assume que le template_id est déjà filtré par client dans la vue
            template = PipelineTemplate.objects.get(id=template_id)
            
            # Récupérer les étapes actives
            stages = template.stages.filter(is_active=True).order_by('order')
            
            # Utiliser les serializers pour la cohérence
            template_serializer = PipelineTemplateSerializer(template)
            stages_serializer = PipelineStageSerializer(stages, many=True)
            
            return {
                'template': template_serializer.data,
                'stages': stages_serializer.data,
                'stages_count': stages.count()
            }
            
        except PipelineTemplate.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )

    @classmethod
    def duplicate_template(cls, template_id: int, new_name: str) -> 'PipelineTemplate':
        """
        Duplique un template existant
        Utilise les serializers pour respecter le ClientScope
        
        Args:
            template_id: ID du template source
            new_name: Nom du nouveau template
        
        Returns:
            PipelineTemplate: Le template dupliqué
        """
        try:
            # ✅ Import différé pour éviter l'import circulaire
            from ..serializers.pipeline_template_serializer import PipelineTemplateSerializer
            from ..serializers.pipeline_stage_serializer import PipelineStageSerializer
            
            with transaction.atomic():
                # Récupérer le template source (le ClientScope sera géré par la vue)
                source_template = PipelineTemplate.objects.get(id=template_id)
                
                # Créer le nouveau template avec le serializer
                template_data = {
                    'name': new_name,
                    'description': f"Copy of {source_template.name}",
                    'is_default': False,
                    'order': source_template.order + 1,  # Décaler l'ordre
                    'is_active': True
                }
                
                template_serializer = PipelineTemplateSerializer(data=template_data)
                if not template_serializer.is_valid():
                    raise StandardizedValidationError(
                        f"Template duplication failed: {template_serializer.errors}"
                    )
                
                new_template = template_serializer.save()
                
                # Dupliquer les étapes avec le serializer
                source_stages = source_template.stages.filter(is_active=True).order_by('order')
                
                for source_stage in source_stages:
                    stage_data = {
                        'template': new_template.id,
                        'name': source_stage.name,
                        'description': source_stage.description,
                        'order': source_stage.order,
                        'is_active': True
                    }
                    
                    stage_serializer = PipelineStageSerializer(data=stage_data)
                    if stage_serializer.is_valid():
                        stage_serializer.save()
                
                return new_template
                
        except PipelineTemplate.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
            )
    

    @classmethod
    def get_opportunity_process_overview(cls, opportunity_id: int, template_id: int, client_id: str) -> dict:
        """
        Récupère l'aperçu complet du processus d'une opportunité avec tous les stages et leurs données
        
        Args:
            opportunity_id: ID de l'opportunité
            template_id: ID du template de processus
            client_id: ID du client
            
        Returns:
            dict: Aperçu complet du processus avec métriques détaillées
        """
        try:
            # ✅ Import différé pour éviter l'import circulaire
            from ..serializers.pipeline_template_serializer import PipelineTemplateSerializer
            from ..serializers.pipeline_stage_serializer import PipelineStageSerializer
            from ..serializers.pipeline_substage_serializer import PipelineSubStageSerializer
            from ..models import Opportunity
            
            # Récupérer l'opportunité
            opportunity = Opportunity.objects.get(id=opportunity_id, client_id=client_id)
            
            # Récupérer le template avec ses relations
            template = PipelineTemplate.objects.prefetch_related(
                'stages__substages__metadata'
            ).get(id=template_id, client_id=client_id)
            
            # Récupérer tous les stages avec leurs substages
            stages = template.stages.filter(is_active=True).prefetch_related(
                'substages__metadata'
            ).order_by('order')
            
            # Calculer les métriques globales
            total_stages = stages.count()
            completed_stages = stages.filter(status='COMPLETED').count()
            
            # Calculer les métriques des substages
            total_substages = 0
            completed_substages = 0
            in_progress_substages = 0
            blocked_substages = 0
            
            stages_data = []
            
            for stage in stages:
                # Récupérer les substages du stage
                substages = stage.substages.filter(is_active=True).order_by('order')
                substages_count = substages.count()
                
                # Calculer les métriques du stage
                stage_completed_substages = substages.filter(status='COMPLETED').count()
                stage_in_progress_substages = substages.filter(status='IN_PROGRESS').count()
                stage_blocked_substages = substages.filter(status='BLOCKED').count()
                
                # Mise à jour des métriques globales
                total_substages += substages_count
                completed_substages += stage_completed_substages
                in_progress_substages += stage_in_progress_substages
                blocked_substages += stage_blocked_substages
                
                # Calculer le pourcentage de progression du stage
                stage_progress = (stage_completed_substages / substages_count * 100) if substages_count > 0 else 0
                
                # Sérialiser les substages
                substages_serializer = PipelineSubStageSerializer(substages, many=True)
                
                # Préparer les données du stage
                stage_data = {
                    'id': stage.id,
                    'name': stage.name,
                    'description': stage.description,
                    'order': stage.order,
                    'status': stage.status,
                    'is_active': stage.is_active,
                    'started_at': stage.started_at,
                    'completed_at': stage.completed_at,
                    'estimated_duration': stage.estimated_duration,
                    'substages': substages_serializer.data,
                    'metrics': {
                        'total_substages': substages_count,
                        'completed_substages': stage_completed_substages,
                        'in_progress_substages': stage_in_progress_substages,
                        'blocked_substages': stage_blocked_substages,
                        'progress_percentage': round(stage_progress, 2)
                    }
                }
                
                stages_data.append(stage_data)
            
            # Calculer les pourcentages globaux
            global_progress = (completed_stages / total_stages * 100) if total_stages > 0 else 0
            substages_progress = (completed_substages / total_substages * 100) if total_substages > 0 else 0
            
            # Déterminer le stage actuel
            current_stage = None
            current_stage_data = stages.filter(status='IN_PROGRESS').first()
            if current_stage_data:
                current_stage = {
                    'id': current_stage_data.id,
                    'name': current_stage_data.name,
                    'order': current_stage_data.order
                }
            
            # Sérialiser le template
            template_serializer = PipelineTemplateSerializer(template)
            
            # Calculer les délais
            estimated_total_duration = sum(
                stage.estimated_duration or 0 for stage in stages
            )
            
            # Préparer les données de l'opportunité
            opportunity_data = {
                'id': opportunity.id,
                'title': opportunity.title,
                'status': opportunity.status,
                'account_name': opportunity.account.company_name if opportunity.account else None,
                'deal_owner': opportunity.deal_owner.get_full_name() if opportunity.deal_owner else None,
                'expected_close_date': opportunity.expected_close_date,
                'created_at': opportunity.created_at
            }
            
            # Assembler la réponse complète
            return {
                'opportunity': opportunity_data,
                'template': template_serializer.data,
                'stages': stages_data,
                'current_stage': current_stage,
                'global_metrics': {
                    'total_stages': total_stages,
                    'completed_stages': completed_stages,
                    'total_substages': total_substages,
                    'completed_substages': completed_substages,
                    'in_progress_substages': in_progress_substages,
                    'blocked_substages': blocked_substages,
                    'stages_progress_percentage': round(global_progress, 2),
                    'substages_progress_percentage': round(substages_progress, 2),
                    'estimated_total_duration_days': estimated_total_duration
                },
                'stage_summary': [
                    {
                        'stage_id': stage['id'],
                        'stage_name': stage['name'],
                        'stage_order': stage['order'],
                        'status': stage['status'],
                        'progress_percentage': stage['metrics']['progress_percentage'],
                        'substages_count': stage['metrics']['total_substages'],
                        'completed_substages': stage['metrics']['completed_substages']
                    }
                    for stage in stages_data
                ],
                'next_actions': cls._get_next_actions(stages_data),
                'alerts': cls._get_process_alerts(stages_data, opportunity)
            }
            
        except Opportunity.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
            )
        except PipelineTemplate.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Failed to get opportunity process overview: {str(e)}")  
                
            )
    
    @classmethod
    def _get_next_actions(cls, stages_data: list) -> list:
        """
        Détermine les prochaines actions à effectuer dans le processus
        
        Args:
            stages_data: Données des stages avec leurs substages
            
        Returns:
            list: Liste des prochaines actions recommandées
        """
        next_actions = []
        
        for stage in stages_data:
            # Chercher les substages en cours ou à démarrer
            for substage in stage['substages']:
                if substage['status'] == 'IN_PROGRESS':
                    next_actions.append({
                        'type': 'continue_substage',
                        'priority': 'high',
                        'stage_name': stage['name'],
                        'substage_name': substage['name'],
                        'message': f"Continue working on '{substage['name']}' in stage '{stage['name']}'",
                        'estimated_duration': substage.get('estimated_duration_days'),
                        'overdue': cls._is_substage_overdue_check(substage)
                    })
                elif substage['status'] == 'NOT_STARTED' and len(next_actions) < 3:
                    next_actions.append({
                        'type': 'start_substage',
                        'priority': 'medium',
                        'stage_name': stage['name'],
                        'substage_name': substage['name'],
                        'message': f"Start '{substage['name']}' in stage '{stage['name']}'",
                        'estimated_duration': substage.get('estimated_duration_days')
                    })
                elif substage['status'] == 'BLOCKED':
                    next_actions.append({
                        'type': 'unblock_substage',
                        'priority': 'urgent',
                        'stage_name': stage['name'],
                        'substage_name': substage['name'],
                        'message': f"Resolve blocking issue for '{substage['name']}' in stage '{stage['name']}'",
                        'blocked_reason': substage.get('blocked_reason', 'No reason specified')
                    })
        
        # Trier par priorité
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        next_actions.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return next_actions[:5]  # Limiter à 5 actions
    
    @classmethod
    def _get_process_alerts(cls, stages_data: list, opportunity) -> list:
        """
        Génère des alertes pour le processus
        
        Args:
            stages_data: Données des stages
            opportunity: Instance de l'opportunité
            
        Returns:
            list: Liste des alertes
        """
        alerts = []
        
        # Vérifier les substages bloquées
        blocked_count = 0
        for stage in stages_data:
            stage_blocked = sum(1 for substage in stage['substages'] if substage['status'] == 'BLOCKED')
            blocked_count += stage_blocked
        
        if blocked_count > 0:
            alerts.append({
                'type': 'warning',
                'category': 'blocked_substages',
                'message': f"{blocked_count} substage(s) are currently blocked",
                'action': 'Review and resolve blocking issues'
            })
        
        # Vérifier les retards potentiels
        overdue_count = 0
        for stage in stages_data:
            for substage in stage['substages']:
                if cls._is_substage_overdue_check(substage):
                    overdue_count += 1
        
        if overdue_count > 0:
            alerts.append({
                'type': 'error',
                'category': 'overdue_substages',
                'message': f"{overdue_count} substage(s) are overdue",
                'action': 'Review timeline and update estimates'
            })
        
        # Vérifier la date de clôture prévue
        if opportunity.expected_close_date:
            from datetime import date
            if opportunity.expected_close_date < date.today():
                alerts.append({
                    'type': 'error',
                    'category': 'close_date_passed',
                    'message': 'Expected close date has passed',
                    'action': 'Update expected close date or accelerate process'
                })
        
        return alerts
    
    @classmethod
    def _is_substage_overdue_check(cls, substage_data: dict) -> bool:
        """
        Vérifie si une substage est en retard (version simplifiée pour les données sérialisées)
        
        Args:
            substage_data: Données sérialisées de la substage
            
        Returns:
            bool: True si en retard
        """
        # Version simplifiée pour éviter la dépendance au SubstageService
        # Utilise les champs is_overdue du serializer si disponible
        return substage_data.get('is_overdue', False)