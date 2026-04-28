# core/error_messages.py
from django.utils.translation import gettext_lazy as _

class AuthErrorMessages:
    AUTH_REQUIRED = _("Authentication required")
    INVALID_CREDENTIALS = _("Authentication failed")
    USER_NOT_FOUND = _("No account found with this email address")
    INVALID_PASSWORD = _("The password you entered is incorrect")
    ACCOUNT_DISABLED = _("This account has been disabled")
    LOGIN_FAILED = _("Login failed. Please check your credentials and try again")
    TOKEN_EXPIRED = _("Your session has expired. Please log in again")
    TOKEN_INVALID = _("Invalid authentication token")

class UsersErrorMessages:
    USER_NOT_FOUND = _("User does not exist")

class TeamErrorMessages:
    MANAGER_HAS_TEAM = _("This user already manage team: {fields}")

class CoreErrorMessages:
    """Base error messages used across all apps"""
    
    # Authentication & Authorization
    AUTH_REQUIRED = _("Authentication required33")
    CLIENT_ID_REQUIRED = _("Client account required")
    PERMISSION_DENIED = _("You don't have permission to perform this action")

    # Admin / User invariants
    LAST_ADMIN_REQUIRED      = _("There must be at least one admin user in the organization")
    LAST_ADMIN_ROLE_LOCKED   = _("You cannot change the role or deactivate the last admin user")

    # Seats / Licensing
    SEAT_LIMIT_REACHED       = _("Active users seat limit reached. Deactivate another user before activating this one")

    # (Optionnel mais recommandé pour uniformiser un message déjà présent)
    SELF_DELETE_FORBIDDEN    = _("You cannot delete your own account")
    
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
    INVALID_REQUEST = _("Invalid request format: {reason}")
    OBJECT_IN_USE = _("Cannot delete {fields} as it is in use")
    CANNOT_DELETE = _("Cannot delete {fields}")

    # AI Service Related
    INVALID_CONFIG = _("AI service configuration is invalid")
    SERVICE_UNAVAILABLE = _("AI service is currently unavailable")
    SERVICE_AUTH_FAILED = _("AI service authentication failed")
    SERVICE_ERROR = _("AI service error occurred")
    PROCESSING_FAILED = _("Failed to process transcript")
    INVALID_OPERATION = _("{operation}")

    INVALID_DATE_RANGE= _("Invalid date range: {start_date} must be before {end_date}")

    # ====== Bulk Error Message ======

    # Bulk Operations
    BULK_NO_DATA = _("No {entity} data provided for bulk operation")
    BULK_INVALID_FORMAT = _("Bulk data must be a list of {entity}")
    BULK_SIZE_EXCEEDED = _("Maximum {max_size} {entity} allowed per bulk operation")
    BULK_DUPLICATE_IN_REQUEST = _("Duplicate {field} in request: '{value}' appears multiple times")
    BULK_PARTIAL_SUCCESS = _("{success_count} succeeded, {failed_count} failed")
    BULK_ALL_FAILED = _("All {entity} failed to {operation}")
    BULK_MODE_INVALID = _("Bulk mode must be 'partial' or 'strict'")
    BULK_STRICT_MODE_FAILED = _("Bulk operation failed in strict mode: {error_count} errors found")
    
    # Bulk Create specific
    BULK_CREATE_DUPLICATE_EMAIL = _(" A user with this email already exists")
    BULK_CREATE_INVALID_ROLE = _("Role '{role}' not found in your organization")
    BULK_CREATE_INVALID_TEAM = _("Team '{team}' not found or doesn't belong to organization '{org}'")
    BULK_CREATE_PASSWORD_REQUIRED = _("Password is required for new users")
    
    # Bulk Update specific  
    BULK_UPDATE_NO_ID = _("ID is required for bulk update")
    BULK_UPDATE_INVALID_ID = _("Object not found")
    BULK_UPDATE_NO_FIELDS = _("No valid fields provided for update")
    BULK_UPDATE_RESTRICTED_FIELD = _("Field '{field}' cannot be updated in bulk operations")
    BULK_UPDATE_SELF_MODIFY = _("Cannot modify your own account in bulk operations")
    
    # Bulk Delete specific
    BULK_DELETE_NO_IDS = _("No IDs provided for bulk delete")
    BULK_DELETE_INVALID_ID = _("Object not found or already deleted")
    BULK_DELETE_SELF = _("Cannot delete your own account")
    BULK_DELETE_LAST_ADMIN = _("Cannot delete user: last admin in organization")
    BULK_DELETE_PROTECTED = _("Cannot delete protected user")
    
    # Bulk Operation Results
    BULK_OPERATION_TIMEOUT = _("Bulk operation timed out after processing {processed} of {total} items")
    BULK_OPERATION_CANCELLED = _("Bulk operation cancelled by user")
    BULK_RESULT_ROW = _("Row {row}")
    BULK_RESULT_ITEM = _("Item {index}")
    
    # CSV Import specific (for frontend integration)
    CSV_PARSE_ERROR = _("Failed to parse CSV file: {error}")
    CSV_INVALID_HEADERS = _("Invalid CSV headers. Expected: {expected}")
    CSV_EMPTY_FILE = _("CSV file is empty")
    CSV_TOO_MANY_ROWS = _("CSV file contains {count} rows. Maximum {max_rows} allowed")
    CSV_ENCODING_ERROR = _("CSV file encoding error. Please use UTF-8 encoding")


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
    ACCOUNT_NOT_FOUND = _("Account not found")

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

class ActivityErrorMessages:
    """Activity specific error messages"""
    
    # Status transitions
    CANNOT_COMPLETE_CANCELLED = _("Cannot complete a cancelled activity")
    CANNOT_CANCEL_COMPLETED = _("Cannot cancel a completed activity")
    ALREADY_CANCELLED = _("Activity is already cancelled")
    CANNOT_REOPEN = _("Only completed or cancelled activities can be reopened")
    CANNOT_REOPEN_CLOSED_CYCLE = _("Cannot reopen activity while the decision cycle is closed. Reopen the cycle first. ")
    INVALID_TARGET_STATUS = _("Target status must be PLANNED")
    PREVIOUS_ACTIVITY_NOT_COMPLETED = "Complete the previous activities in the playlist before logging this one."
    
    # Relation validation
    STEP_REQUIRES_CYCLE = _("Please select a pipeline step when linking to a decision cycle")
    CYCLE_REQUIRED_FOR_STEP = _("Please select a decision cycle before choosing a step")
    STEP_REQUIRED_FOR_CYCLE = _("Please select a pipeline step when linking to a decision cycle")
    CIRCULAR_REFERENCE = _("Activity cannot be its own next activity")
    CONTACT_MUST_BELONG_TO_ACCOUNT = _("Contact must belong to the activity's account")
    STEP_MUST_BELONG_TO_CYCLE = _("The selected step does not belong to this decision cycle")
    
    # Next Step Agreement
    NO_NEXT_STEP_REASON_REQUIRED = _("A reason is required when no follow-up is planned")
    INVALID_NO_NEXT_STEP_REASON = _("Reason must be a valid code or 'OTHER: <custom text>'")
    
    # Creation - Generic
    CREATION_FAILED = _("Activity creation failed. Please try again.")
    
    # Creation - Inline entities
    CONTACT_CREATION_FAILED = _("Failed to create contact. Please try again.")
    CYCLE_CREATION_FAILED = _("Failed to create decision cycle. Please try again.")
    INLINE_ENTITY_FAILED = _("Failed to create {entity}. Please try again.")

    # Creation - Validation failures (with context)
    CREATION_INVALID_DATA = _("Activity creation failed: {detail}")
    
    # Not found
    ACTIVITY_NOT_FOUND = _("Activity not found")


class CampaignErrorMessages: #TO DELETE
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

class CampaignModuleErrorMessages:
    """
    Error messages for new Campaign module (app_modules/campaigns).

    Separate from legacy CampaignErrorMessages (apps/campaign) to avoid
    conflicts during migration.
    """

    # Campaign Lifecycle
    CAMPAIGN_INVALID_STATE = _("Campaign is in an invalid state for this operation: {current_state}")
    CAMPAIGN_TRANSITION_INVALID = _("Cannot transition campaign from '{from_state}' to '{to_state}'")
    CAMPAIGN_ALREADY_ACTIVE = _("Campaign is already active")
    CAMPAIGN_NOT_ACTIVE = _("Campaign must be active to perform this action")
    CAMPAIGN_IN_FINAL_STATE = _("Cannot modify campaign in final state: {state}")

    # Campaign Validation
    CAMPAIGN_DATE_INVALID = _("Campaign end date must be after start date")
    CAMPAIGN_DATE_PAST = _("Campaign dates cannot be in the past")
    CAMPAIGN_TERRITORY_REQUIRED = _("Outbound campaigns require a territory")
    CAMPAIGN_SEQUENCE_REQUIRED = _("Outbound campaigns require a sequence type")
    CAMPAIGN_NO_ACCOUNTS = _("Campaign must have at least one account")
    TARGETED_CAMPAIGN_MANUAL_CREATION_FORBIDDEN = (
        "Targeted campaigns cannot be created manually. "
        "A single Targeted campaign is automatically provisioned per user."
    )

    # CampaignAccount
    ACCOUNT_ALREADY_IN_CAMPAIGN = _("Account is already in this campaign")
    ACCOUNT_NOT_IN_CAMPAIGN = _("Account not found in this campaign")
    ACCOUNT_INVALID_STATE = _("Campaign account is in an invalid state: {state}")
    ACCOUNT_TRANSITION_INVALID = _(
        "Cannot transition account from '{from_state}' to '{to_state}'. "
        "Allowed: {allowed_transitions}"
    )
    ACCOUNT_FINAL_STATE = _("Cannot modify account in final state: {state}")
    MAX_ACCOUNTS_EXCEEDED = _("Maximum accounts per campaign exceeded: {max}")

    # CampaignMember
    MEMBER_ALREADY_EXISTS = _("User already has role '{role}' in this campaign")
    MEMBER_NOT_FOUND = _("Member not found in this campaign")
    OWNER_REQUIRED = _("Campaign must have at least one owner")
    CANNOT_REMOVE_PRIMARY_OWNER = _("Cannot remove the primary owner of a campaign")
    MAX_MEMBERS_EXCEEDED = _("Maximum members per campaign exceeded: {max}")
    CONTACT_OPTED_OUT = _("This contact has opted out and cannot be enrolled in a campaign.")
    CONTACT_NOT_REACHABLE = _("This contact has no reachable channel (email or phone).")
    


    # CampaignObjective
    OBJECTIVE_NOT_FOUND = _("Objective not found for this campaign")
    CANNOT_DELETE_PRIMARY_OBJECTIVE = "Cannot delete the primary objective of an active campaign."
    OBJECTIVE_PRIMARY_EXISTS = _("Campaign already has a primary objective")
    OBJECTIVE_INVALID_TYPE = _("Invalid objective type: {objective_type}")
    OBJECTIVE_TARGET_VALUE_INVALID = _("Target value must be greater than 0")
    MAX_OBJECTIVES_EXCEEDED = _("Maximum objectives per campaign exceeded: {max}")

    # Execution & Activities
    ACTIVITY_GENERATION_FAILED = _("Failed to generate activities: {reason}")
    
    PLAYLIST_EMPTY = _("No activities available in campaign playlist")
    EXECUTION_FAILED = _("Campaign execution failed: {reason}")
    TARGETED_CAMPAIGN_LIFECYCLE_FORBIDDEN = (
    "Lifecycle actions (start/pause/resume/complete) are not available "
    "for Targeted campaigns."
)

    # Analytics
    ANALYTICS_CALCULATION_FAILED = _("Failed to calculate campaign analytics: {reason}")

    # Bulk operations
    BULK_OPERATION_FAILED = _("Bulk operation failed: {operation}")

class SignalErrorMessages:
    # -----------------------------------------------------------------
    # Lifecycle & generic
    # -----------------------------------------------------------------
    NOT_PENDING_VALIDATED    = _("Only PENDING signals can be validated.")
    NOT_PENDING_REJECTED     = _("Only PENDING signals can be rejected.")
    NOT_EDITABLE             = _("Cannot edit a signal with status '{status}'.")
    INVALID_SIGNAL_TYPE      = _("Invalid signal type: '{signal_type}'.")
    SOURCE_CONTACT_REQUIRED  = _("A source contact is required for this signal type.")
    SOURCE_ACTIVITY_REQUIRED = _("A source activity is required for this signal type.")

    # -----------------------------------------------------------------
    # Legacy — kept for backward compatibility (ObjectiveSignal may
    # still enforce the relaxed rule in a future sprint).
    # -----------------------------------------------------------------
    CONTEXT_REQUIRED = _(
        "A pain signal must be linked to at least one of: "
        "source activity, decision cycle, or campaign."
    )

    # Superseded by the Pain/Impact split (Sprint 1.6+). Impacted
    # contact now lives on PainImpact with its own rules. Kept only
    # for code paths that may still reference it.
    IMPACTED_CONTACT_REQUIRED = _(
        "Impacted contact is required when pain level is Personal "
        "or when a human impact is set."
    )

    # -----------------------------------------------------------------
    # PainImpact-specific — level-driven conditional requirements.
    # Introduced in Sprint 1.11 (Pain/Impact split).
    # -----------------------------------------------------------------
    IMPACT_PAIN_REQUIRED = _(
        "An impact must be linked to a pain signal."
    )
    IMPACT_LEVEL_REQUIRED = _(
        "Impact level is required."
    )
    IMPACT_BUSINESS_NO_DEPT = _(
        "Business impacts must not specify an impacted department."
    )
    IMPACT_BUSINESS_NO_CONTACT = _(
        "Business impacts must not specify an impacted contact."
    )
    IMPACT_BUSINESS_NO_HUMAN = _(
        "Human impact is only meaningful on personal impacts."
    )
    IMPACT_DEPT_REQUIRES_DEPT = _(
        "Department impacts require an impacted department."
    )
    IMPACT_DEPT_NO_CONTACT = _(
        "Department impacts must not specify an impacted contact. "
        "Use a personal impact instead."
    )
    IMPACT_PERSONAL_REQUIRES_CONTACT = _(
        "Personal impacts require an impacted contact."
    )
    IMPACT_PERSONAL_NO_DEPT = _(
        "Personal impacts must not specify an impacted department. "
        "Use a department impact instead."
    )
    IMPACT_CONTACT_WRONG_ACCOUNT = _(
        "Impacted contact must belong to the same account as the parent pain."
    )

    # -----------------------------------------------------------------
    # ObjectiveSignal-specific — scope-conditional target requirements.
    # Introduced in Wave B (Objective port).
    #
    # Scope rules (mirror of ObjectiveSignal.clean()):
    #   PERSONAL   → target_contact required, target_department forbidden
    #   DEPARTMENT → target_department required, target_contact forbidden
    #   BUSINESS   → neither target_contact nor target_department
    # -----------------------------------------------------------------
    OBJECTIVE_PERSONAL_REQUIRES_CONTACT = _(
        "Personal objectives require a target contact."
    )
    OBJECTIVE_PERSONAL_NO_DEPT = _(
        "Personal objectives must not specify a target department. "
        "Use a department-scoped objective instead."
    )
    OBJECTIVE_DEPT_REQUIRES_DEPT = _(
        "Department objectives require a target department."
    )
    OBJECTIVE_DEPT_NO_CONTACT = _(
        "Department objectives must not specify a target contact. "
        "Use a personal-scoped objective instead."
    )
    OBJECTIVE_BUSINESS_NO_CONTACT = _(
        "Business objectives must not specify a target contact."
    )
    OBJECTIVE_BUSINESS_NO_DEPT = _(
        "Business objectives must not specify a target department."
    )

    CLUSTER_ACCOUNT_REQUIRED = _(
        "An account is required to query signal clusters."
    )
    CLUSTER_CANONICAL_KEY_REQUIRED = _(
        "A canonical key is required to target a signal cluster."
    )
    CLUSTER_SIGNAL_TYPE_INVALID = _(
        "Invalid cluster signal type: '{signal_type}'."
    )
    CLUSTER_NOT_FOUND = _(
        "No signal cluster found for the given account and canonical key."
    )
    CLUSTER_ALREADY_ARCHIVED = _(
        "This signal cluster is already archived."
    )
    CLUSTER_NOT_ARCHIVED = _(
        "This signal cluster is not archived."
    )

class TechCatalogErrorMessages:
    """Error messages for the TechCatalog module."""

    # Field-level validation
    NAME_REQUIRED       = _("Name is required.")
    ALIASES_NOT_LIST    = _("Aliases must be a list of strings.")
    ALIAS_NOT_STRING    = _("Each alias must be a string.")


class OpportunityErrorMessages:
    """Opportunity and Pipeline specific error messages"""
    
    # Pipeline Template Errors
    TEMPLATE_TYPE_NOT_SUPPORTED = _("Template type '{template_type}' not supported. Available types: {available_types}")
    TEMPLATE_NOT_FOUND = _("Pipeline template not found")
    TEMPLATE_ALREADY_EXISTS = _("A template with this name already exists")
    TEMPLATE_IN_USE = _("Cannot delete template '{template_name}' because it is being used by {pipelines_count} opportunity pipeline(s)")
    TEMPLATE_CREATION_FAILED = _("Template creation failed: {reason}")
    TEMPLATE_UPDATE_FAILED = _("Template update failed: {reason}")
    TEMPLATE_DUPLICATION_FAILED = _("Template duplication failed: {reason}")
    
    # Pipeline Stage Errors
    STAGE_NOT_FOUND = _("Pipeline stage not found")
    STAGE_ORDER_CONFLICT = _("A stage with order {order} already exists in this pipeline")
    STAGE_NAME_DUPLICATE = _("A stage with name '{stage_name}' already exists in this pipeline")
    STAGE_INVALID_TRANSITION = _("Cannot transition from stage '{from_stage}' to '{to_stage}'")
    STAGE_COMPLETION_BLOCKED = _("Cannot complete stage '{stage_name}': {reason}")
    STAGE_HAS_DEPENDENCIES = _("Cannot modify stage '{stage_name}' because it has active substages")
    
    # Pipeline SubStage Errors
    SUBSTAGE_NOT_FOUND = _("Pipeline substage not found")
    SUBSTAGE_TYPE_INVALID = _("Invalid substage type: '{substage_type}'")
    SUBSTAGE_DURATION_INVALID = _("Substage duration must be greater than 0")
    SUBSTAGE_DATE_INVALID = _("Substage end date must be after start date")
    SUBSTAGE_ALREADY_COMPLETED = _("Substage '{substage_name}' is already completed")
    SUBSTAGE_BLOCKED = _("Substage '{substage_name}' is blocked: {reason}")
    SUBSTAGE_DEPENDENCIES_NOT_MET = _("Cannot start substage '{substage_name}': dependencies not met")
    
    # Opportunity Pipeline Errors
    PIPELINE_NOT_FOUND = _("Opportunity pipeline not found")
    PIPELINE_ALREADY_EXISTS = _("Opportunity already has a pipeline")
    PIPELINE_INVALID_STATE = _("Pipeline is in invalid state for this operation: {current_state}")
    PIPELINE_COMPLETION_FAILED = _("Pipeline completion failed: {reason}")
    PIPELINE_CREATION_FAILED = _("Pipeline creation failed: {reason}")
    PIPELINE_UPDATE_FAILED = _("Pipeline update failed: {reason}")
    PIPELINE_CUSTOMIZATION_FAILED = _("Pipeline customization failed: {reason}")
    PIPELINE_NO_STAGES = _("Pipeline must have at least one stage")
    PIPELINE_INVALID_CURRENT_STAGE = _("Current stage does not belong to this pipeline")
    
    # Substage Metadata Errors
    METADATA_NOT_FOUND = _("Substage metadata not found")
    METADATA_STAKEHOLDER_INVALID = _("Invalid stakeholder: contact does not belong to opportunity account")
    METADATA_DEPARTMENT_INVALID = _("Invalid department selection")
    METADATA_APPROVAL_REQUIRED = _("Substage '{substage_name}' requires approval before proceeding")
    METADATA_BUDGET_EXCEEDED = _("Actual cost ({actual}) exceeds estimated budget ({estimated}) for substage '{substage_name}'")
    METADATA_RISK_THRESHOLD_EXCEEDED = _("Risk level for substage '{substage_name}' exceeds acceptable threshold")
    
    # Pipeline Navigation Errors
    NAVIGATION_NO_NEXT_STAGE = _("No next stage available in pipeline")
    NAVIGATION_NO_PREVIOUS_STAGE = _("No previous stage available in pipeline")
    NAVIGATION_STAGE_NOT_READY = _("Stage '{stage_name}' is not ready for transition")
    NAVIGATION_PREREQUISITES_NOT_MET = _("Cannot move to stage '{stage_name}': prerequisites not met")
    
    # Pipeline Validation Errors
    VALIDATION_STAGE_REQUIRED = _("At least one pipeline stage is required")
    VALIDATION_ORDER_GAPS = _("Pipeline stages must have consecutive order numbers")
    VALIDATION_CIRCULAR_DEPENDENCY = _("Circular dependency detected in pipeline stages")
    VALIDATION_INVALID_TEMPLATE = _("Selected template is not compatible with this opportunity")
    VALIDATION_MISSING_REQUIRED_FIELDS = _("Missing required fields for stage '{stage_name}': {fields}")
    
    # Chasing System Errors (Phase 4)
    CHASING_NOT_CONFIGURED = _("Automatic chasing is not configured for substage '{substage_name}'")
    CHASING_INVALID_DELAY = _("Chasing delay must be greater than 0 days")
    CHASING_SEQUENCE_NOT_FOUND = _("Chasing sequence not found")
    CHASING_ALREADY_ACTIVE = _("Chasing is already active for substage '{substage_name}'")
    CHASING_PAUSED = _("Chasing is paused for substage '{substage_name}'")
    CHASING_TRIGGER_FAILED = _("Failed to trigger automatic chasing: {reason}")
    
    # Integration Errors (Phase 3)
    ACTIVITY_LINK_FAILED = _("Failed to link activity to substage: {reason}")
    ACTIVITY_NOT_IN_PIPELINE = _("Activity does not belong to this pipeline")
    ACTIVITY_SUBSTAGE_MISMATCH = _("Activity belongs to a different substage")
    ACTIVITY_OPPORTUNITY_MISMATCH = _("Activity does not belong to the opportunity associated with this substage")
    OPPORTUNITY_NOT_FOUND = _("Opportunity not found or not accessible")
    OPPORTUNITY_CLOSED = _("Cannot modify pipeline: opportunity is closed")
    
    # Permission Errors
    PIPELINE_OWNER_REQUIRED = _("You can only modify your own opportunity pipelines")
    PIPELINE_STAKEHOLDER_REQUIRED = _("You must be a stakeholder to access this pipeline")
    TEMPLATE_MODIFICATION_DENIED = _("You cannot modify this template")
    STAGE_MODIFICATION_DENIED = _("You cannot modify this stage")
    
    # Business Logic Errors
    STAGE_SKIP_NOT_ALLOWED = _("Stage '{stage_name}' cannot be skipped")
    SUBSTAGE_PARALLEL_EXECUTION_CONFLICT = _("Cannot execute parallel substages: {conflicting_substages}")
    PIPELINE_DEADLINE_EXCEEDED = _("Pipeline deadline exceeded: expected completion was {expected_date}")
    STAKEHOLDER_APPROVAL_PENDING = _("Cannot proceed: stakeholder approval pending for '{substage_name}'")
    BUDGET_APPROVAL_REQUIRED = _("Budget approval required for substage '{substage_name}': amount {amount}")
    
    # Data Integrity Errors
    PIPELINE_INCONSISTENT_STATE = _("Pipeline data is in an inconsistent state: {details}")
    STAGE_ORDER_CORRUPTION = _("Stage order corruption detected in pipeline")
    SUBSTAGE_PARENT_MISMATCH = _("Substage does not belong to the specified stage")
    TEMPLATE_STAGE_MISMATCH = _("Stage does not belong to the specified template")
    
    # Metrics and Analytics Errors
    METRICS_CALCULATION_FAILED = _("Failed to calculate pipeline metrics: {reason}")
    PROGRESS_TRACKING_FAILED = _("Failed to track pipeline progress: {reason}")
    ANALYTICS_DATA_INCOMPLETE = _("Cannot generate analytics: incomplete pipeline data")
    PERFORMANCE_DATA_UNAVAILABLE = _("Performance data not available for pipeline")
    
    # Import/Export Errors
    PIPELINE_EXPORT_FAILED = _("Failed to export pipeline data: {reason}")
    PIPELINE_IMPORT_FAILED = _("Failed to import pipeline data: {reason}")
    TEMPLATE_EXPORT_FAILED = _("Failed to export template: {reason}")
    BULK_PIPELINE_OPERATION_FAILED = _("Bulk pipeline operation failed: {operation}")
    
    # Configuration Errors
    PIPELINE_CONFIG_INVALID = _("Invalid pipeline configuration: {config_issue}")
    STAGE_CONFIG_MISSING = _("Stage configuration missing for type '{stage_type}'")
    SUBSTAGE_TYPE_CONFIG_INVALID = _("Invalid configuration for substage type '{substage_type}'")
    TEMPLATE_CONFIG_CORRUPTED = _("Template configuration is corrupted")
    
    # Timing and Schedule Errors
    SUBSTAGE_OVERDUE = _("Substage '{substage_name}' is overdue by {days} days")
    PIPELINE_SCHEDULE_CONFLICT = _("Schedule conflict detected in pipeline: {conflict_details}")
    STAGE_DURATION_EXCEEDED = _("Stage '{stage_name}' duration exceeded: expected {expected} days, actual {actual} days")
    CHASING_SCHEDULE_INVALID = _("Invalid chasing schedule configuration")
    
    # Resource and Capacity Errors
    RESOURCE_UNAVAILABLE = _("Required resource not available for substage '{substage_name}': {resource}")
    CAPACITY_EXCEEDED = _("Pipeline capacity exceeded: maximum {max_pipelines} concurrent pipelines allowed")
    STAKEHOLDER_UNAVAILABLE = _("Required stakeholder not available: {stakeholder}")
    DEPARTMENT_OVERLOADED = _("Department '{department}' is overloaded with pipeline activities")

    ACTIVITY_ALREADY_LINKED = _("Activity is already linked to another substage")
    SUBSTAGE_OPPORTUNITY_NOT_FOUND = _("Cannot determine opportunity for substage")
    
    # Messages existants qui doivent être présents :
    ACTIVITY_LINK_FAILED = _("Failed to link activity to substage: {reason}")
    ACTIVITY_OPPORTUNITY_MISMATCH = _("Activity does not belong to the opportunity associated with this substage")
    SUBSTAGE_NOT_FOUND = _("SubStage not found or not accessible")

    UNIQUE_CONSTRAINT_ACTIVITY_SUBSTAGE = _("An activity already exists for this substage in your organization")
    FAILED_TO_UPDATE_OVERDUE_STATUS = _("Failed to update overdue status for substage: {reason}")
    