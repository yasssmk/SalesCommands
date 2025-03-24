# apps/core_apps/services/historical_tracking_service.py

from django.utils import timezone
import copy
import json
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from django.db import transaction

class HistoricalTrackingService:
    """Service for tracking historical data changes in models with JSONField support."""
    
    @staticmethod
    def update_field(instance, field_name, new_value, user=None, signal=None, update_model=True):
        """
        Update a field with a completely new value and track the change in historical data.
        Works with both regular fields and JSONFields.
        """
        try:
            # Get current value
            if not hasattr(instance, field_name):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field=field_name)
                )
                
            current_value = getattr(instance, field_name)
            
            # If no change, exit early
            if current_value == new_value:
                return False
            
            with transaction.atomic():
            # Update the field if requested
                if update_model:
                    setattr(instance, field_name, new_value)
                
                # Track the change
                result = HistoricalTrackingService._track_change(
                    instance, field_name, current_value, new_value, user, signal, update_model
                )
                
                if not result:
                    # If tracking failed, roll back transaction
                    transaction.set_rollback(True)
                    return False
                
                return True
        except StandardizedValidationError:
            raise
        except Exception as e:

            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
        
    @staticmethod
    def update_json_item(instance, field_name, item_id, new_item, id_key='id', user=None, signal=None):
        """
        Update a specific item in a JSONField that contains an array of objects
        """
        try:
            # Get the current JSON value
            if not hasattr(instance, field_name):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field=field_name)
                )
                
            current_json = getattr(instance, field_name) or []
            
            if not isinstance(current_json, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_OPERATION.format(
                        operation=f"Field {field_name} is not a list"
                    )
                )
            
            # Make a deep copy to avoid modifying the original
            with transaction.atomic():
                # Make a deep copy to avoid modifying the original
                new_json = copy.deepcopy(current_json)
                
                # Find the item by id
                item_found = False
                old_item = None
                
                for i, item in enumerate(new_json):
                    if not isinstance(item, dict):
                        continue
                        
                    if item.get(id_key) == item_id:
                        old_item = copy.deepcopy(item)
                        new_json[i] = new_item
                        item_found = True
                        break
                
                if not item_found:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND
                    )
                
                # Update the field
                setattr(instance, field_name, new_json)
                
                # Create a history entry for the change
                result = HistoricalTrackingService._track_json_change(
                    instance, field_name, old_item, new_item, user, signal, 
                    operation='update_item', item_id=item_id, id_key=id_key
                )
                
                if not result:
                    # If tracking failed, roll back transaction
                    transaction.set_rollback(True)
                    return False
                    
                return True
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
    
    @staticmethod
    def add_json_item(instance, field_name, new_item, user=None, signal=None):
        """
        Add an item to a JSONField that contains an array of objects
        """
        try:
            # Get the current JSON value
            if not hasattr(instance, field_name):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field=field_name)
                )
                
            current_json = getattr(instance, field_name) or []
            
            if not isinstance(current_json, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_OPERATION.format(
                        operation=f"Field {field_name} is not a list"
                    )
                )
            
            # Make a deep copy to avoid modifying the original
            new_json = copy.deepcopy(current_json)
            
            # Add the new item
            new_json.append(new_item)
            
            # Update the field
            setattr(instance, field_name, new_json)
            
            # Create a history entry for the addition
            return HistoricalTrackingService._track_json_change(
                instance, field_name, None, new_item, user, signal, 
                operation='add_item'
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR)
    
    @staticmethod
    def remove_json_item(instance, field_name, item_id, id_key='id', user=None, signal=None):
        """
        Remove an item from a JSONField that contains an array of objects
        """
        try:
            # Get the current JSON value
            if not hasattr(instance, field_name):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field=field_name)
                )
                
            current_json = getattr(instance, field_name) or []
            
            if not isinstance(current_json, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_OPERATION.format(
                        operation=f"Field {field_name} is not a list"
                    )
                )
            
            # Make a deep copy to avoid modifying the original
            new_json = copy.deepcopy(current_json)
            
            # Find the item by id
            item_found = False
            removed_item = None
            
            for i, item in enumerate(new_json):
                if not isinstance(item, dict):
                    continue
                    
                if item.get(id_key) == item_id:
                    removed_item = copy.deepcopy(item)
                    new_json.pop(i)
                    item_found = True
                    break
            
            if not item_found:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
            
            # Update the field
            setattr(instance, field_name, new_json)
            
            # Create a history entry for the removal
            return HistoricalTrackingService._track_json_change(
                instance, field_name, removed_item, None, user, signal, 
                operation='remove_item', item_id=item_id, id_key=id_key
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
    
    @staticmethod
    def _ensure_json_serializable(value):
        """
        Ensure a value is JSON serializable.
        Returns the original value if serializable, otherwise a string representation.
        """
        try:
            # Test JSON serialization
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            # If not serializable, convert to string representation
            if value is None:
                return None
            return str(value)

    @staticmethod
    def _track_change(instance, field_name, old_value, new_value, user, signal, save_model):
        """Internal method to track field changes with JSON serialization safety"""
        try:
            # Ensure values are JSON serializable
            safe_old_value = HistoricalTrackingService._ensure_json_serializable(old_value)
            safe_new_value = HistoricalTrackingService._ensure_json_serializable(new_value)
            
            # Create history entry
            history_entry = HistoricalTrackingService._create_history_entry(
                safe_old_value, safe_new_value, user, signal
            )
            
            # Add to history and save if needed
            result = HistoricalTrackingService._add_history_entry(instance, field_name, history_entry)
            
            if result and save_model:
                return HistoricalTrackingService._save_instance_with_user(instance, user)
            
            return result
        except StandardizedValidationError:
            # Re-raise standardized errors
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
        
    @staticmethod
    def _track_json_change(instance, field_name, old_value, new_value, user, signal, 
                           operation=None, item_id=None, id_key=None):
        """Internal method to track JSON field item changes"""
        try:
            # Create history entry
            history_entry = HistoricalTrackingService._create_history_entry(
                old_value, new_value, user, signal
            )
            
            # Add operation details
            if operation:
                history_entry['operation'] = operation
            if item_id is not None:
                history_entry['item_id'] = item_id
            if id_key:
                history_entry['id_key'] = id_key
            
            # Add to history and save
            result = HistoricalTrackingService._add_history_entry(instance, field_name, history_entry)
            
            if result:
                return HistoricalTrackingService._save_instance_with_user(instance, user)
            
            return result
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
    
    @staticmethod
    def _create_history_entry(old_value, new_value, user, signal):
        """Create a history entry dictionary with standardized user handling"""
        try:
            # Standardized way to get user ID
            user_id = None
            if user:
                try:
                    # If it's a User model instance
                    user_id = str(user.id)
                except (AttributeError, TypeError):
                    # If it's already an ID (string or numeric)
                    try:
                        user_id = str(user)
                    except Exception:
                        raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            history_entry = {
                'old_value': old_value,
                'new_value': new_value,
                'changed_at': timezone.now().isoformat(),
                'changed_by': user_id,
                'source': 'manual'
            }
            
            # Add signal data if provided
            if signal:
                try:
                    history_entry.update({
                        'source': 'signal',
                        'signal_id': str(signal.id),
                        'signal_category': getattr(signal, 'category', None),
                        'signal_confidence': getattr(signal, 'confidence', None),
                        'confirmation_count': getattr(signal, 'confirmation_count', None)
                    })
                except Exception as e:
                    raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(detail="Invalid signal data")
                )
            
            return history_entry
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
    
    @staticmethod
    def _add_history_entry(instance, field_name, history_entry):
        """Add a history entry to the instance's historical_data"""
        try:
            if not hasattr(instance, 'historical_data'):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_OPERATION.format(
                        operation="Instance does not support historical tracking"
                    )
                )
            
            # Initialize historical_data if it doesn't exist
            if instance.historical_data is None:
                instance.historical_data = {}
            
            # Initialize field history if it doesn't exist
            if field_name not in instance.historical_data:
                instance.historical_data[field_name] = []
            
            # Add to historical data
            instance.historical_data[field_name].append(history_entry)
            
            # Also track in signal_metadata if model supports it and entry is from a signal
            if history_entry.get('source') == 'signal' and hasattr(instance, 'track_signal_update'):
                signal_id = history_entry.get('signal_id')
                if signal_id:
                    try:
                        # Use lazy import to avoid circular import issues
                        from apps.sales_insight.models import Signal
                        
                        try:
                            signal = Signal.objects.get(id=signal_id)
                            instance.track_signal_update(
                                signal, 
                                field_name, 
                                history_entry.get('old_value'), 
                                history_entry.get('new_value')
                            )
                        except Signal.DoesNotExist:
                            # Use standardized error message
                            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                    except ImportError:
                        # Use standardized error message
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_OPERATION.format(
                                operation="Signal tracking service not available"
                            )
                        )
            
            return True
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
    
    @staticmethod
    def _save_instance_with_user(instance, user):
        """Standardized method to save instance with user if supported"""
        try:
            if not hasattr(instance, 'save'):
                return False
                
            # Check if save method accepts a user parameter
            save_params = instance.save.__code__.co_varnames
            
            if 'user' in save_params:
                # If the save method accepts a user parameter, use it
                instance.save(user=user)
            else:
                # Otherwise, use the standard save method
                instance.save()
                
            return True
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))