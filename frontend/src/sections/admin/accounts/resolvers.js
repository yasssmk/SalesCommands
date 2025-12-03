// frontend/src/sections/admin/accounts/resolvers.js

/**
 * Resolvers for CSV Import - Convert names to UUIDs
 * 
 * Purpose:
 * - Convert Account Owner (user) names/emails to UUIDs
 * - Convert Parent Company names to UUIDs
 * - Support both UUID and name inputs
 * - Case-insensitive name matching
 * - Clear error messages for resolution failures
 */

import { isValidUUID } from 'utils/validators';

// API imports
import { api } from 'utils/axiosClient';

// ==============================|| API FETCHERS ||============================== //

/**
 * Fetch all users for the current tenant
 */
const fetchUsers = async () => {
  const response = await api.get('/client/users/');
  const data = response.data;
  
  // Handle various response formats
  if (Array.isArray(data)) return data;
  if (data?.results && Array.isArray(data.results)) return data.results;
  if (data?.data && Array.isArray(data.data)) return data.data;
  if (data?.data?.results && Array.isArray(data.data.results)) return data.data.results;
  
  console.warn('[resolvers] Unexpected users response format:', data);
  return [];
};

const fetchAccounts = async () => {
  const response = await api.get('/company-accounts/');
  const data = response.data;
  
  // Handle various response formats
  if (Array.isArray(data)) return data;
  if (data?.results && Array.isArray(data.results)) return data.results;
  if (data?.data && Array.isArray(data.data)) return data.data;
  if (data?.data?.results && Array.isArray(data.data.results)) return data.data.results;
  
  console.warn('[resolvers] Unexpected accounts response format:', data);
  return [];
};

// ==============================|| LOOKUP BUILDER ||============================== //

/**
 * Build lookup tables for efficient name resolution
 * 
 * @returns {Promise<Object>} Lookup tables with byId and byName maps
 * 
 * @example
 * const lookups = await buildLookups();
 * // lookups.users.byId['uuid'] = userObject
 * // lookups.users.byEmail['john@example.com'] = userObject
 * // lookups.accounts.byId['uuid'] = accountObject
 * // lookups.accounts.byName['acme corp'] = accountObject
 */
export const buildLookups = async () => {
  try {
    // Fetch all data in parallel
    const [users, accounts] = await Promise.all([
      fetchUsers(),
      fetchAccounts()
    ]);

    // Build user lookups
    const usersById = new Map();
    const usersByEmail = new Map();
    const usersByFullName = new Map();
    
    users.forEach(user => {
      usersById.set(user.id, user);
      // Store by lowercase email for case-insensitive lookup
      if (user.email) {
        usersByEmail.set(user.email.toLowerCase().trim(), user);
      }
      // Store by full name
      const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim().toLowerCase();
      if (fullName) {
        usersByFullName.set(fullName, user);
      }
    });

    // Build account lookups
    const accountsById = new Map();
    const accountsByName = new Map();
    
    accounts.forEach(account => {
      accountsById.set(account.id, account);
      // Store by lowercase company name for case-insensitive lookup
      if (account.company_name) {
        accountsByName.set(account.company_name.toLowerCase().trim(), account);
      }
    });

    return {
      users: {
        byId: usersById,
        byEmail: usersByEmail,
        byFullName: usersByFullName,
        all: users
      },
      accounts: {
        byId: accountsById,
        byName: accountsByName,
        all: accounts
      }
    };
  } catch (error) {
    console.error('Failed to build lookups:', error);
    throw new Error('Failed to fetch reference data. Please check your connection and try again.');
  }
};

// ==============================|| RESOLVERS ||============================== //

/**
 * Resolve account owner input (name, email, or UUID) to user ID
 * 
 * @param {string} input - User name, email, or UUID
 * @param {Object} lookups - Lookup tables from buildLookups()
 * @returns {Object} { id: string|null, issue?: string }
 * 
 * @example
 * resolveAccountOwner('john.doe@example.com', lookups) // { id: 'uuid-123' }
 * resolveAccountOwner('John Doe', lookups) // { id: 'uuid-123' }
 * resolveAccountOwner('invalid-user', lookups) // { id: null, issue: 'Unknown user "invalid-user"' }
 */
export const resolveAccountOwner = (input, lookups) => {
  if (!input || !lookups?.users) {
    return { id: null };
  }

  const trimmedInput = String(input).trim();
  
  // Check if it's already a valid UUID
  if (isValidUUID(trimmedInput)) {
    // Verify it exists
    if (lookups.users.byId.has(trimmedInput)) {
      return { id: trimmedInput };
    }
    return { 
      id: null, 
      issue: `User ID "${trimmedInput}" not found` 
    };
  }

  // Try to resolve by email (case-insensitive)
  const lowerInput = trimmedInput.toLowerCase();
  const userByEmail = lookups.users.byEmail.get(lowerInput);
  
  if (userByEmail) {
    return { id: userByEmail.id };
  }

  // Try to resolve by full name (case-insensitive)
  const userByName = lookups.users.byFullName.get(lowerInput);
  
  if (userByName) {
    return { id: userByName.id };
  }

  // Not found
  return { 
    id: null, 
    issue: `Unknown user "${trimmedInput}"` 
  };
};

/**
 * Resolve parent company input (name or UUID) to account ID
 * 
 * @param {string} input - Company name or UUID
 * @param {Object} lookups - Lookup tables from buildLookups()
 * @returns {Object} { id: string|null, issue?: string }
 * 
 * @example
 * resolveParentCompany('Acme Corp', lookups) // { id: 'uuid-456' }
 * resolveParentCompany('invalid-company', lookups) // { id: null, issue: 'Unknown company "invalid-company"' }
 */
export const resolveParentCompany = (input, lookups) => {
  if (!input || !lookups?.accounts) {
    return { id: null };
  }

  const trimmedInput = String(input).trim();
  
  // Check if it's already a valid UUID
  if (isValidUUID(trimmedInput)) {
    // Verify it exists
    if (lookups.accounts.byId.has(trimmedInput)) {
      return { id: trimmedInput };
    }
    return { 
      id: null, 
      issue: `Account ID "${trimmedInput}" not found` 
    };
  }

  // Try to resolve by company name (case-insensitive)
  const lowerInput = trimmedInput.toLowerCase();
  const account = lookups.accounts.byName.get(lowerInput);
  
  if (account) {
    return { id: account.id };
  }

  // Not found
  return { 
    id: null, 
    issue: `Unknown company "${trimmedInput}"` 
  };
};

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Get available values for display/help
 * 
 * @param {Object} lookups - Lookup tables
 * @returns {Object} Available values for each field
 */
export const getAvailableValues = (lookups) => {
  if (!lookups) {
    return {
      users: [],
      accounts: []
    };
  }

  return {
    users: lookups.users?.all?.map(u => ({
      id: u.id,
      email: u.email,
      name: `${u.first_name || ''} ${u.last_name || ''}`.trim()
    })).sort((a, b) => (a.name || a.email).localeCompare(b.name || b.email)) || [],
    accounts: lookups.accounts?.all?.map(a => ({
      id: a.id,
      name: a.company_name
    })).sort((a, b) => a.name.localeCompare(b.name)) || []
  };
};

/**
 * Resolve all relational fields in an account row
 * 
 * @param {Object} accountRow - Sanitized account row
 * @param {Object} lookups - Lookup tables
 * @returns {Object} { resolved: Object, issues: string[] }
 */
export const resolveAccountRelations = (accountRow, lookups) => {
  const resolved = { ...accountRow };
  const issues = [];

  // Resolve account owner
  if (accountRow.account_owner) {
    resolved._originalAccountOwner = accountRow.account_owner;
    const ownerResult = resolveAccountOwner(accountRow.account_owner, lookups);
    if (ownerResult.id) {
      resolved.account_owner_id = ownerResult.id;
      delete resolved.account_owner;
    } else {
      delete resolved.account_owner;
      if (ownerResult.issue) {
        issues.push(ownerResult.issue);
      }
    }
  }

  // Resolve parent company
  if (accountRow.parent) {
    resolved._originalParent = accountRow.parent;
    const parentResult = resolveParentCompany(accountRow.parent, lookups);
    if (parentResult.id) {
      resolved.parent_id = parentResult.id;
      delete resolved.parent;
    } else {
      delete resolved.parent;
      if (parentResult.issue) {
        issues.push(parentResult.issue);
      }
    }
  }

  return { resolved, issues };
};

// ==============================|| EXPORTS ||============================== //

export default {
  buildLookups,
  resolveAccountOwner,
  resolveParentCompany,
  resolveAccountRelations,
  getAvailableValues
};