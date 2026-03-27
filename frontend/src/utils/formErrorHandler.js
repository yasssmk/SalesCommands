// frontend/src/utils/formErrorHandler.js

/**
 * ✅ CENTRALIZED FORM ERROR HANDLER (MVP-FRIENDLY)
 *
 * Intelligent error handling for Formik forms:
 * - 4XX with field validation → setFieldError() for each field
 * - 4XX generic (no fields) → snackbar
 * - 5XX / network / timeout → snackbar
 * - All error messages in English
 *
 * This replaces scattered displayErrorSnackbar() calls in forms with
 * a single, intelligent handler that decides the best UX approach.
 *
 * @module utils/formErrorHandler
 */

import { displayErrorSnackbar, displayWarningSnackbar } from "./displayError";
import { getErrorDisplayInfo } from "./errorMessages";
import { showSnackbar } from "./snackbar";

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Check if value is a plain object (not Array, not null)
 * @param {any} obj - Value to check
 * @returns {boolean} true if plain object
 */
const isPlainObject = (obj) => {
  return (
    obj !== null &&
    typeof obj === "object" &&
    !Array.isArray(obj) &&
    Object.prototype.toString.call(obj) === "[object Object]"
  );
};

/**
 *
 * Bulk operations have this structure AND a valid success field:
 * {
 *   success: true | 'partial' | false,  ← Must exist and be valid
 *   summary: { requested, updated/created/deleted/archived, failed, skipped },
 *   results: { success: [], failed: [], skipped: [] },
 *   message: "..."
 * }
 *
 * @param {Object} data - Response data from backend
 * @returns {boolean} true if bulk operation
 */
const isBulkOperation = (data) => {
  if (!isPlainObject(data)) {
    return false;
  }

  const hasSummary = data.summary && isPlainObject(data.summary);
  const hasResults = data.results && isPlainObject(data.results);
  const hasValidSuccess =
    data.success !== undefined &&
    (data.success === true ||
      data.success === false ||
      data.success === "partial");

  return hasSummary && hasResults && hasValidSuccess;
};

/**
 * ✅ IMPROVED: Handle bulk operation partial success ONLY
 *
 * This function should ONLY handle true partial successes (1-99%).
 * Total failures (0%) should fall through to standard error handling.
 *
 * @param {Object} data - Bulk operation response
 * @param {Object} formik - Formik instance (for setSubmitting)
 * @param {Object} options - Handler options
 * @param {Function} onComplete - Optional callback to close modal after handling
 * @returns {boolean} true if handled, false if should fall through
 */
const handleBulkPartialSuccess = (data, formik, options, onComplete) => {
  const { summary, results, success, message: backendMessage } = data;

  // Extract counts
  const requested = summary?.requested || 0;
  const successCount =
    summary?.updated ||
    summary?.created ||
    summary?.deleted ||
    summary?.archived ||
    0;
  const failedCount = summary?.failed || 0;
  const skippedCount = summary?.skipped || 0;

  // Calculate success rate
  const successRate = requested > 0 ? (successCount / requested) * 100 : 0;

  if (process.env.NODE_ENV === "development") {
    console.group("🔍 [handleBulkPartialSuccess] Processing bulk operation");
    console.log("Success:", success);
    console.log("Backend message:", backendMessage);
    console.log("Summary:", summary);
    console.log("Success rate:", `${successRate.toFixed(1)}%`);
    console.log("Results:", results);
  }

  // ====================================================================
  // ⭐ CRITICAL: Si 0% de succès, ce n'est PAS un succès partiel
  // Laisser le code de gestion d'erreur standard gérer ça
  // ====================================================================
  if (successRate === 0) {
    if (process.env.NODE_ENV === "development") {
      console.log("⚠️ 0% success rate - delegating to standard error handling");
      console.groupEnd();
    }

    // Stop submitting state
    if (options.setSubmittingFalse && formik?.setSubmitting) {
      formik.setSubmitting(false);
    }

    return false; // Indicate NOT handled, fall through
  }

  // ====================================================================
  // Determine severity and message (pour 1-99% seulement)
  // ====================================================================
  let severity;
  let message;

  if (successRate < 50) {
    // Mostly failed (1-49%) → RED ERROR
    severity = "error";
    message = `Operation mostly failed: ${successCount}/${requested} succeeded`;
  } else if (successRate < 100) {
    // Partially successful (50-99%) → ORANGE WARNING
    severity = "warning";
    message = `Partially complete: ${successCount}/${requested} succeeded`;
  } else {
    // 100% success should NOT reach this function
    severity = "info";
    message = `Operation complete: ${successCount}/${requested} succeeded`;
  }

  // ====================================================================
  // Display snackbar with appropriate severity
  // ====================================================================
  if (severity === "warning") {
    displayWarningSnackbar(message);
  } else if (severity === "error") {
    displayErrorSnackbar({
      message,
      status: 400,
    });
  } else {
    displayErrorSnackbar({ message, status: 200 });
  }

  // ====================================================================
  // Log failed items in dev for debugging
  // ====================================================================
  if (process.env.NODE_ENV === "development" && results?.failed?.length > 0) {
    console.group("❌ Failed Items Details");
    results.failed.forEach((item, index) => {
      console.log(`\n[${index + 1}] ${item.email || item.id || "Unknown"}`);
      if (item.errors && Array.isArray(item.errors)) {
        item.errors.forEach((err) => console.log(`   - ${err}`));
      }
    });
    console.groupEnd();
  }

  if (process.env.NODE_ENV === "development") {
    console.groupEnd();
  }

  // ====================================================================
  // ⭐ NEW: Close modal after handling (even on partial failure)
  // ====================================================================
  if (onComplete && typeof onComplete === "function") {
    if (process.env.NODE_ENV === "development") {
      console.log("🔒 Closing modal after bulk operation");
    }
    onComplete();
  }

  // Stop submitting state
  if (options.setSubmittingFalse && formik?.setSubmitting) {
    formik.setSubmitting(false);
  }

  return true; // Indicate handled
};

/**
 * Parse field name from generic error message
 *
 * Attempts to extract a field name from error messages like:
 * - "Role is required" → {role: "This field is required"}
 * - ["role is required"] → {role: "This field is required"}  ✅ NEW
 * - "Email is required" → {email: "This field is required"}
 * - "role: This field is required" → {role: "This field is required"}
 * - "User role is required" → {role: "This field is required"}
 *
 * @param {string|Array} errorMessage - Generic error message (string or array)
 * @returns {Object|null} Field errors object or null if no field detected
 */
const parseFieldFromErrorMessage = (errorMessage) => {
  if (!errorMessage) {
    return null;
  }

  // ✅ NEW: Handle array format: ["role is required"] → "role is required"
  if (Array.isArray(errorMessage)) {
    if (errorMessage.length === 0) {
      return null;
    }
    // Take first message from array
    errorMessage = errorMessage[0];
  }

  // Must be string after array handling
  if (typeof errorMessage !== "string") {
    return null;
  }

  const message = errorMessage.trim();

  // ✅ STRATEGY: Two-tier field detection
  //
  // Tier 1: Common fields (fast path)
  // - Covers 95% of form fields across all models
  // - Optimized for "FieldName is required" pattern
  //
  // Tier 2: Dynamic regex fallback (universal)
  // - Captures ANY field via "field_name: message" pattern
  // - Works for all future models without config
  //
  // This approach is:
  // - Scalable: Works for User, Contact, Account, Lead, Opportunity, etc.
  // - Zero-config: New models work automatically
  // - Performance: Fast path for common fields

  const knownFields = [
    // ========== Authentication & Identity ==========
    "email",
    "password",
    "username",
    "first_name",
    "last_name",
    "full_name",
    "name",
    "phone",
    "phone_number",
    "mobile",

    // ========== Address & Location ==========
    "address",
    "street",
    "city",
    "state",
    "country",
    "postal_code",
    "post_code",
    "zip_code",

    // ========== User Management ==========
    "role",
    "organization",
    "team",
    "is_active",
    "is_superuser",
    "is_staff",

    // ========== Contact Fields ==========
    "title",
    "position",
    "department",
    "company",
    "company_name",
    "website",
    "linkedin",

    // ========== Account/Company Fields ==========
    "account_name",
    "industry",
    "annual_revenue",
    "employee_count",
    "company_size",

    // ========== Lead/Opportunity Fields ==========
    "lead_source",
    "lead_status",
    "opportunity_name",
    "deal_value",
    "close_date",
    "probability",
    "stage",
    "pipeline",

    // ========== Campaign Fields ==========
    "campaign_name",
    "campaign_type",
    "start_date",
    "end_date",
    "budget",
    "target_audience",

    // ========== Generic Form Fields ==========
    "description",
    "notes",
    "status",
    "type",
    "category",
    "priority",
    "date",
    "amount",
    "quantity",
    "price",
    "currency",
    "tags",
  ];

  // Pattern 1: "FieldName is required" or "FieldName: error message"
  for (const field of knownFields) {
    const patterns = [
      new RegExp(`^${field}\\s+is\\s+required`, "i"), // "Role is required"
      new RegExp(`^${field}\\s*:\\s*(.+)$`, "i"), // "role: This field is required"
      new RegExp(`^user\\s+${field}\\s+is\\s+required`, "i"), // "User role is required"
      new RegExp(`^${field}\\s+field\\s+is\\s+required`, "i"), // "Role field is required"
      new RegExp(`^the\\s+${field}\\s+is\\s+required`, "i"), // "The role is required"
    ];

    for (const pattern of patterns) {
      if (pattern.test(message)) {
        // Extract the error message (if available) or use generic
        const match = message.match(new RegExp(`^${field}\\s*:\\s*(.+)$`, "i"));
        const errorText = match ? match[1].trim() : "This field is required.";

        if (process.env.NODE_ENV === "development") {
          console.log(
            `✅ Detected field '${field}' from message: "${message}"`,
          );
        }

        return {
          [field]: errorText,
        };
      }
    }
  }

  // Pattern 2: Extract field name from "field: message" format
  const colonMatch = message.match(/^([a-z_]+)\s*:\s*(.+)$/i);
  if (colonMatch) {
    const field = colonMatch[1].toLowerCase().trim();
    const errorText = colonMatch[2].trim();

    if (process.env.NODE_ENV === "development") {
      console.log(
        `✅ Extracted field '${field}' from colon pattern: "${message}"`,
      );
    }

    return {
      [field]: errorText,
    };
  }

  // No field detected
  return null;
};

/**
 * ✅ Extract field-level validation errors from response
 *
 * Handles common DRF validation formats:
 * - {field: ["error"]} → {field: "error"}
 * - {field: "error"} → {field: "error"}
 * - {field: ["error1", "error2"]} → {field: "error1. error2."}
 * - {error: "Role is required"} → {role: "This field is required"}  ✅ NEW
 * - {error: "Email is required"} → {email: "This field is required"}  ✅ NEW
 *
 * @param {Object} data - Response data from backend
 * @returns {Object|null} Field errors object or null if no field errors
 */
const extractFieldErrors = (data) => {
  if (!isPlainObject(data)) {
    return null;
  }

  // ✅ NEW: Try to parse generic error messages that mention field names
  const nonFieldKeys = [
    "detail",
    "error",
    "message",
    "non_field_errors",
    // ✅ Bulk operation metadata (not form fields)
    "success",
    "summary",
    "results", // ← CRITIQUE: contient UUIDs, pas field errors
    "status",
    "httpStatus",
    "isTimeout",
    "is202",
    "hasData",
  ];
  const hasOnlyNonFieldKeys = Object.keys(data).every((key) =>
    nonFieldKeys.includes(key),
  );

  if (hasOnlyNonFieldKeys) {
    // ✅ NEW: Before giving up, check if the error message mentions a field name
    const genericError = data.error || data.detail || data.message;

    if (process.env.NODE_ENV === "development") {
      console.log("[extractFieldErrors] hasOnlyNonFieldKeys = true");
      console.log("[extractFieldErrors] genericError:", genericError);
      console.log(
        "[extractFieldErrors] genericError type:",
        typeof genericError,
      );
      console.log(
        "[extractFieldErrors] genericError isArray:",
        Array.isArray(genericError),
      );
    }

    // ✅ FIXED: Handle both string and array
    if (genericError) {
      const parsedFieldError = parseFieldFromErrorMessage(genericError);

      if (process.env.NODE_ENV === "development") {
        console.log("[extractFieldErrors] parsedFieldError:", parsedFieldError);
      }

      if (parsedFieldError) {
        // Successfully extracted a field name from the generic error
        if (process.env.NODE_ENV === "development") {
          console.log(
            "✅ Parsed field error from generic message:",
            parsedFieldError,
          );
        }
        return parsedFieldError;
      }
    }

    // No field could be extracted, treat as non-field error
    if (process.env.NODE_ENV === "development") {
      console.log(
        "[extractFieldErrors] No field could be extracted, returning null",
      );
    }
    return null;
  }

  const fieldErrors = {};
  let foundFieldError = false;

  Object.entries(data).forEach(([field, value]) => {
    // Skip meta fields
    if (nonFieldKeys.includes(field)) {
      return;
    }

    // Extract error message from various formats
    let errorMessage = null;

    if (typeof value === "string") {
      // Direct string: {email: "Invalid email"}
      errorMessage = value;
    } else if (Array.isArray(value) && value.length > 0) {
      // Array of strings: {email: ["Invalid email"]}
      const stringMessages = value
        .filter((v) => typeof v === "string")
        .map((v) => v.trim())
        .filter((v) => v.length > 0);

      if (stringMessages.length > 0) {
        errorMessage = stringMessages.join(". ");
        if (!errorMessage.endsWith(".")) {
          errorMessage += ".";
        }
      }
    } else if (isPlainObject(value)) {
      // Nested object: {user: {email: ["Invalid"]}}
      // For forms, we typically flatten: user.email → email
      // Or concatenate messages if multiple fields
      const nestedMessages = [];
      Object.values(value).forEach((nestedVal) => {
        if (typeof nestedVal === "string") {
          nestedMessages.push(nestedVal);
        } else if (Array.isArray(nestedVal)) {
          nestedVal.forEach((item) => {
            if (typeof item === "string") {
              nestedMessages.push(item);
            }
          });
        }
      });

      if (nestedMessages.length > 0) {
        errorMessage = nestedMessages.join(". ");
        if (!errorMessage.endsWith(".")) {
          errorMessage += ".";
        }
      }
    }

    if (errorMessage) {
      fieldErrors[field] = errorMessage;
      foundFieldError = true;
    }
  });

  return foundFieldError ? fieldErrors : null;
};

/**
 * ✅ Check if error should show field-level errors vs snackbar
 *
 * Field-level errors are appropriate when:
 * - Status is 4XX (client error)
 * - Response contains field-specific validation errors
 * - Not a generic 401/403/404/429
 *
 * @param {number} status - HTTP status code
 * @param {Object} fieldErrors - Extracted field errors
 * @returns {boolean} true if should use field errors
 */
const shouldUseFieldErrors = (status, fieldErrors) => {
  // Must be 4XX
  if (status < 400 || status >= 500) {
    return false;
  }

  // Skip auth/rate-limit errors (always snackbar)
  if (status === 401 || status === 403 || status === 429) {
    return false;
  }

  // Must have field errors
  if (!fieldErrors || Object.keys(fieldErrors).length === 0) {
    return false;
  }

  return true;
};

// ==============================|| MAIN HANDLER ||============================== //

/**
 * ✅ HANDLE FORMIK ERROR - Intelligent routing to field errors or snackbar
 *
 * This is the main entry point for all form error handling.
 * Use this in all Formik onSubmit handlers instead of displayErrorSnackbar.
 *
 * Decision tree:
 * 1. Extract status and data from error
 * 2. Try to extract field-level validation errors
 * 3. If 4XX + has field errors → setFieldError() for each field + optional snackbar
 * 4. Otherwise → snackbar only
 *
 * ✅ UPDATED: Now automatically sets fields as "touched" to force display of server errors
 *
 * @param {Error|Object} error - Error from API call (Axios error or result object)
 * @param {Object} formik - Formik instance (from useFormik hook)
 * @param {Object} [options={}] - Optional configuration
 * @param {boolean} [options.showSnackbarWithFields=false] - Show snackbar even when using field errors
 * @param {boolean} [options.setSubmittingFalse=true] - Automatically call setSubmitting(false)
 * @param {string} [options.fallbackMessage] - Custom fallback message if extraction fails
 *
 * @example
 * // Basic usage in form onSubmit
 * const formik = useFormik({
 *   onSubmit: async (values, { setSubmitting }) => {
 *     try {
 *       const result = await insertUser(values);
 *       if (result.success) {
 *         displaySuccessSnackbar('User created');
 *         closeModal();
 *       } else {
 *         handleFormikError(result, formik); // 🆕 One call handles everything
 *       }
 *     } catch (err) {
 *       handleFormikError(err, formik); // 🆕 Works with exceptions too
 *     }
 *   }
 * });
 *
 * @example
 * // With options
 * handleFormikError(error, formik, {
 *   showSnackbarWithFields: true, // Show snackbar even if field errors exist
 *   setSubmittingFalse: true,     // Auto-call setSubmitting(false)
 * });
 */
export const handleFormikError = (error, formik, options = {}) => {
  const {
    showSnackbarWithFields = false,
    setSubmittingFalse = true,
    fallbackMessage = null,
    onComplete = null,
  } = options;

  if (process.env.NODE_ENV === "development") {
    console.group("🔍 [handleFormikError] Processing form error");
    console.log("Error:", error);
    console.log("Options:", options);
  }

  // ====================================================================
  // STEP 0: Check if this is a bulk operation (NEW)
  // ====================================================================
  let responseData = null;

  // Try to extract response data
  if (error?.response?.data) {
    responseData = error.response.data;
  } else if (error && !error.response && isPlainObject(error)) {
    // Direct result object (not Axios error)
    responseData = error;
  }

  if (responseData && isBulkOperation(responseData)) {
    const { success } = responseData;

    if (process.env.NODE_ENV === "development") {
      console.log("✅ Bulk operation detected, success:", success);
    }

    // Handle partial success or failure with some successes
    if (success === "partial" || success === false) {
      // ⭐ NEW: Pass onComplete callback from options
      const handled = handleBulkPartialSuccess(
        responseData,
        formik,
        options,
        options.onComplete, // ⭐ NEW: Pass the callback
      );

      if (handled) {
        if (process.env.NODE_ENV === "development") {
          console.groupEnd();
        }
        return; // Done - bulk operation handled
      }

      // Si pas handled, on continue vers STEP 1 pour gestion standard
      if (process.env.NODE_ENV === "development") {
        console.log("→ Falling through to standard error handling");
      }
    }

    // success === true should not reach handleFormikError
    if (success === true) {
      if (process.env.NODE_ENV === "development") {
        console.warn(
          "⚠️ Bulk operation with success=true passed to error handler",
        );
        console.groupEnd();
      }

      if (setSubmittingFalse && formik?.setSubmitting) {
        formik.setSubmitting(false);
      }
      return;
    }
  }

  // ====================================================================
  // STEP 1: Normalize error object
  // ====================================================================
  // Handle both Axios errors and API result objects
  let normalizedError = error;

  // If it's a result object {success: false, error, status}, convert to Error-like
  if (
    error &&
    !error.response &&
    error.status &&
    (error.error || error.message)
  ) {
    normalizedError = new Error(error.error || error.message);
    normalizedError.response = {
      status: error.status,
      data: error.data || error || { detail: error.error },
    };
    normalizedError.status = error.status;
  }

  // ====================================================================
  // STEP 2: Extract structured error info
  // ====================================================================
  const errorInfo = getErrorDisplayInfo(normalizedError);
  const { status, message } = errorInfo;

  if (process.env.NODE_ENV === "development") {
    console.log("Status:", status);
    console.log("General message:", message);
  }

  // ====================================================================
  // STEP 3: Try to extract field-level errors (4XX validation only)
  // ====================================================================
  // ⚠️ CORRECTION: Réutiliser responseData du STEP 0 si disponible
  if (!responseData) {
    responseData = normalizedError?.response?.data;
  }

  const fieldErrors = extractFieldErrors(responseData);

  if (process.env.NODE_ENV === "development") {
    console.log("Field errors extracted:", fieldErrors);
  }

  const useFieldErrors = shouldUseFieldErrors(status, fieldErrors);

  if (process.env.NODE_ENV === "development") {
    console.log("Decision: Use field errors?", useFieldErrors);
  }

  // ====================================================================
  // STEP 4: Apply field errors to Formik
  // ====================================================================
  if (useFieldErrors && fieldErrors) {
    // Set error for each field
    Object.entries(fieldErrors).forEach(([field, errorMsg]) => {
      if (formik.setFieldError) {
        formik.setFieldError(field, errorMsg);

        if (process.env.NODE_ENV === "development") {
          console.log(`✅ Set field error: ${field} = "${errorMsg}"`);
        }
      }

      // ✅ Force field to be "touched" so error displays immediately
      if (formik.setFieldTouched) {
        formik.setFieldTouched(field, true, false);

        if (process.env.NODE_ENV === "development") {
          console.log(`✅ Set field touched: ${field}`);
        }
      }
    });

    // Optionally show snackbar with summary
    if (showSnackbarWithFields) {
      const fieldCount = Object.keys(fieldErrors).length;
      const summaryMessage =
        fieldCount === 1
          ? "Please fix the validation error below."
          : `Please fix ${fieldCount} validation errors below.`;

      displayErrorSnackbar({
        message: summaryMessage,
        status: status,
      });

      if (process.env.NODE_ENV === "development") {
        console.log("📢 Snackbar shown (with field errors):", summaryMessage);
      }
    }

    if (process.env.NODE_ENV === "development") {
      console.log("✅ Field errors applied to Formik");
      console.groupEnd();
    }

    // Stop submitting state
    if (setSubmittingFalse && formik.setSubmitting) {
      formik.setSubmitting(false);
    }

    return; // Done - field errors handled
  }

  // ====================================================================
  // STEP 5: Show snackbar for non-field errors
  // ====================================================================
  // Use cases:
  // - 5XX server errors
  // - Network/timeout errors
  // - 4XX without field details (401, 403, 404, generic 400)
  // - 429 rate limit

  const snackbarMessage = fallbackMessage || message;

  displayErrorSnackbar(normalizedError);

  if (process.env.NODE_ENV === "development") {
    console.log("📢 Snackbar shown:", snackbarMessage);
    console.groupEnd();
  }

  const shouldCloseModal = status >= 500 || status === 0 || status === 408;

  if (shouldCloseModal && onComplete && typeof onComplete === "function") {
    if (process.env.NODE_ENV === "development") {
      console.log(
        "🔒 Closing modal after non-recoverable error (5XX/network/timeout)",
      );
    }
    onComplete();
  } else if (process.env.NODE_ENV === "development") {
    if (status >= 400 && status < 500 && status !== 408) {
      console.log("ℹ️ Keeping modal open (4XX error - user may retry)");
    } else {
      console.log("ℹ️ Modal kept open (no onComplete callback provided)");
    }
  }

  // Stop submitting state
  if (setSubmittingFalse && formik.setSubmitting) {
    formik.setSubmitting(false);
  }
};

// ==============================|| CONVENIENCE HELPERS ||============================== //

/**
 * ✅ Handle error with field errors AND snackbar
 *
 * Convenience wrapper that always shows both field errors and snackbar.
 * Useful for important errors that need maximum visibility.
 *
 * @param {Error|Object} error - Error object
 * @param {Object} formik - Formik instance
 */
export const handleFormikErrorWithSnackbar = (error, formik) => {
  handleFormikError(error, formik, {
    showSnackbarWithFields: true,
    setSubmittingFalse: true,
  });
};

/**
 * ✅ Handle error with custom message
 *
 * Use when you want to override the extracted message.
 *
 * @param {Error|Object} error - Error object
 * @param {Object} formik - Formik instance
 * @param {string} customMessage - Custom message to display
 */
export const handleFormikErrorWithMessage = (error, formik, customMessage) => {
  handleFormikError(error, formik, {
    fallbackMessage: customMessage,
    setSubmittingFalse: true,
  });
};

// ==============================|| EXPORTS ||============================== //

// export default {
//   handleFormikError,
//   handleFormikErrorWithSnackbar,
//   handleFormikErrorWithMessage
// };
