# apps/signals/serializers/signal_serializer_factory.py

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from .qualification_signal_serializer import QualificationSignalSerializer
from .tech_stack_signal_serializer import TechStackSignalSerializer
from .profile_signal_serializer import ProfileSignalSerializer
from ..models.qualification_signal_model import QualificationSignal
from ..models.tech_stack_signal_model import TechStackSignal
from ..models.profile_signal_model import ProfileSignal


class SignalSerializerFactory:
    """
    Factory class to select the appropriate serializer based on signal type or category.
    """
    
    # Mapping of models to their serializers
    _MODEL_SERIALIZER_MAP = {
        QualificationSignal: QualificationSignalSerializer,
        TechStackSignal: TechStackSignalSerializer,
        ProfileSignal: ProfileSignalSerializer,
    }
    
    # Mapping of category names to serializers
    _CATEGORY_SERIALIZER_MAP = {
        'QUALIFICATION': QualificationSignalSerializer,
        'TECH_STACK': TechStackSignalSerializer,
        'PROFILE': ProfileSignalSerializer,
    }
    
    @classmethod
    def get_serializer_for_instance(cls, instance):
        """
        Get the appropriate serializer for a signal instance.
        
        Args:
            instance: Signal instance
            
        Returns:
            Serializer class for the instance
        """
        for model_class, serializer_class in cls._MODEL_SERIALIZER_MAP.items():
            if isinstance(instance, model_class):
                return serializer_class
        
        raise StandardizedValidationError({
            'error': f"No serializer found for {instance.__class__.__name__}"
        })
    
    @classmethod
    def get_serializer_for_category(cls, category):
        """
        Get the appropriate serializer for a signal category.
        
        Args:
            category (str): Signal category name
            
        Returns:
            Serializer class for the category
        """
        if not category:
            raise StandardizedValidationError({
                'category': CoreErrorMessages.REQUIRED_FIELD
            })
            
        category = category.upper()
        serializer_class = cls._CATEGORY_SERIALIZER_MAP.get(category)
        
        if not serializer_class:
            valid_categories = ', '.join(cls._CATEGORY_SERIALIZER_MAP.keys())
            raise StandardizedValidationError({
                'category': f"Invalid category. Must be one of: {valid_categories}"
            })
            
        return serializer_class
    
    @classmethod
    def create_serializer(cls, data=None, instance=None, **kwargs):
        """
        Create an appropriate serializer instance based on data or object instance.
        
        Args:
            data (dict, optional): Data to serialize
            instance (object, optional): Instance to serialize
            **kwargs: Additional arguments to pass to the serializer
            
        Returns:
            Serializer instance
        """
        if instance:
            serializer_class = cls.get_serializer_for_instance(instance)
            return serializer_class(instance=instance, **kwargs)
        
        if data:
            category = data.get('category')
            serializer_class = cls.get_serializer_for_category(category)
            return serializer_class(data=data, **kwargs)
        
        raise StandardizedValidationError({
            'error': "Either data or instance must be provided"
        })