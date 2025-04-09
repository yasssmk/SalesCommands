# apps/signals/views/signal_view.py
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Count, Case, When, Value, IntegerField, F
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.core_apps.models import StandardDepartment
from ..models import Signal
from ..serializers import SignalSerializer, SignalBulkActionSerializer
from ..services.signal_status_service import SignalStatusService
from ..services.signal_application_service import SignalApplicationService
from ..services.signal_lifecycle_service import SignalLifecycleService
from ..services.signal_data_service import SignalDataService

class SignalView(BaseAPIView):
    """
    API View for managing signals with client scoping.
    Provides CRUD operations and specialized signal processing endpoints.
    """
    queryset = Signal.objects.select_related(
        'account',
        'source_contact',
        'source_department',
        'account_product_relationship',
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
                
            source_contact_id = self.request.query_params.get('source_contact_id')
            if source_contact_id:
                queryset = queryset.filter(source_contact_id=source_contact_id)
                
            source_department_id = self.request.query_params.get('source_department_id')
            if source_department_id:
                queryset = queryset.filter(source_department_id=source_department_id)
                
            apr_id = self.request.query_params.get('account_product_relationship_id')
            if apr_id:
                queryset = queryset.filter(account_product_relationship_id=apr_id)
            
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
            
            # Lifecycle filters
            min_confirmations = self.request.query_params.get('min_confirmations')
            if min_confirmations and min_confirmations.isdigit():
                queryset = queryset.filter(confirmation_count__gte=int(min_confirmations))
                
            # Effective status filter
            effective_status = self.request.query_params.get('effective_status')
            if effective_status == 'EXPIRED':
                # Find signals that are effectively expired
                from datetime import timedelta
                from django.utils import timezone
                
                # Calculate expiration cutoffs
                profile_expiry = timezone.now() - timedelta(days=SignalLifecycleService.TIME_TO_EXPIRED_PROFILE)
                process_expiry = timezone.now() - timedelta(days=SignalLifecycleService.TIME_TO_EXPIRED_PROCESS)
                
                # Filter for signals that are approved/applied but have expired by time
                queryset = queryset.filter(
                    status__in=['APPROVED', 'APPLIED'],
                ).filter(
                    Q(category__in=['PROFILE', 'QUALIFICATION'], last_confirmed_at__lte=profile_expiry) |
                    Q(category='PROCESS', last_confirmed_at__lte=process_expiry)
                )
            
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
        """Handle POST requests for signal actions"""
        if 'approve' in request.path:
            return self.approve(request, *args, **kwargs)
        elif 'reject' in request.path:
            return self.reject(request, *args, **kwargs)
        elif 'apply' in request.path:
            return self.apply(request, *args, **kwargs)
        elif 'bulk-action' in request.path:
            return self.bulk_action(request, *args, **kwargs)
        elif 'merge' in request.path:
            return self.merge(request, *args, **kwargs)
        elif 'confirm' in request.path:
            return self.confirm(request, *args, **kwargs)
        else:
            # Standard POST behavior
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
        """Approve a signal with optional value update and entity validation"""
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Handle source_contact and source_department assignments
            if 'source_contact_id' in request.data:
                try:
                    from apps.accounts.models import Contact
                    source_contact_id = request.data['source_contact_id']
                    source_contact = Contact.objects.get(id=source_contact_id)
                    
                    # Validate contact belongs to the same account
                    if str(source_contact.account_id) != str(signal.account_id):
                        raise StandardizedValidationError({
                            CoreErrorMessages.INVALID_FIELD: "Source contact must belong to the same account as the signal"
                        })
                    
                    # Update the signal with the contact
                    signal.source_contact = source_contact
                    
                    # Auto-assign the department if not provided
                    if not signal.source_department and source_contact.standard_department:
                        signal.source_department = source_contact.standard_department
                        
                    signal.save(update_fields=['source_contact', 'source_department'])
                    
                except Contact.DoesNotExist:
                    raise StandardizedValidationError({
                        CoreErrorMessages.OBJECT_NOT_FOUND: "Contact not found"
                    })
            
            if 'source_department_id' in request.data and not signal.source_department:
                try:
                    source_department_id = request.data['source_department_id']
                    source_department = StandardDepartment.objects.get(id=source_department_id)
                    
                    # Update the signal with the department
                    signal.source_department = source_department
                    signal.save(update_fields=['source_department'])
                    
                except StandardDepartment.DoesNotExist:
                    raise StandardizedValidationError({
                        CoreErrorMessages.OBJECT_NOT_FOUND: "Department not found"
                    })
            
            # Check if value update is included
            if 'value' in request.data:
                # Validate new value
                is_valid, error_message = Signal.validate_signal_data(
                    signal.field_name, request.data['value'], signal.category
                )
                
                if not is_valid:
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {'detail': error_message}
                    })
                
                # Update the signal value before approval
                signal.value = request.data['value']
                signal.save(update_fields=['value'])
                
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
                signal.refresh_from_db()
                serializer = self.serializer_class(signal)
                return Response(serializer.data)
            else:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Could not apply signal to target entity"
                })
                
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Handle bulk actions for signals"""
        try:
            # Validate the request data
            serializer = SignalBulkActionSerializer(data=request.data)
            if not serializer.is_valid():
                raise StandardizedValidationError(serializer.errors)
                
            validated_data = serializer.validated_data
            action = validated_data['action']
            signal_ids = validated_data['signal_ids']
            
            # Get signals and validate they exist
            signals = self.get_objects(signal_ids)
            if signals.count() != len(signal_ids):
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Build entity references for assignments during approval
            entity_references = {}
            if action == 'approve':
                for key in ['source_contact_id', 'source_department_id']:
                    if key in validated_data:
                        entity_references[key] = validated_data[key]
            
            # Apply requested action to all signals
            if action == 'approve':
                results = SignalStatusService.bulk_approve(signals, request.user, entity_references)
                return Response(results)
                
            elif action == 'reject':
                # Get optional rejection reason
                reason = validated_data.get('reason')
                results = SignalStatusService.bulk_reject(signals, request.user, reason)
                return Response(results)
                
            elif action == 'apply':
                results = SignalApplicationService.bulk_apply_signals(signals, request.user)
                return Response(results)
            
            elif action == 'merge':
                # For merge action, we need a target signal to merge into
                target_signal_id = validated_data.get('target_signal_id')
                if not target_signal_id:
                    raise StandardizedValidationError({
                        CoreErrorMessages.REQUIRED_FIELD: "target_signal_id is required for merge action"
                    })
                
                # Get target signal
                try:
                    target_signal = Signal.objects.get(
                        id=target_signal_id,
                        client_id=self.get_client_id()
                    )
                except Signal.DoesNotExist:
                    raise StandardizedValidationError({
                        CoreErrorMessages.OBJECT_NOT_FOUND: "Target signal not found"
                    })
                
                # Perform bulk merge
                results = SignalLifecycleService.bulk_merge(
                    target_signal=target_signal,
                    signals=signals,
                    user=request.user
                )
                
                # Include the updated target signal in the response
                results['target_signal'] = self.serializer_class(target_signal).data
                
                return Response(results)
                
            else:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_FIELD: f"Unknown action: {action}"
                })
                
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
            
            # Group by field
            field_counts = queryset.values('field_name').annotate(count=Count('id'))
            
            # Format counts into dictionaries
            status_summary = {
                item['status']: item['count'] for item in status_counts
            }
            
            category_summary = {
                item['category']: item['count'] for item in category_counts
            }
            
            entity_summary = {
                item['entity_type']: item['count'] for item in entity_counts
            }
            
            field_summary = {
                item['field_name']: item['count'] for item in field_counts
            }
            
            return Response({
                'total_count': total_count,
                'by_status': status_summary,
                'by_category': category_summary,
                'by_entity_type': entity_summary,
                'by_field': field_summary
            })
                
        except Exception as e:
            return self.handle_exception(e)
        
    @action(detail=True, methods=['post'])
    def merge(self, request, pk=None):
        """
        Merge this signal into another signal for confirmation tracking.
        """
        try:
            # Get source signal (the one being merged)
            source_signal = self.get_objects([pk]).first()
            if not source_signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Get target signal ID from request
            target_signal_id = request.data.get('target_signal_id')
            if not target_signal_id:
                raise StandardizedValidationError({
                    CoreErrorMessages.REQUIRED_FIELD: "target_signal_id is required"
                })
            
            # Get target signal
            try:
                target_signal = Signal.objects.get(
                    id=target_signal_id,
                    client_id=self.get_client_id()
                )
            except Signal.DoesNotExist:
                raise StandardizedValidationError({
                    CoreErrorMessages.OBJECT_NOT_FOUND: "Target signal not found"
                })
            
            # Perform the merge
            merged_signal = SignalLifecycleService.merge_signals(
                target_signal=target_signal,
                source_signal=source_signal,
                user=request.user
            )
            
            # Return the updated target signal
            return Response({
                'success': True,
                'message': 'Signal merged successfully',
                'signal': self.serializer_class(merged_signal).data
            })
        
        except Exception as e:
            return self.handle_exception(e)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """
        Confirm a signal, incrementing confirmation count and updating last_confirmed_at.
        """
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Source of confirmation (optional)
            source = request.data.get('source', 'manual_confirmation')
            
            # Confirm the signal
            updated_signal = SignalLifecycleService.confirm_signal(
                signal=signal,
                user=request.user,
                source=source
            )
            
            # Return the updated signal
            return Response({
                'success': True,
                'message': f'Signal confirmed (count: {updated_signal.confirmation_count})',
                'signal': self.serializer_class(updated_signal).data
            })
        
        except Exception as e:
            return self.handle_exception(e)