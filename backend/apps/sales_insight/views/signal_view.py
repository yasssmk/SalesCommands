# apps/sales_insight/views/signal_view.py
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Count, Case, When, Value, IntegerField, F
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from ..models import Signal
from ..serializers import SignalSerializer
from ..services.signal_status_service import SignalStatusService
from ..services.signal_application_service import SignalApplicationService

class SignalView(BaseAPIView):
    """
    API View for managing signals with client scoping.
    Provides CRUD operations and specialized signal processing endpoints.
    """
    queryset = Signal.objects.select_related(
        'account',
        'org_unit',
        'contact',
        'account_product_detail',
        'approved_by',
        'parent_signal'
    ).prefetch_related('product_alignment')
    
    serializer_class = SignalSerializer
    entity_name = 'signal'
    
    def get_queryset(self):
        """Get base queryset filtered by client and optional filters"""
        queryset = super().get_queryset()
        
        # Apply additional filters if provided
        if self.request.method == 'GET':
            # Entity filters
            account_id = self.request.query_params.get('account_id')
            if account_id:
                queryset = queryset.filter(account_id=account_id)
                
            org_unit_id = self.request.query_params.get('org_unit_id')
            if org_unit_id:
                queryset = queryset.filter(org_unit_id=org_unit_id)
                
            contact_id = self.request.query_params.get('contact_id')
            if contact_id:
                queryset = queryset.filter(contact_id=contact_id)
                
            apd_id = self.request.query_params.get('account_product_detail_id')
            if apd_id:
                queryset = queryset.filter(account_product_detail_id=apd_id)
            
            # Entity type filter
            entity_type = self.request.query_params.get('entity_type')
            if entity_type:
                queryset = queryset.filter(entity_type=entity_type)
            
            # Signal classification filters
            category = self.request.query_params.get('category')
            if category:
                queryset = queryset.filter(category=category)
                
            status_filter = self.request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
                
            field_name = self.request.query_params.get('field_name')
            if field_name:
                queryset = queryset.filter(field_name=field_name)
            
            # Prioritization filters
            min_value = self.request.query_params.get('min_value')
            if min_value and min_value.isdigit():
                queryset = queryset.filter(potential_value__gte=int(min_value))
                
            urgency = self.request.query_params.get('urgency')
            if urgency:
                queryset = queryset.filter(urgency=urgency)
                
            confidence = self.request.query_params.get('confidence')
            if confidence:
                queryset = queryset.filter(confidence=confidence)
                
            # Product alignment filter
            product_id = self.request.query_params.get('product_id')
            if product_id:
                queryset = queryset.filter(product_alignment_id=product_id)
            
            # Source filter
            source = self.request.query_params.get('source')
            if source:
                queryset = queryset.filter(source=source)
            
            # Date range filters
            created_after = self.request.query_params.get('created_after')
            if created_after:
                queryset = queryset.filter(created_at__gte=created_after)
                
            created_before = self.request.query_params.get('created_before')
            if created_before:
                queryset = queryset.filter(created_at__lte=created_before)
                
            # Approval filters
            approved_by = self.request.query_params.get('approved_by')
            if approved_by:
                queryset = queryset.filter(approved_by=approved_by)
                
            approved_after = self.request.query_params.get('approved_after')
            if approved_after:
                queryset = queryset.filter(approved_at__gte=approved_after)
                
            # General search
            search = self.request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(field_name__icontains=search) | 
                    Q(value__icontains=search)
                )
            
        return self.filter_queryset_by_client(queryset)
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests for approving, rejecting, or applying signals"""
        if 'approve' in request.path:
            return self.approve(request, *args, **kwargs)
        elif 'reject' in request.path:
            return self.reject(request, *args, **kwargs)
        elif 'apply' in request.path:
            return self.apply(request, *args, **kwargs)
        elif 'bulk-action' in request.path:
            return self.bulk_action(request, *args, **kwargs)
        else:
            # Standard POST behavior for creating signals
            return super().post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """Handle GET requests for signal list, detail, by-entity, and summary"""
        if 'by-entity' in request.path:
            return self.by_entity(request, *args, **kwargs)
        elif 'summary' in request.path:
            return self.summary(request, *args, **kwargs)
        else:
            # Standard GET behavior for listing or retrieving signals
            return super().get(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a signal"""
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
            # Approve the signal using the service
            updated_signal = SignalStatusService.approve_signal(signal, request.user)
                
            # Return updated signal
            serializer = self.serializer_class(updated_signal)
            return Response(serializer.data)
                
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a signal"""
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Get optional rejection reason
            reason = None
            if request.data and 'reason' in request.data:
                reason = request.data['reason']
                
            # Reject the signal using the service
            updated_signal = SignalStatusService.reject_signal(signal, request.user, reason)
                
            # Return updated signal
            serializer = self.serializer_class(updated_signal)
            return Response(serializer.data)
                
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Apply an approved signal to the target entity"""
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
            # Apply signal using the service
            success = SignalApplicationService.apply_signal(signal, request.user)
            
            if success:
                # Return updated signal
                serializer = self.serializer_class(signal)
                return Response(serializer.data)
            else:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_OPERATION.format(
                        operation="Could not apply signal to target entity"
                    )
                )
                
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Handle bulk actions for signals"""
        try:
            # Validate action and signal_ids
            if 'action' not in request.data or 'signal_ids' not in request.data:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="action and signal_ids")
                )
                
            action = request.data['action']
            signal_ids = request.data['signal_ids']
            
            if not signal_ids or not isinstance(signal_ids, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="signal_ids must be a non-empty list")
                )
                
            # Get signals and validate they exist
            signals = self.get_objects(signal_ids)
            if signals.count() != len(signal_ids):
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Apply requested action to all signals
            if action == 'approve':
                results = SignalStatusService.bulk_approve(signals, request.user)
                return Response(results)
                
            elif action == 'reject':
                # Get optional rejection reason
                reason = None
                if 'reason' in request.data:
                    reason = request.data['reason']
                    
                results = SignalStatusService.bulk_reject(signals, request.user, reason)
                return Response(results)
                
            elif action == 'apply':
                results = SignalApplicationService.bulk_apply_signals(signals, request.user)
                return Response(results)
                
            else:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Unknown action: {action}"
                    )
                )
                
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        """Get signals grouped by entity"""
        try:
            # Get filtered queryset
            queryset = self.get_queryset()
            
            # Group by entity_type
            grouped_signals = {}
            
            for entity_type in Signal.EntityType.choices:
                entity_code = entity_type[0]
                entity_signals = queryset.filter(entity_type=entity_code)
                
                if entity_signals.exists():
                    serializer = self.serializer_class(entity_signals, many=True)
                    grouped_signals[entity_code] = serializer.data
            
            return Response(grouped_signals)
                
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary statistics for signals"""
        try:
            # Get filtered queryset
            queryset = self.get_queryset()
            
            # Calculate summary statistics
            total_count = queryset.count()
            
            # Group by status
            status_counts = queryset.values('status').annotate(count=Count('id'))
            
            # Group by category
            category_counts = queryset.values('category').annotate(count=Count('id'))
            
            # Group by entity type
            entity_counts = queryset.values('entity_type').annotate(count=Count('id'))
            
            # High value signals
            high_value_count = queryset.filter(
                Q(potential_value__gte=70) | Q(urgency=Signal.Urgency.CRITICAL)
            ).count()
            
            # Format status counts into a dictionary
            status_summary = {
                item['status']: item['count'] for item in status_counts
            }
            
            # Format category counts into a dictionary
            category_summary = {
                item['category']: item['count'] for item in category_counts
            }
            
            # Format entity counts into a dictionary  
            entity_summary = {
                item['entity_type']: item['count'] for item in entity_counts
            }
            
            return Response({
                'total_count': total_count,
                'by_status': status_summary,
                'by_category': category_summary,
                'by_entity_type': entity_summary,
                'high_value_count': high_value_count
            })
                
        except Exception as e:
            return self.handle_exception(e)