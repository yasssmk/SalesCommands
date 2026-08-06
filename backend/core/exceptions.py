# core/exceptions.py
import logging

from rest_framework.exceptions import ValidationError, PermissionDenied, AuthenticationFailed, ErrorDetail
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from core.error_messages import CoreErrorMessages
from rest_framework.exceptions import ParseError
from rest_framework.exceptions import Throttled

logger = logging.getLogger(__name__)


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
            
        #     # For field-specific errors
        #     messages = []
        #     for field, error in detail.items():
        #         # Skip the "detail" key if we already handled it above
        #         if field == "detail" and len(detail) == 1:
        #             continue
                    
        #         # Handle list/tuple of errors for a field
        #         if isinstance(error, (list, tuple)):
        #             error = error[0] if error else ''
        #         elif isinstance(error, dict):
        #             # Handle nested error structures
        #             sub_detail = StandardizedValidationError._format_detail(error)
        #             error = sub_detail.get("error", "")
                
        #         # Build field-specific message
        #         if error:
        #             # messages.append(f"{field}: {str(error)}")
        #             messages.append(f"{str(error)}")
            
        #     # ✅ FIX: Handle empty dict or dict that produced no messages
        #     if messages:
        #         return {"error": " ".join(messages)}
        #     else:
        #         return {"error": "Invalid request data"}

        # # For list/tuple of errors - take only the first error
        # if isinstance(detail, (list, tuple)):
        #     if not detail:  # ✅ FIX: Handle empty list
        #         return {"error": "An unexpected error occurred"}
            
        #     # If first item is already a dict with error key, use it
        #     if isinstance(detail[0], dict) and "error" in detail[0]:
        #         return detail[0]
        #     # Otherwise format the first item
        #     return StandardizedValidationError._format_detail(detail[0])

        # # For any other case, convert to string
        # return {"error": str(detail) if detail else "An unexpected error occurred"}
            is_field_validation = True
            field_errors = {}
            
            for field, error in detail.items():
                # Skip special keys that indicate this is NOT field validation
                if field in ["detail", "error", "message", "non_field_errors"]:
                    is_field_validation = False
                    break
                
                # Extract error message
                if isinstance(error, (list, tuple)) and error:
                    # Take first error if multiple
                    error_msg = str(error[0])
                elif isinstance(error, dict):
                    # Handle nested error structures
                    sub_detail = StandardizedValidationError._format_detail(error)
                    error_msg = sub_detail.get("error", "")
                else:
                    error_msg = str(error) if error else ""
                
                if error_msg:
                    field_errors[field] = [error_msg]  # Keep as array for consistency
            
            # ✅ If this looks like field validation, preserve the structure
            if is_field_validation and field_errors:
                return field_errors  # Return {email: ["error"], role: ["error"]}
            
            # ✅ Otherwise, concatenate into generic error message
            # This handles non-field errors like {"non_field_errors": ["error"]}
            messages = []
            for field, error in detail.items():
                if field == "detail" and len(detail) == 1:
                    continue
                    
                if isinstance(error, (list, tuple)):
                    error = error[0] if error else ''
                elif isinstance(error, dict):
                    sub_detail = StandardizedValidationError._format_detail(error)
                    error = sub_detail.get("error", "")
                
                if error:
                    messages.append(f"{str(error)}")
            
            if messages:
                return {"error": " ".join(messages)}
            else:
                return {"error": "Invalid request data"}

        # For list/tuple of errors - take only the first error
        if isinstance(detail, (list, tuple)):
            if not detail:
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

    # Database integrity violations (unique / foreign-key / not-null) are not
    # recognised by DRF's exception_handler and would otherwise bubble up as a
    # raw HTTP 500 leaking the offending SQL constraint. Convert them to the
    # project's standard error envelope with a generic, non-technical message
    # and a 409 Conflict status. The full technical error is logged server-side
    # so debugging is unaffected.
    if isinstance(exc, IntegrityError):
        logger.error(
            "integrity_error",
            extra={'error': str(exc)},
            exc_info=True,
        )
        return Response(
            StandardizedValidationError._format_detail(
                CoreErrorMessages.DATA_INTEGRITY_CONFLICT
            ),
            status=status.HTTP_409_CONFLICT,
        )

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