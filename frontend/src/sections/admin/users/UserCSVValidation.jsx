// frontend/src/sections/admin/users/userCSVValidation.jsx

/**
 * CSV Validation & Preparation for User Import
 * Centralizes all validation logic for CSV user import
 */

// Utils
import { sanitizeUserRow } from 'utils/validators';
import { resolveUserRelations, getAvailableValues } from './resolvers';

// ==============================|| COLUMN DEFINITIONS ||============================== //

/**
 * Get CSV column definitions
 * @returns {Array} Column definitions with key, label, and required flag
 */
export function getUserCSVColumns() {
  return [
    { key: 'email', label: 'Email', required: true },
    { key: 'first_name', label: 'First Name', required: false },
    { key: 'last_name', label: 'Last Name', required: false },
    { key: 'password', label: 'Password', required: false },
    { key: 'role', label: 'Role', required: false },
    { key: 'organization', label: 'Organization', required: false },
    { key: 'team', label: 'Team', required: false },
    { key: 'is_active', label: 'Active Status', required: false }
  ];
}

// ==============================|| VALIDATION ||============================== //

/**
 * Validate CSV data for user import
 * @param {Array} data - Parsed CSV data (array of row objects)
 * @param {Object} lookups - Lookup tables from buildLookups()
 * @returns {Object} Validation result with valid/invalid rows and stats
 */
export function validateUserCSVData(data, lookups) {
  if (!data || !Array.isArray(data)) {
    return {
      validRows: [],
      invalidRows: [],
      stats: { total: 0, valid: 0, invalid: 0, duplicates: 0 },
      allErrors: []
    };
  }

  const validRows = [];
  const invalidRows = [];
  const allErrors = [];
  const emailsSeen = new Set();

  data.forEach((rawRow, index) => {
    const rowNumber = rawRow._rowIndex || index + 1;
    const rowErrors = [];

    // Step 1: Sanitize the row
    const { clean, issues } = sanitizeUserRow(rawRow);
    
    if (issues.length > 0) {
      issues.forEach(issue => {
        const errorMsg = `Row ${rowNumber}: ${issue}`;
        rowErrors.push(errorMsg);
        allErrors.push(errorMsg);
      });
    }

    // Step 2: Check for duplicate emails in the CSV
    if (clean.email) {
      if (emailsSeen.has(clean.email)) {
        const errorMsg = `Row ${rowNumber}: Duplicate email "${clean.email}"`;
        rowErrors.push(errorMsg);
        allErrors.push(errorMsg);
      } else {
        emailsSeen.add(clean.email);
      }
    }

    // Step 3: Resolve relations (role, organization, team)
    let resolved = { ...clean };
    if (lookups && rowErrors.length === 0) {
      const { resolved: resolvedData, issues: resolveIssues } = resolveUserRelations(clean, lookups);
      resolved = resolvedData;
      
      if (resolveIssues.length > 0) {
        resolveIssues.forEach(issue => {
          const errorMsg = `Row ${rowNumber}: ${issue}`;
          rowErrors.push(errorMsg);
          allErrors.push(errorMsg);
        });
      }
    }

    // Add row to valid or invalid list
    const rowWithIndex = { ...resolved, _rowIndex: rowNumber, _originalRow: rawRow };
    
    if (rowErrors.length === 0) {
      validRows.push(rowWithIndex);
    } else {
      invalidRows.push({ ...rawRow, _rowIndex: rowNumber, _errors: rowErrors });
    }
  });

  return {
    validRows,
    invalidRows,
    stats: {
      total: data.length,
      valid: validRows.length,
      invalid: invalidRows.length,
      duplicates: data.length - emailsSeen.size
    },
    allErrors
  };
}

// ==============================|| SAMPLE CSV GENERATION ||============================== //

/**
 * Generate a sample CSV with example data
 * @param {Object} lookups - Optional lookup tables for real values
 * @returns {string} CSV content as string
 */
export function generateSampleCSV(lookups) {
  const columns = getUserCSVColumns();
  const headers = columns.map(col => col.label).join(',');
  
  // Get available values if lookups provided
  const availableValues = lookups ? getAvailableValues(lookups) : null;
  
  // Sample data rows
  const sampleRows = [
    {
      email: 'john.doe@example.com',
      first_name: 'John',
      last_name: 'Doe',
      password: 'SecurePass123',
      role: availableValues?.roles?.[0] || 'Admin',
      organization: availableValues?.organizations?.[0] || 'Sales EMEA',
      team: availableValues?.teams?.[0]?.name || 'Sales Team',
      is_active: 'true'
    },
    {
      email: 'jane.smith@example.com',
      first_name: 'Jane',
      last_name: 'Smith',
      password: 'AnotherPass456',
      role: availableValues?.roles?.[1] || 'User',
      organization: availableValues?.organizations?.[0] || 'Sales EMEA',
      team: '',
      is_active: 'yes'
    },
    {
      email: 'bob.wilson@example.com',
      first_name: 'Bob',
      last_name: 'Wilson',
      password: '',
      role: '',
      organization: '',
      team: '',
      is_active: '1'
    }
  ];

  // Convert to CSV rows
  const dataRows = sampleRows.map(row => {
    return columns.map(col => {
      const value = row[col.key] || '';
      // Escape quotes and wrap in quotes if contains comma
      const escaped = String(value).replace(/"/g, '""');
      return /[,\n"]/.test(escaped) ? `"${escaped}"` : escaped;
    }).join(',');
  });

  return [headers, ...dataRows].join('\n');
}

// ==============================|| API PREPARATION ||============================== //

/**
 * Prepare validated rows for API submission
 * @param {Array} validatedRows - Rows that passed validation
 * @returns {Array} Array of user objects ready for API
 */
export function prepareUserDataForAPI(validatedRows) {
  if (!validatedRows || !Array.isArray(validatedRows)) {
    return [];
  }

  return validatedRows.map(row => {
    // Remove internal fields
    const { _rowIndex, _originalRow, ...userData } = row;

    // Build API payload
    const payload = {
      email: userData.email
    };

    // Add optional fields only if present
    if (userData.first_name) payload.first_name = userData.first_name;
    if (userData.last_name) payload.last_name = userData.last_name;
    if (userData.password) payload.password = userData.password;
    if (userData.role) payload.role = userData.role;
    if (userData.organization) payload.organization = userData.organization;
    if (userData.team) payload.team = userData.team;
    if (userData.is_active !== undefined) payload.is_active = userData.is_active;

    return payload;
  });
}

// ==============================|| DEFAULT EXPORT ||============================== //

export default {
  getUserCSVColumns,
  validateUserCSVData,
  generateSampleCSV,
  prepareUserDataForAPI
};