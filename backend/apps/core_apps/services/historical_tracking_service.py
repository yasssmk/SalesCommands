# apps/core_apps/services/historical_tracking_service.py

from django.utils import timezone
import copy
import json


class HistoricalTrackingService:
    """Service for tracking historical data changes in models with JSONField support."""
    
    @staticmethod
    def update_field(instance, field_name, new_value, user=None, signal=None, update_model=True):
        """
        Update a field with a completely new value and track the change in historical data.
        Works with both regular fields and JSONFields.
        
        Args:
            instance: Model instance to update
            field_name (str): Field name to update
            new_value: New value for the field
            user (User, optional): User making the update
            signal (Signal, optional): Signal driving this update
            update_model (bool): Whether to update the model instance
        
        Returns:
            bool: Success status
        """
        # Get current value
        current_value = getattr(instance, field_name)
        
        # If no change, exit early
        if current_value == new_value:
            return False
        
        # Update the field if requested
        if update_model:
            setattr(instance, field_name, new_value)
        
        # Track the change
        return HistoricalTrackingService._track_change(
            instance, field_name, current_value, new_value, user, signal, update_model
        )
    
    @staticmethod
    def update_json_item(instance, field_name, item_id, new_item, id_key='id', user=None, signal=None):
        """
        Update a specific item in a JSONField that contains an array of objects
        
        Args:
            instance: Model instance to update
            field_name (str): JSONField name (e.g., 'pain_points', 'objectives')
            item_id: Value of the id_key to find the item to update
            new_item: New value for the item
            id_key (str): Key in the JSON objects used as identifier (default: 'id')
            user (User, optional): User making the update
            signal (Signal, optional): Signal driving this update
        
        Returns:
            bool: Success status
        """
        # Get the current JSON value
        current_json = getattr(instance, field_name) or []
        
        # Make a deep copy to avoid modifying the original
        new_json = copy.deepcopy(current_json)
        
        # Find the item by id
        item_found = False
        old_item = None
        
        for i, item in enumerate(new_json):
            if item.get(id_key) == item_id:
                old_item = copy.deepcopy(item)
                new_json[i] = new_item
                item_found = True
                break
        
        if not item_found:
            return False
        
        # Update the field
        setattr(instance, field_name, new_json)
        
        # Create a history entry for the change
        return HistoricalTrackingService._track_json_change(
            instance, field_name, old_item, new_item, user, signal, 
            operation='update_item', item_id=item_id, id_key=id_key
        )
    
    @staticmethod
    def add_json_item(instance, field_name, new_item, user=None, signal=None):
        """
        Add an item to a JSONField that contains an array of objects
        
        Args:
            instance: Model instance to update
            field_name (str): JSONField name (e.g., 'pain_points', 'objectives')
            new_item: Item to add to the JSON array
            user (User, optional): User making the update
            signal (Signal, optional): Signal driving this update
        
        Returns:
            bool: Success status
        """
        # Get the current JSON value
        current_json = getattr(instance, field_name) or []
        
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
    
    @staticmethod
    def remove_json_item(instance, field_name, item_id, id_key='id', user=None, signal=None):
        """
        Remove an item from a JSONField that contains an array of objects
        
        Args:
            instance: Model instance to update
            field_name (str): JSONField name (e.g., 'pain_points', 'objectives')
            item_id: Value of the id_key for the item to remove
            id_key (str): Key in the JSON objects used as identifier (default: 'id')
            user (User, optional): User making the update
            signal (Signal, optional): Signal driving this update
        
        Returns:
            bool: Success status
        """
        # Get the current JSON value
        current_json = getattr(instance, field_name) or []
        
        # Make a deep copy to avoid modifying the original
        new_json = copy.deepcopy(current_json)
        
        # Find the item by id
        item_found = False
        removed_item = None
        
        for i, item in enumerate(new_json):
            if item.get(id_key) == item_id:
                removed_item = copy.deepcopy(item)
                new_json.pop(i)
                item_found = True
                break
        
        if not item_found:
            return False
        
        # Update the field
        setattr(instance, field_name, new_json)
        
        # Create a history entry for the removal
        return HistoricalTrackingService._track_json_change(
            instance, field_name, removed_item, None, user, signal, 
            operation='remove_item', item_id=item_id, id_key=id_key
        )
    
    @staticmethod
    def _track_change(instance, field_name, old_value, new_value, user, signal, save_model):
        """Internal method to track field changes"""
        # Create history entry
        history_entry = HistoricalTrackingService._create_history_entry(
            old_value, new_value, user, signal
        )
        
        # Add to history and save if needed
        result = HistoricalTrackingService._add_history_entry(instance, field_name, history_entry)
        
        if result and save_model:
            if hasattr(instance, 'save'):
                kwargs = {'user': user} if 'user' in instance.save.__code__.co_varnames else {}
                instance.save(**kwargs)
        
        return result
    
    @staticmethod
    def _track_json_change(instance, field_name, old_value, new_value, user, signal, 
                           operation=None, item_id=None, id_key=None):
        """Internal method to track JSON field item changes"""
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
            if hasattr(instance, 'save'):
                kwargs = {'user': user} if 'user' in instance.save.__code__.co_varnames else {}
                instance.save(**kwargs)
        
        return result
    
    @staticmethod
    def _create_history_entry(old_value, new_value, user, signal):
        """Create a history entry dictionary"""
        history_entry = {
            'old_value': old_value,
            'new_value': new_value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None,
            'source': 'manual'
        }
        
        # Add signal data if provided
        if signal:
            history_entry.update({
                'source': 'signal',
                'signal_id': str(signal.id),
                'signal_category': signal.category,
                'signal_confidence': getattr(signal, 'confidence', None),
                'confirmation_count': getattr(signal, 'confirmation_count', None)
            })
        
        return history_entry
    
    @staticmethod
    def _add_history_entry(instance, field_name, history_entry):
        """Add a history entry to the instance's historical_data"""
        if hasattr(instance, 'historical_data'):
            # Initialize historical_data if it doesn't exist
            if not instance.historical_data:
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
                        pass
            
            return True
            
        return False