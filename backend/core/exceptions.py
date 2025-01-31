# core/exceptions.py
from rest_framework.exceptions import ValidationError, PermissionDenied, AuthenticationFailed, ErrorDetail
from django.core.exceptions import ValidationError as DjangoValidationError
from core.error_messages import CoreErrorMessages

class StandardizedValidationError(ValidationError):
    """Returns 400 Bad Request with a clean error message"""

    def __init__(self, detail=None):
        """
        Initialize with properly formatted error detail.
        Ensures a single level of error wrapping.
        """
        formatted_detail = self._format_detail(detail)
        super().__init__(formatted_detail)

    @staticmethod
    def _format_detail(detail):
        """Format the detail into our standard error structure"""
        if detail is None:
            return {"error": CoreErrorMessages.UNEXPECTED_ERROR}
            
        # If it's already a proper error format, return as is
        if isinstance(detail, dict) and len(detail) == 1 and "error" in detail:
            return detail
            
        # If it's an ErrorDetail object, extract its string value
        if isinstance(detail, ErrorDetail):
            return {"error": str(detail)}
            
        # If it's a string, wrap it
        if isinstance(detail, str):
            return {"error": detail}
            
        # If it's a list/tuple with a single item, process that item
        if isinstance(detail, (list, tuple)) and len(detail) == 1:
            return StandardizedValidationError._format_detail(detail[0])
            
        # If it's a dictionary
        if isinstance(detail, dict):
            # If there's only one key-value pair
            if len(detail) == 1:
                key, value = next(iter(detail.items()))
                # If the value is a list with one item that's an ErrorDetail
                if isinstance(value, (list, tuple)) and len(value) == 1 and isinstance(value[0], ErrorDetail):
                    return {"error": str(value[0])}
                # If the value is an ErrorDetail
                if isinstance(value, ErrorDetail):
                    return {"error": str(value)}
            
            # For multiple field errors
            error_messages = []
            for key, value in detail.items():
                if isinstance(value, (list, tuple)) and value:
                    error_messages.append(f"{key}: {str(value[0])}")
                else:
                    error_messages.append(f"{key}: {str(value)}")
            return {"error": " ".join(error_messages)}
            
        # For any other case, convert to string
        return {"error": str(detail)}

    # Add alias for backward compatibility if needed
    _extract_error_message = _format_detail


class StandardizedPermissionDenied(PermissionDenied):
    """Returns 403 Forbidden with a clean error message"""

    def __init__(self, detail=None):
        formatted_detail = StandardizedValidationError._format_detail(detail)
        super().__init__(formatted_detail)


class StandardizedAuthenticationFailed(AuthenticationFailed):
    """Returns 401 Unauthorized with a clean error message"""

    def __init__(self, detail=None):
        formatted_detail = StandardizedValidationError._format_detail(detail)
        super().__init__(formatted_detail)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that ensures consistent error format
    """
    from rest_framework.views import exception_handler
    
    # Convert Django validation errors
    if isinstance(exc, DjangoValidationError):
        exc = StandardizedValidationError(exc.message_dict)
        
    # Get DRF's standard error response
    response = exception_handler(exc, context)
    
    if response is not None:
        # Ensure consistent error format
        response.data = StandardizedValidationError._format_detail(response.data)
        
    return response