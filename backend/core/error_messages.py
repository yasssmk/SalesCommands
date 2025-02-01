# core/error_messages.py
from django.utils.translation import gettext_lazy as _

class CoreErrorMessages:
    """Base error messages used across all apps"""
    
    # Authentication & Authorization
    AUTH_REQUIRED = _("Authentication required")
    CLIENT_ID_REQUIRED = _("Client account required")
    PERMISSION_DENIED = _("You don't have permission to perform this action")
    
    # Client Scope
    CLIENT_MISMATCH = _("Object does not belong to your organization")
    CLIENT_SCOPE_UNSUPPORTED = _("Object does not support client scoping")
    CLIENT_ID_IMMUTABLE = _("client_id cannot be modified after creation")
    CLIENT_ID_REQUIRED = _("client_id is required when creating a new record")
    
    # Object Operations
    OBJECT_NOT_FOUND = _("Object not found or access denied")
    INVALID_DATA = _("Invalid data provided: {detail}")
    BATCH_UPDATE_MISSING_ID = _("All items in batch update must have an ID")
    NO_OBJECTS_FOUND = _("No objects were found to process")
    MASS_UPDATE_INVALID = _("No valid fields provided for update")
    
    # Field Validation
    REQUIRED_FIELD = _("{field} is required")
    INVALID_FIELD = _("Invalid value: {field}")
    FIELD_IMMUTABLE = _("{field} cannot be modified after creation")
    
    # Uniqueness
    UNIQUE_CONSTRAINT = _("An entry with this {fields} already exists in your organization")
    
    # Filtering
    INVALID_FILTER = _("Invalid filter format provided {detail}")
    
    # Generic
    UNEXPECTED_ERROR = _("An unexpected error occurred")
    INVALID_REQUEST = _("Invalid request format")

class AccountErrorMessages:
    """Account specific error messages"""
    INVALID_PARENT = _("Invalid parent assignment")
    PARENT_NOT_FOUND = _("Parent not found")
    INVALID_PARENT_ORG = _("Invalid relationship : {detail}")
    SELF_PARENT = _("Cannot be its own parent")
    CIRCULAR_HIERARCHY = _("Cannot create a circular parent-child relationship")
    TEAM_MISMATCH = _("Account manager must belong to the assigned team")
    USER_INACTIVE = _("Selected user is not active")
    INVALID_USER = _("Invalid user ID")
    EMPLOYEE_COUNT = _("Employee count cannot be negative")
    CHANGE_ACCOUNT_ORG = _("Cannot change the account of an existing organization unit")

class ContactErrorMessages:
    """Contact specific error messages"""
    DUPLICATE_EMAIL = _("A contact with this email already exists")
    DUPLICATE_PHONE = _("A contact with this phone number already exists")
    INVALID_ACCOUNT = _("Invalid or inaccessible account assigned")
    ACCOUNT_REQUIRED = _("Account association is required")

class ValidationErrorMessages:
    """Validation specific error messages"""
    INVALID_UUID = _("Invalid UUID format")
    INVALID_PHONE = _("Invalid phone number format")
    INVALID_URL = _("Invalid URL format")
    DATE_RANGE_INVALID = _("End date must be after start date")
    MAX_LENGTH = _("{field} exceeds maximum length of {max_length} characters")
    MIN_LENGTH = _("{field} must be at least {min_length} characters")