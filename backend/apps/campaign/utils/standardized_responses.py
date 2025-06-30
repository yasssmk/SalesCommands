# apps/campaign/utils/standardized_responses.py
from rest_framework.response import Response
from rest_framework import status
from typing import Any, Dict, List, Optional, Union


class CampaignSuccessMessages:
    """
    Messages standardisés pour les réponses de succès des campagnes
    Suit le même pattern que CoreErrorMessages et CampaignErrorMessages
    """
    
    # Campaign Creation
    CAMPAIGN_CREATED = "Campaign '{name}' created successfully with {activities_count} activities"
    CAMPAIGN_CREATED_NO_ACTIVITIES = "Campaign '{name}' created successfully (no sequence activities)"
    CAMPAIGN_CREATED_EMPTY = "Campaign '{name}' created but no valid contacts found - please review target selection"
    
    # Campaign Control
    CAMPAIGN_STARTED = "Campaign '{name}' started successfully"
    CAMPAIGN_PAUSED = "Campaign '{name}' paused successfully"
    CAMPAIGN_RESUMED = "Campaign '{name}' resumed successfully"
    
    # Campaign Activities
    ACTIVITY_COMPLETED = "Activity completed successfully"
    ACTIVITY_CALLBACK_SCHEDULED = "Callback scheduled for {date}"
    ACTIVITY_MEETING_SCHEDULED = "Meeting scheduled successfully for {date}"
    ACTIVITY_SEQUENCE_PROGRESSED = "Activity completed, sequence progressed"
    ACTIVITIES_GENERATED = "Generated {activities_count} activities for campaign '{name}'"
    ACTIVITIES_GENERATED_EMPTY = "No activities generated for campaign '{name}' - no valid contacts found"
    
    # Campaign Management
    CONTACT_REMOVED = "Contact removed from campaign successfully"
    ACCOUNT_REMOVED = "Account removed from campaign successfully"
    TARGETS_ADDED = "Successfully added {count} targets to campaign"
    
    # Campaign Data
    PLAYLIST_RETRIEVED = "Retrieved {count} activities from campaign queue"
    CONTACT_QUEUE_RETRIEVED = "Retrieved {count} contacts from campaign queue"
    SUMMARY_RETRIEVED = "Campaign summary retrieved successfully"
    ACTIVITIES_RETRIEVED = "Retrieved {count} campaign activities"
    
    # Bulk Operations
    BULK_OPERATION_COMPLETED = "Bulk operation completed: {successful}/{total} successful"
    BULK_CONTACTS_REMOVED = "Bulk contact removal: {successful}/{total} successful"
    BULK_TARGETS_CREATED = "Bulk targets created: {successful}/{total} successful"


class StandardizedSuccessResponse:
    """
    Classe pour créer des réponses de succès standardisées
    Suit le même pattern que StandardizedValidationError
    """
    
    @staticmethod
    def success(
        message: str,
        data: Any = None,
        meta: Dict = None,
        status_code: int = status.HTTP_200_OK
    ) -> Response:
        """
        Crée une réponse de succès standardisée
        
        Args:
            message: Message de succès (utiliser CampaignSuccessMessages)
            data: Données de la réponse
            meta: Métadonnées additionnelles
            status_code: Code de statut HTTP
        """
        response_data = {
            'success': True,
            'message': message
        }
        
        if data is not None:
            response_data['data'] = data
            
        if meta:
            response_data['meta'] = meta
            
        return Response(response_data, status=status_code)
    
    @staticmethod
    def created(
        message: str,
        data: Any = None,
        resource_id: Union[int, str] = None,
        meta: Dict = None
    ) -> Response:
        """
        Réponse standardisée pour les créations (201)
        """
        if meta is None:
            meta = {}
            
        if resource_id:
            meta['resource_id'] = resource_id
            
        return StandardizedSuccessResponse.success(
            message=message,
            data=data,
            meta=meta,
            status_code=status.HTTP_201_CREATED
        )


class CampaignResponseBuilder:
    """
    Builder spécialisé pour les réponses de campagne
    Utilise les messages standardisés et ajoute des métadonnées contextuelles
    """
    
    @staticmethod
    def campaign_created(
        campaign_id: int,
        campaign_name: str,
        targets_created: int,
        activities_created: int,
        skipped_contacts: List = None,
        targeting_stats: Dict = None,
        additional_data: Dict = None
    ) -> Response:
        """Réponse pour la création de campagne"""
        
        # Choisir le message approprié
        if activities_created > 0:
            message = CampaignSuccessMessages.CAMPAIGN_CREATED.format(
                name=campaign_name,
                activities_count=activities_created
            )
        else:
            message = CampaignSuccessMessages.CAMPAIGN_CREATED_NO_ACTIVITIES.format(
                name=campaign_name
            )
        
        data = {
            'campaign_id': campaign_id,
            'campaign_name': campaign_name,
            'targets_created': targets_created,
            'activities_created': activities_created
        }
        
        if skipped_contacts:
            data['skipped_contacts'] = skipped_contacts
            
        meta = {
            'operation': 'campaign_creation',
            'targets_created': targets_created,
            'activities_created': activities_created
        }
        
        if targeting_stats:
            meta['targeting_stats'] = targeting_stats
            
        return StandardizedSuccessResponse.created(
            message=message,
            data=data,
            resource_id=campaign_id,
            meta=meta
        )
    
    @staticmethod
    def campaign_playlist(
        campaign_id: int,
        campaign_name: str,
        items: List,
        queue_type: str,
        is_sequence: bool,
        total_items: int = None,
        additional_data: Dict = None
    ) -> Response:
        """Réponse pour les playlists de campagne"""
        
        items_count = len(items)
        
        if queue_type == 'activity':
            message = CampaignSuccessMessages.PLAYLIST_RETRIEVED.format(count=items_count)
        else:
            message = CampaignSuccessMessages.CONTACT_QUEUE_RETRIEVED.format(count=items_count)
        
        data = {
            'campaign_id': campaign_id,
            'campaign_name': campaign_name,
            'queue_type': queue_type,
            'is_sequence': is_sequence,
            'items': items
        }
        
        if additional_data:
            data.update(additional_data)
            
        meta = {
            'operation': 'playlist_retrieval',
            'queue_type': queue_type,
            'items_returned': items_count,
            'is_sequence': is_sequence
        }
        
        if total_items is not None:
            meta['total_items'] = total_items
            
        return StandardizedSuccessResponse.success(
            message=message,
            data=data,
            meta=meta
        )
    
    @staticmethod
    def activity_completed(
        result_action: str,
        activity_id: int = None,
        next_activities: List = None,
        additional_info: Dict = None
    ) -> Response:
        """Réponse pour la completion d'activité"""
        
        # Choisir le message basé sur l'action
        if result_action == 'callback_scheduled':
            callback_date = additional_info.get('callback_date') if additional_info else None
            message = CampaignSuccessMessages.ACTIVITY_CALLBACK_SCHEDULED.format(
                date=callback_date or 'requested date'
            )
        elif result_action == 'meeting_scheduled':
            meeting_date = additional_info.get('meeting_date') if additional_info else None
            message = CampaignSuccessMessages.ACTIVITY_MEETING_SCHEDULED.format(
                date=meeting_date or 'requested date'
            )
        elif result_action in ['activity_completed', 'completed_moving_next']:
            message = CampaignSuccessMessages.ACTIVITY_SEQUENCE_PROGRESSED
        else:
            message = CampaignSuccessMessages.ACTIVITY_COMPLETED
        
        data = {
            'action': result_action
        }
        
        if activity_id:
            data['activity_id'] = activity_id
            
        if next_activities:
            data['next_activities'] = next_activities
            
        if additional_info:
            data.update(additional_info)
            
        meta = {
            'operation': 'activity_completion',
            'result_action': result_action
        }
        
        return StandardizedSuccessResponse.success(
            message=message,
            data=data,
            meta=meta
        )
    
    @staticmethod
    def bulk_operation(
        operation_type: str,
        successful_items: List,
        failed_items: List = None,
        custom_message: str = None
    ) -> Response:
        """Réponse pour les opérations bulk"""
        
        total = len(successful_items) + len(failed_items or [])
        successful_count = len(successful_items)
        
        if custom_message:
            message = custom_message
        else:
            message = CampaignSuccessMessages.BULK_OPERATION_COMPLETED.format(
                successful=successful_count,
                total=total
            )
        
        data = {
            'successful': successful_items,
            'successful_count': successful_count,
            'total_processed': total
        }
        
        if failed_items:
            data['failed'] = failed_items
            data['failed_count'] = len(failed_items)
            
        meta = {
            'operation': f'bulk_{operation_type}',
            'success_rate': round((successful_count / total * 100) if total > 0 else 0, 1)
        }
        
        return StandardizedSuccessResponse.success(
            message=message,
            data=data,
            meta=meta
        )
    
    @staticmethod
    def campaign_created_empty(
        campaign_id: int,
        campaign_name: str,
        targets_created: int,
        skipped_contacts: List,
        targeting_stats: Dict = None,
        additional_data: Dict = None
    ) -> Response:
        """Réponse pour une campagne créée mais sans contacts valides"""
        
        message = CampaignSuccessMessages.CAMPAIGN_CREATED_EMPTY.format(
            name=campaign_name
        )
        
        data = {
            'campaign_id': campaign_id,
            'campaign_name': campaign_name,
            'targets_created': targets_created,
            'activities_created': 0,
            'skipped_contacts': skipped_contacts,
            'warning': 'No valid contacts found for campaign activities'
        }
        
        meta = {
            'operation': 'campaign_creation',
            'targets_created': targets_created,
            'activities_created': 0,
            'has_warning': True,
            'warning_type': 'empty_campaign'
        }
        
        if targeting_stats:
            meta['targeting_stats'] = targeting_stats
            
        return StandardizedSuccessResponse.created(
            message=message,
            data=data,
            resource_id=campaign_id,
            meta=meta
        )
    
    @staticmethod
    def activities_generated(
        campaign_id: int,
        campaign_name: str,
        activities_created: int,
        skipped_contacts: List = None,
        additional_data: Dict = None
    ) -> Response:
        """Réponse spécialisée pour la génération d'activités (campagne existante)"""
        
        if activities_created > 0:
            message = CampaignSuccessMessages.ACTIVITIES_GENERATED.format(
                activities_count=activities_created,
                name=campaign_name
            )
        else:
            message = CampaignSuccessMessages.ACTIVITIES_GENERATED_EMPTY.format(
                name=campaign_name
            )
        
        data = {
            'campaign_id': campaign_id,
            'campaign_name': campaign_name,
            'activities_created': activities_created,
            'operation': 'activities_generation'
        }
        
        if skipped_contacts:
            data['skipped_contacts'] = skipped_contacts
            
        if additional_data:
            data.update(additional_data)
            
        meta = {
            'operation': 'activities_generation',
            'activities_created': activities_created,
            'campaign_modified': activities_created > 0
        }
        
        return StandardizedSuccessResponse.success(
            message=message,
            data=data,
            meta=meta
        )