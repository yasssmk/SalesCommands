# apps/core_apps/models/historical_tracking.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class HistoricalTrackingModel(models.Model):
    """
    Model mixin that provides historical data tracking functionality.
    """
    historical_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Historical Data')
    )
    
    class Meta:
        abstract = True
    
    def track_field_change(self, field_name, old_value, new_value, user=None):
        """
        Track changes to any field in historical data
        
        Args:
            field_name (str): Field name that changed
            old_value: Previous value
            new_value: New value
            user (User, optional): User who made the change
        """
        from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
        
        tracked = HistoricalTrackingService._track_change(
        instance=self,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        user=user,
        signal=None,
        save_model=False  # Don't automatically save the model
        )
        
        # Initialize historical_data if it doesn't exist
        if self.historical_data is None:
            self.historical_data = {}
        
        # Ensure changes are saved (the service might not save the instance)
        return tracked
    
    def update_tracked_field(self, field_name, new_value, user=None):
        """
        Update a field and track the change
        
        Args:
            field_name (str): Field name to update
            new_value: New value for the field
            user (User, optional): User making the change
            
        Returns:
            bool: Whether the update was successful
        """
        from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
        
        return HistoricalTrackingService.update_field(
            instance=self,
            field_name=field_name,
            new_value=new_value,
            user=user
        )
    
    def update_tracked_json_item(self, field_name, item_id, new_item, id_key='id', user=None):
        """
        Update a single item in a JSONField array
        
        Args:
            field_name (str): JSONField name
            item_id: ID of the item to update
            new_item: New value for the item
            id_key (str): Key used as identifier in the JSON objects
            user (User, optional): User making the change
            
        Returns:
            bool: Whether the update was successful
        """
        from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
        
        return HistoricalTrackingService.update_json_item(
            instance=self,
            field_name=field_name,
            item_id=item_id,
            new_item=new_item,
            id_key=id_key,
            user=user
        )
    
    def add_tracked_json_item(self, field_name, new_item, user=None):
        """
        Add an item to a JSONField array
        
        Args:
            field_name (str): JSONField name
            new_item: Item to add
            user (User, optional): User making the change
            
        Returns:
            bool: Whether the addition was successful
        """
        from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
        
        return HistoricalTrackingService.add_json_item(
            instance=self,
            field_name=field_name,
            new_item=new_item,
            user=user
        )
    
    def remove_tracked_json_item(self, field_name, item_id, id_key='id', user=None):
        """
        Remove an item from a JSONField array
        
        Args:
            field_name (str): JSONField name
            item_id: ID of the item to remove
            id_key (str): Key used as identifier in the JSON objects
            user (User, optional): User making the change
            
        Returns:
            bool: Whether the removal was successful
        """
        from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
        
        return HistoricalTrackingService.remove_json_item(
            instance=self,
            field_name=field_name,
            item_id=item_id,
            id_key=id_key,
            user=user
        )