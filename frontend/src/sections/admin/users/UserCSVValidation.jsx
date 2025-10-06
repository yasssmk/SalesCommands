// frontend/src/sections/admin/users/userCSVValidation.jsx

/**
 * CSV Validation & Preparation for User Import
 * Centralizes all validation logic for CSV user import
 * 
 * IMPORTANT:
 * - organization is NOT in CSV (auto-assigned from team)
 * - is_superuser IS supported
 * - role is optional (not required)
 */

// Utils
import { sanitizeUserRow } from 'utils/validators';
import { resolveUserRelations, getAvailableValues } from './resolvers';

// ==============================|| COLUMN DEFINITIONS ||============================== //

/**
 * Get CSV column definitions
 * @returns {Array} Column definitions with key, label, and required flag
 * 
 * NOTES:
 * - email + password are required for user creation
 * - role is optional (can be assigned later)
 * - organization is NOT included (auto-assigned from team)
 * - team is optional
 * - is_active and is_superuser are optional booleans
 */
export function getUserCSVColumns() {
  return [
    { key: 'email', label: 'Email', required: true },
    { key: 'password', label: 'Password', required: true },
    { key: 'first_name', label: 'First Name', required: false },
    { key: 'last_name', label: 'Last Name', required: false },
    { key: 'role', label: 'Role', required: false },
    { key: 'team', label: 'Team', required: false },
    { key: 'is_active', label: 'Active', required: false },
    { key: 'is_superuser', label: 'Superuser', required: false }
  ];
}

export function getUserCSVGuidelines (){
  return [
  'Required fields: Email (*), Password (*)',
  'Active Status accepted values: true/false, 1/0, yes/no, y/n, on/off',
  'SUPERUSER accepted values: true/false, 1/0, yes/no, y/n, on/off',
  'Role / Team accept either name or ID (case-insensitive)',
  'Password must be at least 8 characters'
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

    // Step 1: Sanitize the row (includes is_superuser now)
    const { clean, issues } = sanitizeUserRow(rawRow);
    
    if (issues.length > 0) {
      issues.forEach(issue => {
        const errorMsg = `Row ${rowNumber}: ${issue}`;
        rowErrors.push(errorMsg);
        allErrors.push(errorMsg);
      });
    }

    // Step 2: Password is required for user creation
    if (!clean.password || clean.password.length < 8) {
      const errorMsg = `Row ${rowNumber}: Password is required (min 8 characters)`;
      rowErrors.push(errorMsg);
      allErrors.push(errorMsg);
    }

    // Step 3: Check for duplicate emails in the CSV
    if (clean.email) {
      if (emailsSeen.has(clean.email)) {
        const errorMsg = `Row ${rowNumber}: Duplicate email "${clean.email}"`;
        rowErrors.push(errorMsg);
        allErrors.push(errorMsg);
      } else {
        emailsSeen.add(clean.email);
      }
    }

    // Step 4: Resolve relations (role, team)
    // NOTE: organization is NOT resolved from CSV (auto-assigned from team)
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
      password: 'SecurePass123',
      first_name: 'John',
      last_name: 'Doe',
      role: availableValues?.roles?.[1] || 'Admin',
      team: availableValues?.teams?.[0]?.name || 'Admin Team',
      is_active: 'true',
      is_superuser: 'false'
    },
    {
      email: 'jane.smith@example.com',
      password: 'AnotherPass456',
      first_name: 'Jane',
      last_name: 'Smith',
      role: availableValues?.roles?.[0] || 'Account Executive',
      team: availableValues?.teams?.[1]?.name || 'Sale Team',
      is_active: 'yes',
      is_superuser: 'no'
    },
    {
      email: 'bob.wilson@example.com',
      password: 'BobPass789',
      first_name: 'Bob',
      last_name: 'Wilson',
      role: '',
      team: '',
      is_active: '1',
      is_superuser: '0'
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
 * 
 * NOTE: organization is intentionally excluded (auto-assigned from team)
 */
export function prepareUserDataForAPI(validatedRows) {
  if (!validatedRows || !Array.isArray(validatedRows)) {
    return [];
  }

  return validatedRows.map(row => {
    // Remove internal fields
    const { _rowIndex, _originalRow, ...userData } = row;

    // Build API payload (required fields)
    const payload = {
      email: userData.email,
      password: userData.password // Required for user creation
    };

    // Add optional fields only if present
    if (userData.first_name) payload.first_name = userData.first_name;
    if (userData.last_name) payload.last_name = userData.last_name;
    if (userData.role) payload.role = userData.role;
    if (userData.team) payload.team = userData.team;
    if (userData.is_active !== undefined) payload.is_active = userData.is_active;
    if (userData.is_superuser !== undefined) payload.is_superuser = userData.is_superuser;

    // NOTE: organization is NOT included (auto-assigned by backend from team)

    return payload;
  });
}

// ==============================|| DEFAULT EXPORT ||============================== //

export default {
  getUserCSVColumns,
  getUserCSVGuidelines,
  validateUserCSVData,
  generateSampleCSV,
  prepareUserDataForAPI
};