# apps/signals/views/base_signal_view.py

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from django.db import transaction
from core.apps_shared_methods import BaseAPIView
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..serializers.signal_serializer_factory import SignalSerializerFactory
from ..services.signal_manager import SignalManager

class BaseSignalView(BaseAPIView):
    """
    Base API view for signal operations with centralized logic.
    """
    entity_name = 'signal'
    
    def get_object(self):
        """Get signal instance based on pk"""
        pk = self.kwargs.get('pk')
        if not pk:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
        queryset = self.get_queryset()
        obj = queryset.filter(id=pk).first()
        
        if not obj:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
        self.validate_client_id(obj)
        return obj
    
    def get(self, request, pk=None, *args, **kwargs):
        """Handle GET requests based on path"""
        # Custom endpoints check
        path = request.path.split('/')
        
        # Handle specialized endpoints
        if 'by-account' in path:
            return self.by_account(request)
        elif 'by-tech-stack' in path:
            return self.by_tech_stack(request)
        elif 'account-tech-evaluation' in path:
            return self.account_tech_evaluation(request)
        elif 'account-profile' in path:
            return self.account_profile(request)
        
        # Default list/detail behavior
        if pk:
            # Detail view
            instance = self.get_object()
            serializer = SignalSerializerFactory.get_serializer_for_instance(instance)
            return Response(serializer(instance).data)
        else:
            # List view
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
                
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
    
    def get_serializer(self, instance=None, many=False, **kwargs):
        """
        Get an appropriate serializer instance for the data or model instance.
        
        Args:
            instance: Optional model instance or queryset to serialize
            many: Whether to serialize multiple instances
            **kwargs: Additional serializer arguments
            
        Returns:
            Serializer instance
        """
        context = self.get_serializer_context()
        
        if instance is None:
            return self.serializer_class(**kwargs, context=context)
        
        # For a queryset or list, use the first item to determine the serializer
        if many and hasattr(instance, '__iter__') and len(instance) > 0:
            first_item = instance[0] if isinstance(instance, list) else instance.first()
            if first_item:
                serializer_class = SignalSerializerFactory.get_serializer_for_instance(first_item)
                return serializer_class(instance, many=True, context=context, **kwargs)
        
        # For a single instance, get the appropriate serializer
        if not many and instance is not None:
            serializer_class = SignalSerializerFactory.get_serializer_for_instance(instance)
            return serializer_class(instance, context=context, **kwargs)
        
        # Fallback to the view's default serializer class
        return self.serializer_class(instance, many=many, context=context, **kwargs)

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'client_id': self.get_client_id(),
            'format': self.format_kwarg,
            'view': self
        }
    
    def post(self, request, pk=None, *args, **kwargs):
        """Handle POST requests based on path"""
        # Check for specific action endpoints
        path = request.path.split('/')
        
        if pk:
            instance = self.get_object()
            
            if 'approve' in path:
                return self.approve(request, instance)
            elif 'reject' in path:
                return self.reject(request, instance)
            elif 'confirm' in path:
                return self.confirm(request, instance)
            elif 'merge' in path:
                return self.merge(request, instance)
                
        # Standard creation
        try:
            client_id = self.get_client_id()
            
            # Process data through SignalManager
            data = request.data.copy()
            signal = SignalManager.create_signal(
                data=data,
                user=request.user,
                client_id=client_id
            )
            
            # Return serialized response
            serializer = SignalSerializerFactory.get_serializer_for_instance(signal)
            return Response(
                serializer(signal).data,
                status=status.HTTP_201_CREATED
            )
            
        except StandardizedValidationError as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)
        
    @transaction.atomic
    def bulk_action(self, request):
        """Handle bulk actions for multiple signals"""
        try:
            # Validate the request
            action = request.data.get('action')
            if not action:
                raise StandardizedValidationError({
                    'action': 'Action is required for bulk operations'
                })
                
            signal_ids = request.data.get('signal_ids')
            if not signal_ids or not isinstance(signal_ids, list):
                raise StandardizedValidationError({
                    'signal_ids': 'List of signal IDs is required'
                })
            
            # Get the signals
            signals = []
            for signal_id in signal_ids:
                try:
                    # Use the get_object method from the appropriate view
                    # This is a simplification - in practice, you'd need to determine
                    # the correct signal type and query it
                    queryset = self.get_queryset()
                    signal = queryset.filter(id=signal_id).first()
                    
                    if not signal:
                        raise StandardizedValidationError({
                            'signal_ids': f'Signal with ID {signal_id} not found'
                        })
                        
                    self.validate_client_id(signal)
                    signals.append(signal)
                    
                except Exception as e:
                    raise StandardizedValidationError({
                        'signal_ids': f'Error with signal ID {signal_id}: {str(e)}'
                    })
            
            # Process the action
            results = {
                'processed': 0,
                'skipped': 0,
                'errors': []
            }
            
            if action == 'approve':
                for signal in signals:
                    try:
                        if signal.status == signal.Status.PENDING:
                            # Use the service layer
                            SignalManager.approve_signal(
                                signal=signal,
                                user=request.user
                            )
                            results['processed'] += 1
                        else:
                            results['skipped'] += 1
                    except Exception as e:
                        results['errors'].append(f"Error processing signal {signal.id}: {str(e)}")
                        
            elif action == 'reject':
                reason = request.data.get('reason')
                
                for signal in signals:
                    try:
                        if signal.status == signal.Status.PENDING:
                            # Use the service layer
                            SignalManager.reject_signal(
                                signal=signal,
                                user=request.user,
                                reason=reason
                            )
                            results['processed'] += 1
                        else:
                            results['skipped'] += 1
                    except Exception as e:
                        results['errors'].append(f"Error processing signal {signal.id}: {str(e)}")
                        
            elif action == 'merge':
                # For merge, we need a target signal
                target_signal_id = request.data.get('target_signal_id')
                if not target_signal_id:
                    raise StandardizedValidationError({
                        'target_signal_id': 'Target signal ID is required for merge operations'
                    })
                
                # Get the target signal
                queryset = self.get_queryset()
                target_signal = queryset.filter(id=target_signal_id).first()
                
                if not target_signal:
                    raise StandardizedValidationError({
                        'target_signal_id': 'Target signal not found'
                    })
                    
                self.validate_client_id(target_signal)
                
                # Process each signal for merging
                for signal in signals:
                    try:
                        # Skip the target signal if it's in the list
                        if str(signal.id) == str(target_signal_id):
                            results['skipped'] += 1
                            continue
                            
                        # Use the service layer
                        SignalManager.merge_signals(
                            source_signal=signal,
                            target_signal=target_signal,
                            user=request.user
                        )
                        results['processed'] += 1
                    except Exception as e:
                        results['errors'].append(f"Error merging signal {signal.id}: {str(e)}")
                        
                # Include the updated target signal in results
                serializer = SignalSerializerFactory.get_serializer_for_instance(target_signal)
                results['target_signal'] = serializer(target_signal).data
                
            else:
                raise StandardizedValidationError({
                    'action': f'Unknown action: {action}. Valid actions are: approve, reject, merge'
                })
                
            return Response(results)
            
        except StandardizedValidationError as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)
    
    # These methods need to be implemented by subclasses
    def by_account(self, request):
        raise NotImplementedError("Subclasses must implement by_account()")
        
    def by_tech_stack(self, request):
        raise NotImplementedError("Subclasses must implement by_tech_stack()")
        
    def account_tech_evaluation(self, request):
        raise NotImplementedError("Subclasses must implement account_tech_evaluation()")
        
    def account_profile(self, request):
        raise NotImplementedError("Subclasses must implement account_profile()")
            
    def approve(self, request, instance):
        """Approve a signal"""
        try:
            # Extract additional data
            updated_value = request.data.get('value')
            source_contact_id = request.data.get('source_contact_id')
            source_department_id = request.data.get('source_department_id')
            
            # Get related objects if IDs provided
            source_contact = None
            if source_contact_id:
                from apps.accounts.models import Contact
                try:
                    source_contact = Contact.objects.get(
                        id=source_contact_id,
                        client_id=self.get_client_id()
                    )
                except Contact.DoesNotExist:
                    raise StandardizedValidationError({
                        'source_contact_id': CoreErrorMessages.OBJECT_NOT_FOUND
                    })
            
            source_department = None
            if source_department_id:
                from apps.core_apps.models import StandardDepartment
                try:
                    source_department = StandardDepartment.objects.get(
                        id=source_department_id
                    )
                except StandardDepartment.DoesNotExist:
                    raise StandardizedValidationError({
                        'source_department_id': CoreErrorMessages.OBJECT_NOT_FOUND
                    })
            
            # Use SignalManager to approve signal
            updated_signal = SignalManager.approve_signal(
                signal=instance,
                user=request.user,
                updated_value=updated_value,
                source_contact=source_contact,
                source_department=source_department
            )
            
            # Return serialized response
            serializer = SignalSerializerFactory.get_serializer_for_instance(updated_signal)
            return Response(
                serializer(updated_signal).data,
                status=status.HTTP_200_OK
            )
            
        except StandardizedValidationError as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)
            
    def reject(self, request, instance):
        """Reject a signal"""
        try:
            reason = request.data.get('reason')
            
            updated_signal = SignalManager.reject_signal(
                signal=instance,
                user=request.user,
                reason=reason
            )
            
            # Return serialized response
            serializer = SignalSerializerFactory.get_serializer_for_instance(updated_signal)
            return Response(
                serializer(updated_signal).data,
                status=status.HTTP_200_OK
            )
            
        except StandardizedValidationError as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)

    def merge(self, request, instance):
        """
        Merge a signal into another signal.
        
        Args:
            request: HTTP request
            instance: Source signal to merge from
            
        Returns:
            Response with merged signal details
        """
        try:
            # Get target signal ID from request
            target_signal_id = request.data.get('target_signal_id')
            if not target_signal_id:
                raise StandardizedValidationError({
                    'target_signal_id': 'Target signal ID is required'
                })
            
            # Import helper
            from apps.signals.utils.signal_helpers import SignalHelpers
            
            # Find the target signal
            target_signal = SignalHelpers.get_signal_by_id(
                signal_id=target_signal_id,
                client_id=self.get_client_id()
            )
            
            if not target_signal:
                raise StandardizedValidationError({
                    'target_signal_id': 'Target signal not found'
                })
            
            # Use the SignalManager to merge signals
            merged_signal = SignalManager.merge_signals(
                source_signal=instance,
                target_signal=target_signal,
                user=request.user
            )
            
            # Return serialized response
            serializer = SignalSerializerFactory.get_serializer_for_instance(merged_signal)
            return Response({
                'success': True,
                'message': 'Signal merged successfully',
                'signal': serializer(merged_signal).data
            })
            
        except StandardizedValidationError as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)
        
    def confirm(self, request, instance):
        """Confirm a signal, incrementing its confirmation count"""
        try:
            # Get source contact if provided
            source_contact = None
            source_contact_id = request.data.get('source_contact_id')
            
            if source_contact_id:
                from apps.accounts.models import Contact
                try:
                    source_contact = Contact.objects.get(
                        id=source_contact_id,
                        client_id=self.get_client_id()
                    )
                except Contact.DoesNotExist:
                    raise StandardizedValidationError({
                        'source_contact_id': CoreErrorMessages.OBJECT_NOT_FOUND
                    })
            
            # Use SignalManager to confirm signal
            updated_signal = SignalManager.confirm_signal(
                signal=instance,
                user=request.user,
                source_contact=source_contact
            )
            
            # Return serialized response
            serializer = SignalSerializerFactory.get_serializer_for_instance(updated_signal)
            return Response({
                'success': True,
                'message': f'Signal confirmed (count: {updated_signal.confirmation_count})',
                'signal': serializer(updated_signal).data
            })
            
        except StandardizedValidationError as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)