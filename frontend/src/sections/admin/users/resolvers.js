// frontend/src/sections/admin/users/resolvers.js

/**
 * Resolvers for CSV Import - Convert names to UUIDs
 * 
 * Purpose:
 * - Convert Role, Team names to UUIDs
 * - Support both UUID and name inputs
 * - Case-insensitive name matching
 * - Clear error messages for resolution failures
 */

import { isValidUUID } from 'utils/validators';

// API imports
import { api } from 'utils/axiosClient';

// ==============================|| API FETCHERS ||============================== //

/**
 * Fetch all roles for the current tenant
 * Handles multiple response formats from backend
 */
const fetchRoles = async () => {
  const response = await api.get('/client/roles/');
  const data = response.data;
  
  // Handle various response formats
  if (Array.isArray(data)) return data;
  if (data?.results && Array.isArray(data.results)) return data.results;
  if (data?.data && Array.isArray(data.data)) return data.data;
  if (data?.data?.results && Array.isArray(data.data.results)) return data.data.results;
  
  console.warn('[resolvers] Unexpected roles response format:', data);
  return [];
};

/**
 * Fetch all teams for the current tenant
 * Handles multiple response formats from backend
 */
const fetchTeams = async () => {
  const response = await api.get('/client/teams/');
  const data = response.data;
  
  // Handle various response formats
  if (Array.isArray(data)) return data;
  if (data?.results && Array.isArray(data.results)) return data.results;
  if (data?.data && Array.isArray(data.data)) return data.data;
  if (data?.data?.results && Array.isArray(data.data.results)) return data.data.results;
  
  console.warn('[resolvers] Unexpected teams response format:', data);
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
 * // lookups.roles.byId['uuid'] = roleObject
 * // lookups.roles.byName['admin'] = roleObject
 * // lookups.teams.byId['uuid'] = teamObject
 * // lookups.teams.byName['sales team'] = teamObject
 */
export const buildLookups = async () => {
  try {
    // Fetch all data in parallel
    const [roles, teams] = await Promise.all([
      fetchRoles(),
      fetchTeams()
    ]);

    // Build role lookups
    const rolesById = new Map();
    const rolesByName = new Map();
    
    roles.forEach(role => {
      rolesById.set(role.id, role);
      // Store by lowercase name for case-insensitive lookup
      rolesByName.set(role.name.toLowerCase().trim(), role);
    });

    // Build team lookups
    const teamsById = new Map();
    const teamsByName = new Map();
    
    teams.forEach(team => {
      teamsById.set(team.id, team);
      // Store by lowercase name for case-insensitive lookup
      teamsByName.set(team.name.toLowerCase().trim(), team);
    });

    return {
      roles: {
        byId: rolesById,
        byName: rolesByName,
        all: roles
      },
      teams: {
        byId: teamsById,
        byName: teamsByName,
        all: teams
      }
    };
  } catch (error) {
    console.error('Failed to build lookups:', error);
    throw new Error('Failed to fetch reference data. Please check your connection and try again.');
  }
};

// ==============================|| RESOLVERS ||============================== //

/**
 * Resolve role input (name or UUID) to role ID
 * 
 * @param {string} input - Role name or UUID
 * @param {Object} lookups - Lookup tables from buildLookups()
 * @returns {Object} { id: string|null, issue?: string }
 * 
 * @example
 * resolveRole('Admin', lookups) // { id: 'uuid-123' }
 * resolveRole('invalid-role', lookups) // { id: null, issue: 'Unknown role "invalid-role"' }
 */
export const resolveRole = (input, lookups) => {
  if (!input || !lookups?.roles) {
    return { id: null };
  }

  const trimmedInput = String(input).trim();
  
  // Check if it's already a valid UUID
  if (isValidUUID(trimmedInput)) {
    // Verify it exists
    if (lookups.roles.byId.has(trimmedInput)) {
      return { id: trimmedInput };
    }
    return { 
      id: null, 
      issue: `Role ID "${trimmedInput}" not found` 
    };
  }

  // Try to resolve by name (case-insensitive)
  const lowerInput = trimmedInput.toLowerCase();
  const role = lookups.roles.byName.get(lowerInput);
  
  if (role) {
    return { id: role.id };
  }

  // Not found
  return { 
    id: null, 
    issue: `Unknown role "${trimmedInput}"` 
  };
};

/**
 * Resolve team input (name or UUID) to team ID
 * 
 * @param {string} input - Team name or UUID
 * @param {Object} lookups - Lookup tables from buildLookups()
 * @returns {Object} { id: string|null, issue?: string }
 * 
 * @example
 * resolveTeam('Sales Team', lookups) // { id: 'uuid-789' }
 * resolveTeam('invalid-team', lookups) // { id: null, issue: 'Unknown team "invalid-team"' }
 */
export const resolveTeam = (input, lookups) => {
  if (!input || !lookups?.teams) {
    return { id: null };
  }

  const trimmedInput = String(input).trim();
  
  // Check if it's already a valid UUID
  if (isValidUUID(trimmedInput)) {
    // Verify it exists
    if (lookups.teams.byId.has(trimmedInput)) {
      return { id: trimmedInput };
    }
    return { 
      id: null, 
      issue: `Team ID "${trimmedInput}" not found` 
    };
  }

  // Try to resolve by name (case-insensitive)
  const lowerInput = trimmedInput.toLowerCase();
  const team = lookups.teams.byName.get(lowerInput);
  
  if (team) {
    return { id: team.id };
  }

  // Not found
  return { 
    id: null, 
    issue: `Unknown team "${trimmedInput}"` 
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
      roles: [],
      teams: []
    };
  }

  return {
    roles: lookups.roles?.all?.map(r => r.name).sort() || [],
    teams: lookups.teams?.all?.map(t => t.name).sort() || []
  };
};

/**
 * Resolve all relational fields in a user row
 * 
 * @param {Object} userRow - Sanitized user row
 * @param {Object} lookups - Lookup tables
 * @returns {Object} { resolved: Object, issues: string[] }
 */
export const resolveUserRelations = (userRow, lookups) => {
  const resolved = { ...userRow };
  const issues = [];

  // Resolve role
  if (userRow.role) {
    resolved._originalRole = userRow.role;
    const roleResult = resolveRole(userRow.role, lookups);
    if (roleResult.id) {
      resolved.role = roleResult.id;
    } else {
      resolved.role = null;
      if (roleResult.issue) {
        issues.push(roleResult.issue);
      }
    }
  }

  // Resolve team
  if (userRow.team) {
    resolved._originalTeam = userRow.team;
    const teamResult = resolveTeam(userRow.team, lookups);
    if (teamResult.id) {
      resolved.team = teamResult.id;
    } else {
      resolved.team = null;
      if (teamResult.issue) {
        issues.push(teamResult.issue);
      }
    }
  }

  return { resolved, issues };
};

// ==============================|| EXPORTS ||============================== //

export default {
  buildLookups,
  resolveRole,
  resolveTeam,
  resolveUserRelations,
  getAvailableValues
};