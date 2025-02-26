# core/exceptions.py
from rest_framework.exceptions import ValidationError, PermissionDenied, AuthenticationFailed, ErrorDetail
from django.core.exceptions import ValidationError as DjangoValidationError
from core.error_messages import CoreErrorMessages

class StandardizedValidationError(ValidationError):
    """Returns 400 Bad Request with a clean error message"""

    def __init__(self, detail=None):
        formatted_detail = self._format_detail(detail)
        super().__init__(formatted_detail)

    @staticmethod
    def _format_detail(detail):
        """Format the detail into our standard error structure"""
        if detail is None:
            return {"error": CoreErrorMessages.UNEXPECTED_ERROR}

        # For direct string messages
        if isinstance(detail, str):
            return {"error": detail}

        # For ErrorDetail objects
        if isinstance(detail, ErrorDetail):
            return {"error": str(detail)}

        # If it's already a proper error format, return as is
        if isinstance(detail, dict):
            if "error" in detail:
                return detail
            
            # For field-specific errors
            messages = []
            for field, error in detail.items():
                # Handle list/tuple of errors for a field
                if isinstance(error, (list, tuple)):
                    error = error[0] if error else ''
                elif isinstance(error, dict):
                    # Handle nested error structures
                    sub_detail = StandardizedValidationError._format_detail(error)
                    error = sub_detail.get("error", "")
                messages.append(f"{field}: {str(error)}")
            return {"error": " ".join(msg for msg in messages if msg)}

        # For list/tuple of errors - take only the first error
        if isinstance(detail, (list, tuple)) and detail:
            # If first item is already a dict with error key, use it
            if isinstance(detail[0], dict) and "error" in detail[0]:
                return detail[0]
            # Otherwise format the first item
            return StandardizedValidationError._format_detail(detail[0])

        # For any other case, convert to string
        return {"error": str(detail)}

    # Alias for backward compatibility
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
        # Handle potential list responses
        if isinstance(response.data, list):
            if response.data:  # If list is not empty
                response.data = StandardizedValidationError._format_detail(response.data[0])
            else:
                response.data = {"error": CoreErrorMessages.UNEXPECTED_ERROR}
        elif not isinstance(response.data, dict) or "error" not in response.data:
            response.data = StandardizedValidationError._format_detail(response.data)
    
    return response