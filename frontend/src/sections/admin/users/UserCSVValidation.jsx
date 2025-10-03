/**
 * User CSV validation logic
 * Validates and transforms user data for import
 */

// Email validation regex
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Valid boolean values
const BOOLEAN_TRUE = ['true', '1', 'yes', 'y', 'on'];
const BOOLEAN_FALSE = ['false', '0', 'no', 'n', 'off'];

/**
 * Validate single user row
 * @param {Object} row - Raw row data from CSV
 * @param {number} rowIndex - Row number in CSV
 * @returns {Object} {isValid: boolean, errors: Array, data: Object}
 */
const validateUserRow = (row, rowIndex) => {
  const errors = [];
  const transformedData = {};

  // Required: Email
  if (!row.email || !row.email.trim()) {
    errors.push(`Row ${rowIndex}: Email is required`);
  } else {
    const email = row.email.trim().toLowerCase();
    if (!EMAIL_REGEX.test(email)) {
      errors.push(`Row ${rowIndex}: Invalid email format (${row.email})`);
    }
    transformedData.email = email;
  }

  // Optional: First Name
  if (row.first_name) {
    const firstName = row.first_name.trim();
    if (firstName.length > 50) {
      errors.push(`Row ${rowIndex}: First name too long (max 50 characters)`);
    }
    transformedData.first_name = firstName;
  } else {
    transformedData.first_name = '';
  }

  // Optional: Last Name
  if (row.last_name) {
    const lastName = row.last_name.trim();
    if (lastName.length > 50) {
      errors.push(`Row ${rowIndex}: Last name too long (max 50 characters)`);
    }
    transformedData.last_name = lastName;
  } else {
    transformedData.last_name = '';
  }

  // Optional: Role (keep as string for backend to validate against existing roles)
  if (row.role) {
    transformedData.role = row.role.trim();
  }

  // Optional: Organization (keep as string for backend to validate)
  if (row.organization) {
    transformedData.organization = row.organization.trim();
  }

  // Optional: Team
  if (row.team) {
    const team = row.team.trim();
    // Team requires organization
    if (team && !transformedData.organization) {
      errors.push(`Row ${rowIndex}: Team requires an organization`);
    }
    transformedData.team = team;
  }

  // Optional: Active Status (default to true if not specified)
  if (row.is_active && row.is_active.trim()) {
    const value = row.is_active.trim().toLowerCase();
    if (BOOLEAN_TRUE.includes(value)) {
      transformedData.is_active = true;
    } else if (BOOLEAN_FALSE.includes(value)) {
      transformedData.is_active = false;
    } else {
      errors.push(`Row ${rowIndex}: Invalid is_active value "${row.is_active}". Use true/false, 1/0, yes/no`);
    }
  } else {
    transformedData.is_active = true; // Default to active
  }

  // Optional: Password (only for new users)
  if (row.password) {
    const password = row.password.trim();
    if (password.length < 8) {
      errors.push(`Row ${rowIndex}: Password must be at least 8 characters`);
    }
    transformedData.password = password;
  }

  return {
    isValid: errors.length === 0,
    errors,
    data: transformedData
  };
};

/**
 * Validate all user data from CSV
 * @param {Array} rawData - Raw data from CSV parser
 * @returns {Object} Validation results
 */
export const validateUserCSVData = (rawData) => {
  if (!rawData || !Array.isArray(rawData)) {
    return {
      success: false,
      error: 'No data to validate',
      validRows: [],
      invalidRows: [],
      totalRows: 0
    };
  }

  const validRows = [];
  const invalidRows = [];
  const allErrors = [];
  const emailMap = new Map();
  const duplicateEmails = new Set();

  // First pass: validate each row
  rawData.forEach((row) => {
    const rowIndex = row._rowIndex || validRows.length + invalidRows.length + 1;
    const validation = validateUserRow(row, rowIndex);

    const processedRow = {
      ...validation.data,
      _rowIndex: rowIndex,
      _errors: validation.errors,
      _isValid: validation.isValid
    };

    if (validation.isValid) {
      // Check for duplicate emails
      const email = validation.data.email;
      if (emailMap.has(email)) {
        // Mark both rows as invalid
        const firstOccurrence = emailMap.get(email);
        processedRow._errors.push(`Row ${rowIndex}: Duplicate email (first seen in row ${firstOccurrence})`);
        processedRow._isValid = false;
        duplicateEmails.add(email);
        invalidRows.push(processedRow);
      } else {
        emailMap.set(email, rowIndex);
        validRows.push(processedRow);
      }
    } else {
      invalidRows.push(processedRow);
    }

    allErrors.push(...validation.errors);
  });

  // Second pass: mark first occurrences of duplicate emails as invalid
  if (duplicateEmails.size > 0) {
    const updatedValidRows = [];
    validRows.forEach(row => {
      if (duplicateEmails.has(row.email)) {
        row._errors.push(`Row ${row._rowIndex}: Duplicate email found in other rows`);
        row._isValid = false;
        invalidRows.push(row);
      } else {
        updatedValidRows.push(row);
      }
    });
    validRows.length = 0;
    validRows.push(...updatedValidRows);
  }

  // Sort invalid rows by row number for better display
  invalidRows.sort((a, b) => a._rowIndex - b._rowIndex);

  return {
    success: true,
    validRows,
    invalidRows,
    allErrors,
    totalRows: rawData.length,
    stats: {
      total: rawData.length,
      valid: validRows.length,
      invalid: invalidRows.length,
      duplicates: duplicateEmails.size
    }
  };
};

/**
 * Prepare valid data for API submission
 * @param {Array} validRows - Validated rows
 * @returns {Array} Clean data ready for API
 */
export const prepareUserDataForAPI = (validRows) => {
  return validRows.map(row => {
    // Remove internal fields
    const { _rowIndex, _errors, _isValid, ...userData } = row;
    return userData;
  });
};

/**
 * Get column definitions for user import
 */
export const getUserCSVColumns = () => [
  { key: 'email', label: 'email', required: true },
  { key: 'first_name', label: 'First Name', required: false },
  { key: 'last_name', label: 'Last Name', required: false },
  { key: 'password', label: 'Password', required: false },
  { key: 'role', label: 'Role', required: false },
  { key: 'organization', label: 'Organization', required: false },
  { key: 'team', label: 'Team', required: false },
  { key: 'is_active', label: 'Active Status', required: false }
];