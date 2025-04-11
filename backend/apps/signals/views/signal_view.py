# apps/signals/views/signal_view.py
from rest_framework import status
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.core_apps.models import StandardDepartment
from ..models import Signal
from ..serializers import SignalSerializer, SignalBulkSerializer

class SignalView(BaseAPIView):
    """
    API View for managing signals with client scoping.
    Provides CRUD operations and specialized signal processing endpoints.
    """
    queryset = Signal.objects.select_related(
        'account',
        'source_contact',
        'source_department',
    )
    
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
                
            # Date range filters
            created_after = self.request.query_params.get('created_after')
            if created_after:
                queryset = queryset.filter(created_at__gte=created_after)
                
            created_before = self.request.query_params.get('created_before')
            if created_before:
                queryset = queryset.filter(created_at__lte=created_before)
                
            last_confirmed_after = self.request.query_params.get('last_confirmed_after')
            if last_confirmed_after:
                queryset = queryset.filter(last_confirmed_at__gte=last_confirmed_after)
                
            # Source filter
            source = self.request.query_params.get('source')
            if source:
                queryset = queryset.filter(source=source)
                
            # Value search
            value_contains = self.request.query_params.get('value_contains')
            if value_contains:
                queryset = queryset.filter(value__icontains=value_contains)
                
            # General keyword search
            search = self.request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(field_name__icontains=search) | 
                    Q(value__icontains=search)
                )
            
        return self.filter_queryset_by_client(queryset)
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests for signal actions or creation"""
        # Handle specialized actions based on URL path
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
            # Standard POST for signal creation
            client_id = self.get_client_id()
            
            # Handle both single object and list of objects
            if isinstance(request.data, list):
                data_list = request.data
            else:
                data_list = [request.data]
                
            created_signals = []
            
            with transaction.atomic():
                for data_item in data_list:
                    serializer = self.serializer_class(
                        data=data_item, 
                        context={'request': request, 'client_id': client_id}
                    )
                    
                    if serializer.is_valid():
                        # Auto-set status for manual entries
                        if serializer.validated_data.get('source') == 'manual_entry':
                            serializer.validated_data['status'] = Signal.Status.APPROVED
                        
                        # Create signal with client_id
                        try:
                            signal = serializer.save(
                                client_id=client_id,
                                user=request.user
                            )
                            created_signals.append(signal)
                        except Exception as e:
                            # Log the error and re-raise
                            print(f"Error creating signal: {str(e)}")
                            raise
                    else:
                        raise StandardizedValidationError(serializer.errors)
            
            # Return appropriate response format
            if len(created_signals) > 1:
                serializer = self.serializer_class(created_signals, many=True)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                serializer = self.serializer_class(created_signals[0])
                return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests for signal list, detail, by-entity, and summary"""
        if 'by-entity' in request.path:
            return self.by_entity(request, *args, **kwargs)
        elif 'summary' in request.path:
            return self.summary(request, *args, **kwargs)
        elif 'qualification-data' in request.path:
            return self.qualification_data(request, *args, **kwargs)
        elif 'tech-evaluation-data' in request.path:
            return self.tech_evaluation_data(request, *args, **kwargs)
        else:
            # Standard GET behavior for listing or retrieving signals
            return super().get(request, *args, **kwargs)
    
    def approve(self, request, pk=None, *args, **kwargs):
        """Approve a signal"""
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Validate signal can be approved
            if signal.status not in [Signal.Status.PENDING]:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Only pending signals can be approved"
                })
            
            # Update signal value if provided
            if 'value' in request.data:
                signal.value = request.data['value']
            
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
                    if not signal.source_department and hasattr(source_contact, 'standard_department') and source_contact.standard_department:
                        signal.source_department = source_contact.standard_department
                    
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
                    
                except StandardDepartment.DoesNotExist:
                    raise StandardizedValidationError({
                        CoreErrorMessages.OBJECT_NOT_FOUND: "Department not found"
                    })
            
            # Approve the signal
            signal.status = Signal.Status.APPROVED
            signal.approved_by = request.user
            signal.approved_at = timezone.now()
            signal.save()
                
            # Return updated signal
            serializer = self.serializer_class(signal)
            return Response(serializer.data)
            
        except Exception as e:
            return self.handle_exception(e)

    def reject(self, request, pk=None, *args, **kwargs):
        """Reject a signal"""
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Validate signal can be rejected
            if signal.status not in [Signal.Status.PENDING]:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Only pending signals can be rejected"
                })
            
            # Get optional rejection reason
            reason = None
            if request.data and 'reason' in request.data:
                reason = request.data['reason']
                
                # Store rejection reason in metadata
                if reason:
                    if not signal.metadata:
                        signal.metadata = {}
                    signal.metadata['rejection_reason'] = reason
                    signal.metadata['rejected_at'] = timezone.now().isoformat()
                    signal.metadata['rejected_by'] = str(request.user.id)
            
            # Reject the signal
            signal.status = Signal.Status.REJECTED
            signal.save()
                
            # Return updated signal
            serializer = self.serializer_class(signal)
            return Response(serializer.data)
                
        except Exception as e:
            return self.handle_exception(e)
    
    def apply(self, request, pk=None, *args, **kwargs):
        """Apply a signal to update target entity fields"""
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Validate signal can be applied
            if signal.status != Signal.Status.APPROVED:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Only approved signals can be applied"
                })
            
            # Apply signal value to target entity based on entity_type
            if signal.entity_type == Signal.EntityType.ACCOUNT:
                # Apply to account
                account = signal.account
                field_name = signal.field_name
                
                # Update account field if it's a valid field
                if hasattr(account, field_name):
                    setattr(account, field_name, signal.value)
                    account.save(update_fields=[field_name])
                    
                    # Mark signal as applied
                    signal.status = Signal.Status.APPLIED
                    signal.applied_date = timezone.now()
                    signal.save()
                    
                    serializer = self.serializer_class(signal)
                    return Response(serializer.data)
                else:
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_OPERATION: f"Field '{field_name}' is not a valid account field"
                    })
            else:
                # Other entity types - add implementation as needed
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: f"Application for entity type '{signal.entity_type}' not implemented"
                })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def merge(self, request, pk=None, *args, **kwargs):
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
            
            # Enhanced validation
            # Check that signals are for the same account
            if source_signal.account_id != target_signal.account_id:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Cannot merge signals from different accounts"
                })
                
            # Check field name and category match
            if source_signal.field_name != target_signal.field_name:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Cannot merge signals with different field names"
                })
                
            if source_signal.category != target_signal.category:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Cannot merge signals from different categories"
                })
                
            # Prevent merging a signal that's already merged
            if source_signal.status == Signal.Status.MERGED:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Cannot merge a signal that is already merged"
                })
                
            # Prevent merging into a non-approved signal
            if target_signal.status not in [Signal.Status.APPROVED]:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Target signal must be approved"
                })
                
            # Prevent circular merges
            if target_signal.merged_into and target_signal.merged_into.id == source_signal.id:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Circular merge detected"
                })
            
            # Perform the merge
            with transaction.atomic():
                # Increment confirmation count on target signal
                target_signal.confirmation_count += 1
                target_signal.last_confirmed_at = timezone.now()
                
                # Mark source signal as merged
                source_signal.status = Signal.Status.MERGED
                source_signal.merged_into = target_signal
                
                # If source signal has any confirmation history, add it to target
                if source_signal.confirmation_count > 1:
                    target_signal.confirmation_count += (source_signal.confirmation_count - 1)
                
                # Track merge history in metadata
                if not target_signal.metadata:
                    target_signal.metadata = {}
                
                if 'merge_history' not in target_signal.metadata:
                    target_signal.metadata['merge_history'] = []
                
                # Add merge record
                target_signal.metadata['merge_history'].append({
                    'merged_signal_id': str(source_signal.id),
                    'field_name': source_signal.field_name,
                    'timestamp': timezone.now().isoformat(),
                    'merged_by': str(request.user.id),
                    'confirmations_added': source_signal.confirmation_count
                })
                
                # Save both signals
                target_signal.save()
                source_signal.save()
            
            # Return the updated target signal
            return Response({
                'success': True,
                'message': 'Signal merged successfully',
                'signal': self.serializer_class(target_signal).data
            })
        
        except Exception as e:
            return self.handle_exception(e)

    def confirm(self, request, pk=None, *args, **kwargs):
        """
        Confirm a signal, incrementing confirmation count and updating last_confirmed_at.
        Used when the same information is encountered again, increasing its relevance.
        """
        try:
            signal = self.get_objects([pk]).first()
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Enhanced validation
            # Only approved signals can be confirmed
            if signal.status != Signal.Status.APPROVED:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Only approved signals can be confirmed"
                })
            
            # Optional: Add contact who confirmed the information
            if 'source_contact_id' in request.data:
                try:
                    from apps.accounts.models import Contact
                    contact_id = request.data.get('source_contact_id')
                    contact = Contact.objects.get(id=contact_id, client_id=self.get_client_id())
                    
                    # Validate contact belongs to signal's account
                    if contact.account_id != signal.account_id:
                        raise StandardizedValidationError({
                            CoreErrorMessages.INVALID_FIELD: "Contact must belong to the signal's account"
                        })
                    
                    # Store confirmation metadata
                    if not signal.metadata:
                        signal.metadata = {}
                    
                    if 'confirmation_history' not in signal.metadata:
                        signal.metadata['confirmation_history'] = []
                    
                    # Add confirmation record
                    signal.metadata['confirmation_history'].append({
                        'contact_id': str(contact.id),
                        'contact_name': f"{contact.first_name} {contact.last_name}",
                        'timestamp': timezone.now().isoformat(),
                        'confirmed_by': str(request.user.id)
                    })
                    
                except Contact.DoesNotExist:
                    raise StandardizedValidationError({
                        CoreErrorMessages.OBJECT_NOT_FOUND: "Contact not found"
                    })
            
            # Confirm the signal
            signal.confirmation_count += 1
            signal.last_confirmed_at = timezone.now()
            signal.save()
            
            # Return the updated signal
            return Response({
                'success': True,
                'message': f'Signal confirmed (count: {signal.confirmation_count})',
                'signal': self.serializer_class(signal).data
            })
        
        except Exception as e:
            return self.handle_exception(e)
    
    def bulk_action(self, request, *args, **kwargs):
        """Handle bulk actions for signals"""
        try:
            # Validate the request data
            action = request.data.get('action')
            if not action:
                raise StandardizedValidationError({
                    CoreErrorMessages.REQUIRED_FIELD: "action is required"
                })
                
            signal_ids = request.data.get('signal_ids')
            if not signal_ids or not isinstance(signal_ids, list):
                raise StandardizedValidationError({
                    CoreErrorMessages.REQUIRED_FIELD: "signal_ids list is required"
                })
            
            # Get signals and validate they exist
            signals = self.get_objects(signal_ids)
            if signals.count() != len(signal_ids):
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            results = {"processed": 0, "skipped": 0, "errors": []}
            
            # Apply requested action to all signals
            if action == 'approve':
                for signal in signals:
                    try:
                        if signal.status == Signal.Status.PENDING:
                            signal.status = Signal.Status.APPROVED
                            signal.approved_by = request.user
                            signal.approved_at = timezone.now()
                            signal.save()
                            results["processed"] += 1
                        else:
                            results["skipped"] += 1
                    except Exception as e:
                        results["errors"].append(f"Error on signal {signal.id}: {str(e)}")
                        
            elif action == 'reject':
                reason = request.data.get('reason')
                
                for signal in signals:
                    try:
                        if signal.status == Signal.Status.PENDING:
                            # Store rejection reason if provided
                            if reason:
                                if not signal.metadata:
                                    signal.metadata = {}
                                signal.metadata['rejection_reason'] = reason
                                signal.metadata['rejected_at'] = timezone.now().isoformat()
                                signal.metadata['rejected_by'] = str(request.user.id)
                            
                            signal.status = Signal.Status.REJECTED
                            signal.save()
                            results["processed"] += 1
                        else:
                            results["skipped"] += 1
                    except Exception as e:
                        results["errors"].append(f"Error on signal {signal.id}: {str(e)}")
            
            elif action == 'merge':
                # For merge action, we need a target signal to merge into
                target_signal_id = request.data.get('target_signal_id')
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
                
                # Validate target signal is approved
                if target_signal.status != Signal.Status.APPROVED:
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_OPERATION: "Target signal must be approved"
                    })
                
                # Track total confirmations added
                total_confirmations_added = 0
                
                # Process each signal for merging
                with transaction.atomic():
                    for signal in signals:
                        try:
                            # Skip the target signal if it's in the list
                            if signal.id == target_signal.id:
                                results["skipped"] += 1
                                continue
                                
                            # Validate signal can be merged
                            if (signal.status != Signal.Status.MERGED and 
                                signal.field_name == target_signal.field_name and
                                signal.category == target_signal.category and
                                signal.account_id == target_signal.account_id):
                                
                                # Mark source signal as merged
                                signal.status = Signal.Status.MERGED
                                signal.merged_into = target_signal
                                signal.save()
                                
                                # Add confirmations from this signal
                                total_confirmations_added += signal.confirmation_count
                                
                                results["processed"] += 1
                            else:
                                results["skipped"] += 1
                                
                        except Exception as e:
                            results["errors"].append(f"Error on signal {signal.id}: {str(e)}")
                    
                    # Update target signal with all confirmations
                    if total_confirmations_added > 0:
                        target_signal.confirmation_count += total_confirmations_added
                        target_signal.last_confirmed_at = timezone.now()
                        target_signal.save()
                        
                    # Include the updated target signal in results
                    results["target_signal"] = self.serializer_class(target_signal).data
            
            else:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_FIELD: f"Unknown action: {action}"
                })
                
            return Response(results)
                
        except Exception as e:
            return self.handle_exception(e)
    
    def by_entity(self, request, *args, **kwargs):
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
    
    def summary(self, request, *args, **kwargs):
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
            
            # Group by field name
            field_counts = queryset.values('field_name').annotate(count=Count('id'))
            
            # Format counts into dictionaries
            status_summary = {
                item['status']: item['count'] for item in status_counts
            }
            
            category_summary = {
                item['category']: item['count'] for item in category_counts
            }
            
            field_summary = {
                item['field_name']: item['count'] for item in field_counts
            }
            
            return Response({
                'total_count': total_count,
                'by_status': status_summary,
                'by_category': category_summary,
                'by_field': field_summary
            })
                
        except Exception as e:
            return self.handle_exception(e)
            
    def qualification_data(self, request, *args, **kwargs):
        """Get filtered qualification data for an account"""
        try:
            # Get account ID from query params
            account_id = request.query_params.get('account_id')
            if not account_id:
                raise StandardizedValidationError({
                    CoreErrorMessages.REQUIRED_FIELD: "account_id is required"
                })
            
            # Filter signals for the account, qualification category, and approved status
            queryset = self.get_queryset().filter(
                account_id=account_id,
                category=Signal.Category.QUALIFICATION,
                status=Signal.Status.APPROVED
            )
            
            # Additional filtering
            contact_id = request.query_params.get('contact_id')
            if contact_id:
                queryset = queryset.filter(source_contact_id=contact_id)
                
            department_id = request.query_params.get('department_id')
            if department_id:
                queryset = queryset.filter(source_department_id=department_id)
                
            field_name = request.query_params.get('field_name')
            if field_name:
                queryset = queryset.filter(field_name=field_name)
            
            # Group by field_name
            result = {}
            for field in [Signal.Field.OBJECTIVES, Signal.Field.MOTIVATIONS, 
                           Signal.Field.METRICS, Signal.Field.PAIN_POINTS, 
                           Signal.Field.IMPLICATIONS]:
                field_signals = queryset.filter(field_name=field)
                if field_signals.exists():
                    serializer = self.serializer_class(field_signals, many=True)
                    result[field] = serializer.data
            
            return Response(result)
            
        except Exception as e:
            return self.handle_exception(e)
            
    def tech_evaluation_data(self, request, *args, **kwargs):
        """Get tech stack evaluation data for an account"""
        try:
            # Get account ID from query params
            account_id = request.query_params.get('account_id')
            if not account_id:
                raise StandardizedValidationError({
                    CoreErrorMessages.REQUIRED_FIELD: "account_id is required"
                })
            
            # Filter signals for the account, tech_stack category, and approved status
            queryset = self.get_queryset().filter(
                account_id=account_id,
                category=Signal.Category.TECH_STACK,
                status=Signal.Status.APPROVED
            )
            
            # Get tech stack IDs to group by
            from apps.accounts.models import TechStack
            tech_stacks = TechStack.objects.filter(account_id=account_id)
            
            # Group signals by tech stack
            result = {}
            for tech_stack in tech_stacks:
                tech_signals = queryset.filter(tech_stack=tech_stack)
                if tech_signals.exists():
                    tech_data = {
                        'tech_id': tech_stack.id,
                        'tech_name': tech_stack.tech_name,
                        'signals': {}
                    }
                    
                    # Group by field name within each tech stack
                    for field in [Signal.Field.PURPOSE, Signal.Field.PROS, 
                                  Signal.Field.CONS, Signal.Field.ANNUAL_COSTS, 
                                  Signal.Field.RENEWAL_DATE, Signal.Field.START_YEAR_OF_USAGE]:
                        field_signals = tech_signals.filter(field_name=field)
                        if field_signals.exists():
                            serializer = self.serializer_class(field_signals, many=True)
                            tech_data['signals'][field] = serializer.data
                    
                    result[str(tech_stack.id)] = tech_data
            
            return Response(result)
            
        except Exception as e:
            return self.handle_exception(e)