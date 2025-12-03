// frontend/src/sections/admin/accounts/AccountCSVValidation.jsx

/**
 * CSV Validation & Preparation for Account Import
 * Centralizes all validation logic for CSV account import
 */

// Utils
import { 
  trimString,
  isValidEmail,
  isValidUUID
} from 'utils/validators';

// ==============================|| COLUMN DEFINITIONS ||============================== //

/**
 * Get CSV column definitions
 * @returns {Array} Column definitions with key, label, and required flag
 */
export function getAccountCSVColumns() {
  return [
    { key: 'company_name', label: 'Company Name', required: true },
    { key: 'type', label: 'Type', required: false },
    { key: 'classification', label: 'Classification', required: false },
    { key: 'industry', label: 'Industry', required: false },
    { key: 'website', label: 'Website', required: false },
    { key: 'email', label: 'Email', required: false },
    { key: 'phone_number', label: 'Phone Number', required: false },
    { key: 'country', label: 'Country', required: true },
    { key: 'city', label: 'City', required: true },
    { key: 'address', label: 'Address', required: false },
    { key: 'post_code', label: 'Post Code', required: false },
    { key: 'state', label: 'State', required: false },
    { key: 'account_owner', label: 'Account Owner', required: false },
    { key: 'parent', label: 'Parent Company', required: false }
  ];
}

/**
 * Get import guidelines for accounts
 * @returns {Array<string>}
 */
export function getAccountCSVGuidelines() {
  return [
    'Required fields: Company Name (*), Country (*), City (*)',
    'Country must be a valid ISO country code (e.g., US, FR, GB, DE)',
    'Type accepted values: CLIENT, PROSPECT, PARTNER, VENDOR, OTHER',
    'Classification accepted values: SMB, MIDMARKET, ENTERPRISE, STARTUP, NONPROFIT',
    'Account Owner accepts either full name or email',
    'Parent Company accepts company name',
    'Email must be valid format if provided',
    'Website should include protocol (https://)'
  ];
}

// ==============================|| CONSTANTS ||============================== //

const VALID_TYPES = ['CLIENT', 'PROSPECT', 'PARTNER', 'VENDOR', 'OTHER'];
const VALID_CLASSIFICATIONS = ['SMB', 'MIDMARKET', 'ENTERPRISE', 'STARTUP', 'NONPROFIT'];

// ==============================|| CSV ROW SANITIZATION ||============================== //

/**
 * Sanitize an account row from CSV import
 * @param {Object} rawRow - Raw row from CSV
 * @returns {Object} { clean, issues }
 */
export function sanitizeAccountRow(rawRow) {
  const issues = [];
  const clean = {};

  // Company Name (required)
  if (rawRow.company_name) {
    const name = trimString(rawRow.company_name);
    if (name && name.length >= 2) {
      clean.company_name = name;
    } else {
      issues.push('Company name must be at least 2 characters');
    }
  } else {
    issues.push('Company name is required');
  }

  // Type (optional, must be valid)
  if (rawRow.type) {
    const type = trimString(rawRow.type).toUpperCase();
    if (VALID_TYPES.includes(type)) {
      clean.type = type;
    } else {
      issues.push(`Invalid type "${rawRow.type}". Valid: ${VALID_TYPES.join(', ')}`);
    }
  }

  // Classification (optional, must be valid)
  if (rawRow.classification) {
    const classification = trimString(rawRow.classification).toUpperCase();
    if (VALID_CLASSIFICATIONS.includes(classification)) {
      clean.classification = classification;
    } else {
      issues.push(`Invalid classification "${rawRow.classification}". Valid: ${VALID_CLASSIFICATIONS.join(', ')}`);
    }
  }

  // Industry (optional)
  if (rawRow.industry) {
    clean.industry = trimString(rawRow.industry);
  }

  // Website (optional)
  if (rawRow.website) {
    let website = trimString(rawRow.website);
    // Add https:// if no protocol
    if (website && !website.match(/^https?:\/\//i)) {
      website = `https://${website}`;
    }
    clean.website = website;
  }

  // Email (optional, validate format)
  if (rawRow.email) {
    const email = trimString(rawRow.email)?.toLowerCase();
    if (email && isValidEmail(email)) {
      clean.email = email;
    } else if (email) {
      issues.push(`Invalid email format: "${rawRow.email}"`);
    }
  }

  // Phone Number (optional)
  if (rawRow.phone_number) {
    clean.phone_number = trimString(rawRow.phone_number);
  }

  // Address fields 
 // Country (required, must be valid code from COUNTRIES)
  if (rawRow.country) {
    const countryCode = trimString(rawRow.country)?.toUpperCase();
    // Validate against COUNTRIES constant (imported from constants)
    if (countryCode && countryCode.length === 2) {
      clean.country = countryCode;
    } else {
      issues.push(`Invalid country code "${rawRow.country}". Use ISO code (e.g., US, FR, GB)`);
    }
  } else {
    issues.push('Country is required (ISO code, e.g., US, FR)');
  }

  // City (required)
  if (rawRow.city) {
    const city = trimString(rawRow.city);
    if (city && city.length >= 2) {
      clean.city = city;
    } else {
      issues.push('City must be at least 2 characters');
    }
  } else {
    issues.push('City is required');
  }

  if (rawRow.address) clean.address = trimString(rawRow.address);
  if (rawRow.post_code) clean.post_code = trimString(rawRow.post_code);
  if (rawRow.state) clean.state = trimString(rawRow.state);

  // Account Owner (optional, resolved later)
  if (rawRow.account_owner) {
    clean.account_owner = trimString(rawRow.account_owner);
  }

  // Parent Company (optional, resolved later)
  if (rawRow.parent) {
    clean.parent = trimString(rawRow.parent);
  }

  return { clean, issues };
}

// ==============================|| RELATION RESOLUTION ||============================== //

/**
 * Resolve account relations (account_owner, parent)
 * @param {Object} cleanRow - Sanitized row
 * @param {Object} lookups - Lookup tables { users, accounts }
 * @returns {Object} { resolved, issues }
 */
export function resolveAccountRelations(cleanRow, lookups) {
  const issues = [];
  const resolved = { ...cleanRow };

  // Resolve Account Owner
  if (cleanRow.account_owner) {
    const ownerInput = cleanRow.account_owner;
    let foundOwner = null;

    // Check if it's a UUID
    if (isValidUUID(ownerInput)) {
      foundOwner = lookups.users?.find(u => u.id === ownerInput);
    }
    
    // Try by email
    if (!foundOwner) {
      foundOwner = lookups.users?.find(
        u => u.email?.toLowerCase() === ownerInput.toLowerCase()
      );
    }
    
    // Try by full name
    if (!foundOwner) {
      foundOwner = lookups.users?.find(
        u => `${u.first_name} ${u.last_name}`.toLowerCase() === ownerInput.toLowerCase()
      );
    }

    if (foundOwner) {
      resolved.account_owner_id = foundOwner.id;
      delete resolved.account_owner;
    } else {
      issues.push(`Account owner not found: "${ownerInput}"`);
    }
  }

  // Resolve Parent Company
  if (cleanRow.parent) {
    const parentInput = cleanRow.parent;
    let foundParent = null;

    // Check if it's a UUID
    if (isValidUUID(parentInput)) {
      foundParent = lookups.accounts?.find(a => a.id === parentInput);
    }
    
    // Try by company name
    if (!foundParent) {
      foundParent = lookups.accounts?.find(
        a => a.company_name?.toLowerCase() === parentInput.toLowerCase()
      );
    }

    if (foundParent) {
      resolved.parent_id = foundParent.id;
      delete resolved.parent;
    } else {
      issues.push(`Parent company not found: "${parentInput}"`);
    }
  }

  return { resolved, issues };
}

// ==============================|| VALIDATION ||============================== //

/**
 * Validate CSV data for account import
 * @param {Array} data - Parsed CSV data (array of row objects)
 * @param {Object} lookups - Lookup tables from buildLookups()
 * @returns {Object} Validation result with valid/invalid rows and stats
 */
export function validateAccountCSVData(data, lookups) {
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
  const namesSeen = new Set();

  data.forEach((rawRow, index) => {
    const rowNumber = rawRow._rowIndex || index + 1;
    const rowErrors = [];

    // Step 1: Sanitize the row
    const { clean, issues } = sanitizeAccountRow(rawRow);
    
    if (issues.length > 0) {
      issues.forEach(issue => {
        const errorMsg = `Row ${rowNumber}: ${issue}`;
        rowErrors.push(errorMsg);
        allErrors.push(errorMsg);
      });
    }

    // Step 2: Check for duplicate company names in the CSV
    if (clean.company_name) {
      const normalizedName = clean.company_name.toLowerCase();
      if (namesSeen.has(normalizedName)) {
        const errorMsg = `Row ${rowNumber}: Duplicate company name "${clean.company_name}"`;
        rowErrors.push(errorMsg);
        allErrors.push(errorMsg);
      } else {
        namesSeen.add(normalizedName);
      }
    }

    // Step 3: Resolve relations (account_owner, parent)
    let resolved = { ...clean };
    if (lookups && rowErrors.length === 0) {
      const { resolved: resolvedData, issues: resolveIssues } = resolveAccountRelations(clean, lookups);
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
      duplicates: data.length - namesSeen.size
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
  const columns = getAccountCSVColumns();
  const headers = columns.map(col => col.label).join(',');
  
  // Sample data rows
  const sampleRows = [
    {
      company_name: 'Acme Corporation',
      type: 'CLIENT',
      classification: 'ENTERPRISE',
      industry: 'Technology',
      website: 'https://acme.com',
      email: 'contact@acme.com',
      phone_number: '+1-555-0100',
      country: 'United States',
      city: 'San Francisco',
      address: '123 Main St',
      post_code: '94105',
      state: 'CA',
      account_owner: lookups?.users?.[0]?.email || 'john.doe@example.com',
      parent: ''
    },
    {
      company_name: 'Tech Startup Inc',
      type: 'PROSPECT',
      classification: 'STARTUP',
      industry: 'Software',
      website: 'https://techstartup.io',
      email: 'hello@techstartup.io',
      phone_number: '+1-555-0200',
      country: 'US',
      city: 'Austin',
      address: '456 Innovation Blvd',
      post_code: '78701',
      state: 'TX',
      account_owner: '',
      parent: 'Acme Corporation'
    },
    {
      company_name: 'Global Partners Ltd',
      type: 'PARTNER',
      classification: 'MIDMARKET',
      industry: 'Consulting',
      website: 'https://globalpartners.com',
      email: 'info@globalpartners.com',
      phone_number: '+44-20-7946-0958',
      country: 'GB',
      city: 'London',
      address: '10 Downing Street',
      post_code: 'SW1A 2AA',
      state: '',
      account_owner: '',
      parent: ''
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
 * @returns {Array} Array of account objects ready for API
 */
export function prepareAccountDataForAPI(validatedRows) {
  if (!validatedRows || !Array.isArray(validatedRows)) {
    return [];
  }

  return validatedRows.map(row => {
    // Remove internal fields
    const { _rowIndex, _originalRow, ...accountData } = row;

    // Build API payload (required fields)
    const payload = {
      company_name: accountData.company_name
    };

    // Add optional string fields only if present
    const optionalFields = [
      'type', 'classification', 'industry', 'website', 'email',
      'phone_number', 'country', 'city', 'address', 'post_code', 'state'
    ];
    
    optionalFields.forEach(field => {
      if (accountData[field]) {
        payload[field] = accountData[field];
      }
    });

    // Add resolved FK fields
    if (accountData.account_owner_id) {
      payload.account_owner_id = accountData.account_owner_id;
    }
    if (accountData.parent_id) {
      payload.parent_id = accountData.parent_id;
    }

    return payload;
  });
}

// ==============================|| DEFAULT EXPORT ||============================== //

export default {
  getAccountCSVColumns,
  getAccountCSVGuidelines,
  validateAccountCSVData,
  generateSampleCSV,
  prepareAccountDataForAPI
};