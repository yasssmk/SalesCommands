# backend/apps/opportunities/services/activity_pipeline_service.py

from typing import List, Dict, Optional
from django.db import transaction
from rest_framework.response import Response
from apps.activities.models import Activity
from apps.opportunities.models import (
    PipelineSubStage, 
    SubStageActivity, 
    OpportunityPipeline
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages


class ActivityPipelineService:
    """
    Service pour gérer les liaisons entre activités et pipelines.
    Gère la liaison automatique, mise à jour des statuts, et détection d'activités.
    """
    
    @classmethod
    def link_activity_to_substage(cls, activity_id: int, substage_id: int, 
                                client_id: str, link_type='FUTURE_ACTIVITY',
                                is_required=False, 
                                user=None) -> Response:
        """
        Lie une activité existante à une sous-étape
        """
        try:
            with transaction.atomic():
                # Récupérer l'activité
                try:
                    activity = Activity.objects.get(id=activity_id, client_id=client_id)
                except Activity.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND.format(object_type='Activity')
                    )
                
                # Récupérer la sous-étape
                try:
                    substage = PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
                except PipelineSubStage.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                    )
                
                # Vérifier que l'activité appartient au bon compte
                opportunity = substage.stage.opportunity_pipeline.opportunity
                if activity.account != opportunity.account:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.ACTIVITY_NOT_IN_PIPELINE
                    )
                
                # Créer la liaison dans SubStageActivity
                link = SubStageActivity.create_link(
                    substage=substage,
                    activity=activity,
                    link_type=link_type,
                    is_required=is_required,
                    user=user
                )
                
                # Mettre à jour l'activité avec la liaison directe
                activity.link_to_substage(substage)
                
                return Response({
                    'success': True,
                    'message': f'Activity "{activity.title}" linked to substage "{substage.name}"',
                    'data': {
                        'link_id': link.id,
                        'activity_id': activity.id,
                        'activity_title': activity.title,
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'link_type': link_type,
                        'is_required': is_required
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def create_activity_for_substage(cls, substage_id: int, activity_data: Dict, 
                                   client_id: str, user=None) -> Response:
        """
        Crée une nouvelle activité directement liée à une sous-étape
        """
        try:
            with transaction.atomic():
                # Récupérer la sous-étape
                try:
                    substage = PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
                except PipelineSubStage.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                    )
                
                # Récupérer l'opportunité et le compte
                opportunity = substage.stage.opportunity_pipeline.opportunity
                account = opportunity.account
                
                # Créer l'activité
                activity = Activity.objects.create(
                    title=activity_data.get('title', f'Activity for {substage.name}'),
                    description=activity_data.get('description', ''),
                    activity_type=activity_data.get('activity_type', 'TASK'),
                    account=account,
                    owner=user or opportunity.deal_owner,
                    opportunity=opportunity,
                    pipeline_substage=substage,
                    scheduled_start=activity_data.get('scheduled_start'),
                    scheduled_end=activity_data.get('scheduled_end'),
                    status='PLANNED',
                    client_id=client_id,
                    user=user
                )
                
                # Lier les contacts si spécifiés
                contact_ids = activity_data.get('contact_ids', [])
                if contact_ids:
                    from apps.accounts.models import Contact
                    contacts = Contact.objects.filter(
                        id__in=contact_ids,
                        account=account,
                        client_id=client_id
                    )
                    activity.contacts.set(contacts)
                elif opportunity.contact:
                    # Utiliser le contact principal de l'opportunité par défaut
                    activity.contacts.add(opportunity.contact)
                
                # Créer la liaison SubStageActivity
                link = SubStageActivity.create_link(
                    substage=substage,
                    activity=activity,
                    link_type='FUTURE_ACTIVITY',
                    is_required=activity_data.get('is_required', False),
                    user=user
                )
                
                return Response({
                    'success': True,
                    'message': f'Activity "{activity.title}" created and linked to substage "{substage.name}"',
                    'data': {
                        'activity_id': activity.id,
                        'activity_title': activity.title,
                        'activity_type': activity.activity_type,
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'link_id': link.id,
                        'scheduled_start': activity.scheduled_start,
                        'scheduled_end': activity.scheduled_end
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def update_substage_from_activities(cls, substage_id: int, client_id: str) -> Response:
        """
        Met à jour le statut d'une sous-étape basé sur ses activités liées
        """
        try:
            # Récupérer la sous-étape
            try:
                substage = PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Récupérer toutes les liaisons d'activités
            activity_links = SubStageActivity.objects.filter(
                substage=substage,
                client_id=client_id
            ).select_related('activity')
            
            # Analyser les activités
            total_activities = activity_links.count()
            completed_activities = activity_links.filter(is_completed=True).count()
            required_activities = activity_links.filter(is_required=True)
            required_completed = required_activities.filter(is_completed=True).count()
            required_total = required_activities.count()
            
            # Simplification pour MVP : utiliser seulement les activités terminées
            completing_activities = activity_links.filter(is_completed=True)
            
            # Déterminer le nouveau statut
            old_status = substage.status
            new_status = old_status
            
            # Logique simplifiée pour MVP
            if required_total > 0 and required_completed == required_total:
                new_status = 'COMPLETED'
            elif completing_activities.exists():
                new_status = 'IN_PROGRESS'
            
            # Mettre à jour si nécessaire
            status_changed = False
            if new_status != old_status:
                if new_status == 'IN_PROGRESS':
                    substage.mark_as_started()
                elif new_status == 'COMPLETED':
                    substage.mark_as_completed()
                status_changed = True
            
            return Response({
                'success': True,
                'message': f'SubStage status {"updated" if status_changed else "checked"}',
                'data': {
                    'substage_id': substage.id,
                    'substage_name': substage.name,
                    'old_status': old_status,
                    'new_status': substage.status,
                    'status_changed': status_changed,
                    'activity_summary': {
                        'total_activities': total_activities,
                        'completed_activities': completed_activities,
                        'required_total': required_total,
                        'required_completed': required_completed,
                        'completing_activities': completing_activities.count()
                    }
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PROGRESS_TRACKING_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def detect_new_pipeline_activities(cls, opportunity_id: int, client_id: str, 
                                     hours_lookback: int = 24) -> Response:
        """
        Détecte les nouvelles activités qui pourraient être liées au pipeline
        """
        try:
            # Récupérer l'opportunité et son pipeline
            from apps.opportunities.models import Opportunity
            try:
                opportunity = Opportunity.objects.get(id=opportunity_id, client_id=client_id)
                pipeline = opportunity.pipeline
            except Opportunity.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
                )
            except AttributeError:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.PIPELINE_NOT_FOUND
                )
            
            # Calculer la période de recherche
            from django.utils import timezone
            from datetime import timedelta
            cutoff_time = timezone.now() - timedelta(hours=hours_lookback)
            
            # Trouver les nouvelles activités liées à cette opportunité
            new_activities = Activity.objects.filter(
                opportunity=opportunity,
                client_id=client_id,
                created_at__gte=cutoff_time,
                pipeline_substage__isnull=True  # Pas encore liées au pipeline
            )
            
            # Analyser les activités et suggérer des liaisons
            suggestions = []
            current_stage = pipeline.current_stage
            
            if current_stage:
                current_substages = current_stage.substages.filter(
                    status__in=['NOT_STARTED', 'IN_PROGRESS'],
                    is_active=True
                )
                
                for activity in new_activities:
                    # Suggérer des liaisons basées sur le type d'activité et la sous-étape
                    for substage in current_substages:
                        suggestion = cls._analyze_activity_substage_match(activity, substage)
                        if suggestion:
                            suggestions.append(suggestion)
            
            return Response({
                'success': True,
                'message': f'Found {new_activities.count()} new activities with {len(suggestions)} linking suggestions',
                'data': {
                    'opportunity_id': opportunity.id,
                    'pipeline_id': pipeline.id,
                    'lookback_hours': hours_lookback,
                    'new_activities_count': new_activities.count(),
                    'new_activities': [
                        {
                            'id': activity.id,
                            'title': activity.title,
                            'activity_type': activity.activity_type,
                            'created_at': activity.created_at,
                            'status': activity.status
                        }
                        for activity in new_activities
                    ],
                    'linking_suggestions': suggestions
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Activity detection failed: {str(e)}")
            )
    
    @classmethod
    def auto_link_activities_to_pipeline(cls, opportunity_id: int, client_id: str, 
                                       user=None) -> Response:
        """
        Lie automatiquement les activités existantes au pipeline basé sur des règles
        """
        try:
            with transaction.atomic():
                # Récupérer l'opportunité et son pipeline
                from apps.opportunities.models import Opportunity
                try:
                    opportunity = Opportunity.objects.get(id=opportunity_id, client_id=client_id)
                    pipeline = opportunity.pipeline
                except Opportunity.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
                    )
                except AttributeError:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.PIPELINE_NOT_FOUND
                    )
                
                # Récupérer les activités non liées
                unlinked_activities = Activity.objects.filter(
                    opportunity=opportunity,
                    client_id=client_id,
                    pipeline_substage__isnull=True
                )
                
                linked_count = 0
                linking_details = []
                
                # Règles de liaison automatique
                for activity in unlinked_activities:
                    best_match = cls._find_best_substage_match(activity, pipeline)
                    
                    if best_match:
                        substage, confidence, reasoning = best_match
                        
                        # Lier si la confiance est suffisante
                        if confidence >= 0.7:  # Seuil de confiance
                            link = SubStageActivity.create_link(
                                substage=substage,
                                activity=activity,
                                link_type='PAST_ACTIVITY' if activity.status == 'COMPLETED' else 'FUTURE_ACTIVITY',
                                user=user
                            )
                            
                            # Correction : utiliser la signature correcte
                            activity.link_to_substage(substage)
                            linked_count += 1
                            
                            linking_details.append({
                                'activity_id': activity.id,
                                'activity_title': activity.title,
                                'substage_id': substage.id,
                                'substage_name': substage.name,
                                'confidence': confidence,
                                'reasoning': reasoning
                            })
                
                return Response({
                    'success': True,
                    'message': f'Auto-linked {linked_count} activities to pipeline',
                    'data': {
                        'opportunity_id': opportunity.id,
                        'pipeline_id': pipeline.id,
                        'total_unlinked': unlinked_activities.count(),
                        'linked_count': linked_count,
                        'linking_details': linking_details
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def get_substage_activities(cls, substage_id: int, client_id: str, 
                              include_completed=True) -> Response:
        """
        Récupère toutes les activités liées à une sous-étape
        """
        try:
            # Récupérer la sous-étape
            try:
                substage = PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Récupérer les liaisons
            queryset = SubStageActivity.objects.filter(
                substage=substage,
                client_id=client_id
            ).select_related('activity')
            
            if not include_completed:
                queryset = queryset.filter(is_completed=False)
            
            activity_links = queryset.order_by('priority_order', 'linked_at')
            
            activities_data = []
            for link in activity_links:
                activity = link.activity
                activities_data.append({
                    'link_id': link.id,
                    'activity_id': activity.id,
                    'activity_title': activity.title,
                    'activity_type': activity.activity_type,
                    'activity_status': activity.status,
                    'link_type': link.link_type,
                    'is_required': link.is_required,
                    'is_completed': link.is_completed,
                    'scheduled_start': activity.scheduled_start,
                    'scheduled_end': activity.scheduled_end,
                    'completed_at': link.completed_at,
                    'is_overdue': link.is_overdue,
                    'days_until_due': link.days_until_due
                })
            
            return Response({
                'success': True,
                'data': {
                    'substage_id': substage.id,
                    'substage_name': substage.name,
                    'stage_name': substage.stage.name,
                    'activities_count': len(activities_data),
                    'activities': activities_data
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Activities retrieval failed: {str(e)}")
            )
    
    # ===== MÉTHODES PRIVÉES =====
    
    @classmethod
    def _analyze_activity_substage_match(cls, activity, substage):
        """
        Analyse si une activité correspond à une sous-étape
        """
        # Règles simples de correspondance
        activity_type = activity.activity_type.lower()
        substage_name = substage.name.lower()
        substage_type = substage.substage_type
        
        score = 0
        reasons = []
        
        # Correspondance par type d'activité
        if activity_type == 'meeting' and 'meeting' in substage_name:
            score += 0.8
            reasons.append('Meeting activity matches substage name')
        elif activity_type == 'call' and ('call' in substage_name or 'phone' in substage_name):
            score += 0.7
            reasons.append('Call activity matches substage name')
        elif activity_type == 'email' and 'email' in substage_name:
            score += 0.6
            reasons.append('Email activity matches substage name')
        
        # Correspondance par type de sous-étape
        if substage_type == 'INTERACTION_CLIENT' and activity_type in ['meeting', 'call', 'email']:
            score += 0.5
            reasons.append('Client interaction activity')
        
        if score >= 0.5:
            return {
                'activity_id': activity.id,
                'activity_title': activity.title,
                'substage_id': substage.id,
                'substage_name': substage.name,
                'confidence': score,
                'reasons': reasons
            }
        
        return None
    
    @classmethod
    def _find_best_substage_match(cls, activity, pipeline):
        """
        Trouve la meilleure correspondance de sous-étape pour une activité
        """
        current_stage = pipeline.current_stage
        if not current_stage:
            return None
        
        best_match = None
        best_score = 0
        
        # Chercher dans l'étape courante d'abord
        for substage in current_stage.substages.filter(is_active=True):
            match = cls._analyze_activity_substage_match(activity, substage)
            if match and match['confidence'] > best_score:
                best_score = match['confidence']
                best_match = (substage, match['confidence'], match['reasons'])
        
        return best_match