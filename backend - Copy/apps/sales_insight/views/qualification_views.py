from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.sales_insight.models import QualificationChange
from apps.sales_insight.serializers import (
    QualificationChangeSerializer,
    ApproveChangesSerializer,
    ProcessAIDataSerializer
)
from apps.sales_insight.services.qualification_service import QualificationService
from core.exceptions import StandardizedValidationError


class QualificationViewSet(viewsets.ViewSet, ClientScopeManager.ViewMixin):
    """
    API endpoints for qualification data and change management.
    """
    
    @action(detail=False, methods=['post'])
    def process_ai_data(self, request):
        """
        Process AI-generated data for an account and create qualification changes.
        
        POST /api/qualification/process_ai_data/
        """
        serializer = ProcessAIDataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        account_id = request.query_params.get('account_id')
        if not account_id:
            return Response(
                {"error": _("account_id is required as a query parameter")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = QualificationService.process_ai_data(
                ai_data=serializer.validated_data['ai_data'],
                account_id=account_id,
                user=request.user,
                source=serializer.validated_data.get('source', 'ai_analysis')
            )
            
            return Response(result, status=status.HTTP_200_OK)
        except StandardizedValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def pending_changes(self, request):
        """
        Get pending qualification changes for an account.
        
        GET /api/qualification/pending_changes/?account_id=<account_id>&entity_type=<entity_type>
        """
        account_id = request.query_params.get('account_id')
        entity_type = request.query_params.get('entity_type')
        
        if not account_id:
            return Response(
                {"error": _("account_id is required as a query parameter")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if entity_type:
                # Get changes for a specific entity type
                if entity_type not in ['account', 'org_unit', 'contact']:
                    return Response(
                        {"error": _("entity_type must be one of: account, org_unit, contact")},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                changes = QualificationService.get_pending_changes_by_entity_type(
                    account_id=account_id,
                    entity_type=entity_type,
                    user=request.user
                )
            else:
                # Get all pending changes
                changes = QualificationService.get_all_pending_changes(
                    account_id=account_id,
                    user=request.user
                )
            
            # Convert QualificationChange objects to serialized data
            if entity_type == 'account' and 'account' in changes:
                changes['account'] = QualificationChangeSerializer(
                    changes['account'], many=True
                ).data
            elif entity_type == 'org_unit' and 'org_units' in changes:
                for org_name, org_changes in changes['org_units'].items():
                    changes['org_units'][org_name] = QualificationChangeSerializer(
                        org_changes, many=True
                    ).data
            elif entity_type == 'contact' and 'contacts' in changes:
                for contact_name, contact_changes in changes['contacts'].items():
                    changes['contacts'][contact_name] = QualificationChangeSerializer(
                        contact_changes, many=True
                    ).data
            elif not entity_type:
                # Format all changes
                if 'account' in changes:
                    changes['account'] = QualificationChangeSerializer(
                        changes['account'], many=True
                    ).data
                
                if 'org_units' in changes:
                    for org_name, org_changes in changes['org_units'].items():
                        changes['org_units'][org_name] = QualificationChangeSerializer(
                            org_changes, many=True
                        ).data
                
                if 'contacts' in changes:
                    for contact_name, contact_changes in changes['contacts'].items():
                        changes['contacts'][contact_name] = QualificationChangeSerializer(
                            contact_changes, many=True
                        ).data
            
            return Response(changes, status=status.HTTP_200_OK)
        except StandardizedValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def approve_changes(self, request):
        """
        Approve or reject qualification changes with human modifications.
        
        POST /api/qualification/approve_changes/?account_id=<account_id>&entity_type=<entity_type>
        """
        serializer = ApproveChangesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        account_id = request.query_params.get('account_id')
        entity_type = request.query_params.get('entity_type')
        
        if not account_id:
            return Response(
                {"error": _("account_id is required as a query parameter")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if entity_type and entity_type not in ['account', 'org_unit', 'contact']:
            return Response(
                {"error": _("entity_type must be one of: account, org_unit, contact")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if entity_type:
                # Process changes for a specific entity type
                result = QualificationService.approve_entity_changes(
                    account_id=account_id,
                    entity_type=entity_type,
                    changes_data=serializer.validated_data['changes'],
                    user=request.user
                )
            else:
                # Process all changes together
                result = QualificationService.approve_changes_with_modifications(
                    changes_data=serializer.validated_data['changes'],
                    user=request.user
                )
            
            return Response(result, status=status.HTTP_200_OK)
        except StandardizedValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def change_history(self, request):
        """
        Get change history for an account or specific entity.
        
        GET /api/qualification/change_history/?account_id=<account_id>&entity_type=<entity_type>&entity_id=<entity_id>
        """
        account_id = request.query_params.get('account_id')
        entity_type = request.query_params.get('entity_type')
        entity_id = request.query_params.get('entity_id')
        
        if not account_id:
            return Response(
                {"error": _("account_id is required as a query parameter")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if entity_type and entity_id:
                # Get history for a specific entity
                history = QualificationService.get_change_history(
                    account_id=account_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    user=request.user
                )
            else:
                # Get history for the entire account
                history = QualificationService.get_full_change_history(
                    account_id=account_id,
                    user=request.user
                )
            
            return Response(history, status=status.HTTP_200_OK)
        except StandardizedValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)