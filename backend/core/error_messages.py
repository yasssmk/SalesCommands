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
    UNEXPECTED_ERROR = _("An unexpected error occurred: {detail}")
    INVALID_REQUEST = _("Invalid request format")
    OBJECT_IN_USE = _("Cannot delete {fields} as it is in use")

    # AI Service Related
    INVALID_CONFIG = _("AI service configuration is invalid")
    SERVICE_UNAVAILABLE = _("AI service is currently unavailable")
    SERVICE_AUTH_FAILED = _("AI service authentication failed")
    SERVICE_ERROR = _("AI service error occurred")
    PROCESSING_FAILED = _("Failed to process transcript")
    INVALID_OPERATION = _("{operation}")

    INVALID_DATE_RANGE= _("Invalid date range: {start_date} must be before {end_date}")

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


class CampaignErrorMessages:
    """Campaign specific error messages"""
    
    # Campaign State & Validation
    CAMPAIGN_ALREADY_STARTED = _("Campaign has already been started and cannot be modified")
    CAMPAIGN_NOT_STARTED = _("Campaign must be started before performing this action")
    CAMPAIGN_COMPLETED = _("Cannot modify a completed campaign")
    CAMPAIGN_INVALID_STATE = _("Campaign is in an invalid state for this operation: {current_state}")
    CAMPAIGN_TRANSITION_INVALID = _("Cannot transition from {from_state} to {to_state}")
    
    # Campaign Configuration
    CAMPAIGN_DATE_INVALID = _("Campaign end date must be after start date")
    CAMPAIGN_DATE_PAST = _("Campaign end date cannot be in the past")
    CAMPAIGN_NO_SEQUENCE_TYPE = _("Call list campaigns cannot have automated sequences")
    CAMPAIGN_SEQUENCE_REQUIRED = _("Campaign type {campaign_type} requires a sequence type")
    CAMPAIGN_TARGETS_REQUIRED = _("At least one target (account, contact, lead, or opportunity) is required")
    
    # Campaign Targets
    TARGET_ALREADY_EXISTS = _("This {target_type} is already a target for this campaign")
    TARGET_TYPE_CONFLICT = _("Only one target type can be specified per campaign target")
    TARGET_TYPE_REQUIRED = _("One target (account, contact, lead, or opportunity) must be specified")
    TARGET_NOT_FOUND_IN_CAMPAIGN = _("Target not found in this campaign")
    TARGET_INVALID_TYPE = _("Invalid target type: {target_type}")
    
    # Campaign Activities
    ACTIVITY_NOT_IN_CAMPAIGN = _("Activity does not belong to this campaign")
    ACTIVITY_INVALID_RESULT = _("Invalid activity result: {result}")
    ACTIVITY_ALREADY_COMPLETED = _("Activity is already completed")
    ACTIVITY_INVALID_STATE = _("Activity is in invalid state for this operation: {current_state}")
    ACTIVITY_SEQUENCE_BROKEN = _("Activity sequence is broken or corrupted")
    ACTIVITY_CALLBACK_DATE_REQUIRED = _("Callback date is required for callback results")
    ACTIVITY_MEETING_DATE_REQUIRED = _("Meeting date is required for successful results")
    ACTIVITY_GENERATION_FAILED = _("Failed to generate activities: {reason}")
    
    # Campaign Stakeholders
    STAKEHOLDER_ALREADY_EXISTS = _("User already has role {role} for this campaign")
    STAKEHOLDER_ROLE_REQUIRED = _("Stakeholder role is required")
    STAKEHOLDER_INVALID_ROLE = _("Invalid stakeholder role: {role}")
    STAKEHOLDER_CANNOT_REMOVE_OWNER = _("Cannot remove the campaign owner")
    STAKEHOLDER_PERMISSION_DENIED = _("You don't have permission to manage stakeholders for this campaign")
    
    # Campaign Objectives
    OBJECTIVE_TARGET_VALUE_INVALID = _("Target value must be greater than zero")
    OBJECTIVE_CURRENT_VALUE_INVALID = _("Current value cannot be negative")
    OBJECTIVE_TYPE_INVALID = _("Invalid objective type: {objective_type}")
    OBJECTIVE_PRIMARY_REQUIRED = _("At least one primary objective is required")
    OBJECTIVE_PRIMARY_CONFLICT = _("Only one primary objective allowed per campaign")
    
    # Campaign Execution
    CAMPAIGN_NO_READY_ACTIVITIES = _("No activities are ready for execution")
    CAMPAIGN_CONTACT_OPTED_OUT = _("Contact has opted out of communications")
    CAMPAIGN_CONTACT_NO_CHANNELS = _("Contact has no valid communication channels")
    CAMPAIGN_SEQUENCE_GENERATION_FAILED = _("Failed to generate sequence for contact: {reason}")
    
    # Campaign Permissions
    CAMPAIGN_OWNER_REQUIRED = _("You can only perform this action on your own campaigns")
    CAMPAIGN_STAKEHOLDER_REQUIRED = _("You must be a stakeholder of this campaign")
    CAMPAIGN_EXECUTOR_REQUIRED = _("You must be an executor to perform campaign activities")
    
    # Campaign Data Integrity
    CAMPAIGN_CONTACT_MAPPING_FAILED = _("Failed to map contact to campaign target")
    CAMPAIGN_ACTIVITY_ORPHANED = _("Activity exists without proper campaign relationship")
    CAMPAIGN_TARGET_ORPHANED = _("Campaign target exists without valid relationship")
    
    # Campaign Limits & Constraints  
    CAMPAIGN_MAX_TARGETS_EXCEEDED = _("Maximum number of targets exceeded: {max_targets}")
    CAMPAIGN_MAX_ACTIVITIES_EXCEEDED = _("Maximum number of activities exceeded: {max_activities}")
    CAMPAIGN_DUPLICATE_CONTACT = _("Contact is already targeted through another relationship")
    
    # Campaign Queue & Playlist
    PLAYLIST_EMPTY = _("No activities available in campaign playlist")
    PLAYLIST_BATCH_INVALID = _("Invalid activity type for batching: {activity_type}")
    QUEUE_OPTIMIZATION_FAILED = _("Failed to optimize campaign queue")
    
    # Campaign Results & Analytics
    RESULT_PROCESSING_FAILED = _("Failed to process activity result: {reason}")
    OBJECTIVE_UPDATE_FAILED = _("Failed to update campaign objective: {reason}")
    ANALYTICS_CALCULATION_FAILED = _("Failed to calculate campaign analytics")
    
    # Campaign Import/Export
    IMPORT_INVALID_FORMAT = _("Invalid import format for campaign data")
    EXPORT_GENERATION_FAILED = _("Failed to generate campaign export")
    BULK_OPERATION_FAILED = _("Bulk operation failed: {operation}")
    
    # Campaign Dependencies
    DEPENDENCY_VIOLATION = _("Cannot perform action due to dependency: {dependency}")
    RELATED_OBJECT_REQUIRED = _("Related object required: {object_type}")
    CASCADE_DELETE_BLOCKED = _("Cannot delete campaign with active dependencies")

    # Campaign Target Status Transitions
    TARGET_INVALID_STATE = _("Invalid target state: {state}")
    TARGET_TRANSITION_INVALID = _("Cannot transition from '{from_state}' to '{to_state}'. Allowed transitions: {allowed_transitions}")
    TARGET_FINAL_STATE_IMMUTABLE = _("Cannot modify target in final state '{state}'")
    TARGET_TRANSITION_MISSING_TRIGGER = _("Business trigger required for transition to '{to_state}'")
    TARGET_TRANSITION_INVALID_TRIGGER = _("Invalid trigger '{trigger}' for transition from '{from_state}' to '{to_state}'")
    TARGET_STATE_MACHINE_ERROR = _("State machine validation failed: {reason}")
    TARGET_STATUS_UPDATE_FAILED = _("Failed to update target status: {reason}")
    TARGET_STATUS_SYNC_FAILED = _("Failed to synchronize target status with activities: {reason}")