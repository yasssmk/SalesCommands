# apps/signals/validators.py

from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

class FieldValidators:
    """Registry of validators for different signal fields."""
    
    @staticmethod
    def validate_list_items(value, item_schema=None):
        """
        Validate that a value is a list and optionally validate its items.
        
        Args:
            value: Value to validate
            item_schema: Optional schema for validating individual items
            
        Returns:
            bool: True if valid
            
        Raises:
            StandardizedValidationError: If invalid
        """
        if not isinstance(value, list):
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_DATA: {"detail": "Value must be a list"}
            })
        
        if item_schema:
            for i, item in enumerate(value):
                try:
                    FieldValidators._validate_item_schema(item, item_schema)
                except StandardizedValidationError as e:
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            "detail": f"Item at index {i} is invalid: {e.detail['error']}"
                        }
                    })
        
        return True
    
    @staticmethod
    def _validate_item_schema(item, schema):
        """Validate an item against a schema."""
        if not isinstance(item, dict):
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_DATA: {"detail": "Item must be an object"}
            })
        
        # Check required fields
        for field in schema.get('required', []):
            if field not in item or item[field] is None:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_DATA: {
                        "detail": f"Required field '{field}' is missing"
                    }
                })
        
        # Validate field types and constraints
        for field_name, field_spec in schema.get('properties', {}).items():
            if field_name in item:
                field_type = field_spec.get('type')
                
                # Type validation
                if field_type == 'string' and not isinstance(item[field_name], str):
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            "detail": f"Field '{field_name}' must be a string"
                        }
                    })
                    
                elif field_type == 'number' and not isinstance(item[field_name], (int, float)):
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            "detail": f"Field '{field_name}' must be a number"
                        }
                    })
                    
                elif field_type == 'boolean' and not isinstance(item[field_name], bool):
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            "detail": f"Field '{field_name}' must be a boolean"
                        }
                    })
                    
                # Length validation for strings
                if field_type == 'string' and 'maxLength' in field_spec:
                    if len(item[field_name]) > field_spec['maxLength']:
                        raise StandardizedValidationError({
                            CoreErrorMessages.INVALID_DATA: {
                                "detail": f"Field '{field_name}' exceeds maximum length of {field_spec['maxLength']}"
                            }
                        })
                
                # Min/max validation for numbers
                if field_type == 'number':
                    if 'minimum' in field_spec and item[field_name] < field_spec['minimum']:
                        raise StandardizedValidationError({
                            CoreErrorMessages.INVALID_DATA: {
                                "detail": f"Field '{field_name}' must be at least {field_spec['minimum']}"
                            }
                        })
                        
                    if 'maximum' in field_spec and item[field_name] > field_spec['maximum']:
                        raise StandardizedValidationError({
                            CoreErrorMessages.INVALID_DATA: {
                                "detail": f"Field '{field_name}' must be at most {field_spec['maximum']}"
                            }
                        })
        
        return True
    
    # List item schemas for different field types
    OBJECTIVE_SCHEMA = {
        'properties': {
            'id': {'type': 'string'},
            'objective': {'type': 'string', 'maxLength': 500},
        },
        'required': ['id', 'objective']
    }
    
    PAIN_POINT_SCHEMA = {
        'properties': {
            'id': {'type': 'string'},
            'pain_point': {'type': 'string', 'maxLength': 500},
        },
        'required': ['id', 'pain_point']
    }
    
    METRIC_SCHEMA = {
        'properties': {
            'id': {'type': 'string'},
            'metric': {'type': 'string', 'maxLength': 500},
            'target': {'type': 'string', 'maxLength': 100},
            'current': {'type': 'string', 'maxLength': 100}
        },
        'required': ['id', 'metric']
    }
    
    TECH_COST_SCHEMA = {
        'properties': {
            'type': {'type': 'string', 'maxLength': 100},
            'amount': {'type': 'number', 'minimum': 0},
            'currency': {'type': 'string', 'maxLength': 3},
            'period': {'type': 'string', 'maxLength': 50}
        },
        'required': ['type']
    }
    
    # Validator methods for specific field types
    @classmethod
    def validate_objectives(cls, value):
        """Validate objectives list format."""
        return cls.validate_list_items(value, cls.OBJECTIVE_SCHEMA)
    
    @classmethod
    def validate_pain_points(cls, value):
        """Validate pain points list format."""
        return cls.validate_list_items(value, cls.PAIN_POINT_SCHEMA)
    
    @classmethod
    def validate_metrics(cls, value):
        """Validate metrics list format."""
        return cls.validate_list_items(value, cls.METRIC_SCHEMA)
    
    @classmethod
    def validate_annual_costs(cls, value):
        """Validate annual costs list format."""
        return cls.validate_list_items(value, cls.TECH_COST_SCHEMA)
    
    @classmethod
    def validate_start_year(cls, value):
        """Validate start year."""
        try:
            year = int(value)
            if year < 1900 or year > 2100:
                raise ValueError("Year out of reasonable range")
            return True
        except (ValueError, TypeError):
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_DATA: {"detail": "Value must be a valid year"}
            })