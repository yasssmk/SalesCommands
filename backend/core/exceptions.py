# core/exceptions.py
from rest_framework.exceptions import ValidationError, PermissionDenied, AuthenticationFailed, ErrorDetail
from django.core.exceptions import ValidationError as DjangoValidationError
from core.error_messages import CoreErrorMessages
from rest_framework.exceptions import ParseError
from rest_framework.exceptions import Throttled


#TO DO: GESTION DES ERREUR 500

class StandardizedValidationError(ValidationError):
    """Returns 400 Bad Request with a clean error message"""

    def __init__(self, detail=None):
        formatted_detail = self._format_detail(detail)
        super().__init__(formatted_detail)

    @staticmethod
    def _format_detail(detail):
        """Format the detail into our standard error structure"""
        if detail is None:
            return {"error": "An unexpected error occurred"}
        
        if isinstance(detail, ParseError):
            return {"error": detail}

        # For ErrorDetail objects
        if isinstance(detail, str):
            # ✅ Handle empty strings
            if not detail.strip():
                return {"error": "An unexpected error occurred"}
            return {"error": detail}

        # If it's already a proper error format, return as is
        if isinstance(detail, dict):
            if "error" in detail:
                return detail
            
            if "detail" in detail and len(detail) == 1:
                detail_value = detail["detail"]
                # Si c'est une string simple, extraire directement
                if isinstance(detail_value, (str, ErrorDetail)):
                    return {"error": str(detail_value)}
                # Si c'est un dict avec "error", le retourner tel quel
                if isinstance(detail_value, dict) and "error" in detail_value:
                    return detail_value
                # Sinon, récurser pour traiter la structure
                return StandardizedValidationError._format_detail(detail_value)
            
            # For field-specific errors
            messages = []
            for field, error in detail.items():
                # Skip the "detail" key if we already handled it above
                if field == "detail" and len(detail) == 1:
                    continue
                    
                # Handle list/tuple of errors for a field
                if isinstance(error, (list, tuple)):
                    error = error[0] if error else ''
                elif isinstance(error, dict):
                    # Handle nested error structures
                    sub_detail = StandardizedValidationError._format_detail(error)
                    error = sub_detail.get("error", "")
                
                # Build field-specific message
                if error:
                    messages.append(f"{field}: {str(error)}")
            
            # ✅ FIX: Handle empty dict or dict that produced no messages
            if messages:
                return {"error": " ".join(messages)}
            else:
                return {"error": "Invalid request data"}

        # For list/tuple of errors - take only the first error
        if isinstance(detail, (list, tuple)):
            if not detail:  # ✅ FIX: Handle empty list
                return {"error": "An unexpected error occurred"}
            
            # If first item is already a dict with error key, use it
            if isinstance(detail[0], dict) and "error" in detail[0]:
                return detail[0]
            # Otherwise format the first item
            return StandardizedValidationError._format_detail(detail[0])

        # For any other case, convert to string
        return {"error": str(detail) if detail else "An unexpected error occurred"}


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
        # ✅ FIX: Improved response data normalization
        
        # Case 1: Response is a list (rare, but happens)
        if isinstance(response.data, list):
            if response.data:  # If list is not empty
                response.data = StandardizedValidationError._format_detail(response.data[0])
            else:
                response.data = {"error": CoreErrorMessages.UNEXPECTED_ERROR}
        
        # Case 2: Response is not a dict (very rare)
        elif not isinstance(response.data, dict):
            response.data = StandardizedValidationError._format_detail(response.data)
        
        # Case 3: Response is a dict - check if it needs normalization
        elif isinstance(response.data, dict):
            # If it already has "error" key, it's in our format - leave it
            if "error" not in response.data:
                # Otherwise, normalize it (handles {"detail": ...} and other formats)
                response.data = StandardizedValidationError._format_detail(response.data)
    
    return response