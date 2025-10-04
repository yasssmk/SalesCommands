// frontend/src/sections/admin/users/resolvers.js

/**
 * Resolvers for CSV Import - Convert names to UUIDs
 * 
 * Purpose:
 * - Convert Role, Organization, Team names to UUIDs
 * - Support both UUID and name inputs
 * - Case-insensitive name matching
 * - Clear error messages for resolution failures
 */

import { isValidUUID } from 'utils/validators';

// API imports
import axiosClient from 'utils/axiosClient';

// ==============================|| API FETCHERS ||============================== //

/**
 * Fetch all roles for the current tenant
 */
const fetchRoles = async () => {
  const response = await axiosClient.get('/client/roles/');
  return response.data?.results || [];
};

/**
 * Fetch all organizations for the current tenant
 */
const fetchOrganizations = async () => {
  const response = await axiosClient.get('/client/organizations/');
  return response.data?.results || [];
};

/**
 * Fetch all teams for the current tenant
 * @param {string} organizationId - Optional filter by organization
 */
const fetchTeams = async (organizationId = null) => {
  let url = '/client/teams/';
  if (organizationId) {
    url += `?organization=${organizationId}`;
  }
  const response = await axiosClient.get(url);
  return response.data?.results || [];
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
 */
export const buildLookups = async () => {
  try {
    // Fetch all data in parallel
    const [roles, organizations, teams] = await Promise.all([
      fetchRoles(),
      fetchOrganizations(),
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

    // Build organization lookups
    const orgsById = new Map();
    const orgsByName = new Map();
    
    organizations.forEach(org => {
      orgsById.set(org.id, org);
      orgsByName.set(org.name.toLowerCase().trim(), org);
    });

    // Build team lookups (grouped by organization)
    const teamsById = new Map();
    const teamsByOrgAndName = new Map(); // Map<orgId, Map<teamName, team>>
    
    teams.forEach(team => {
      teamsById.set(team.id, team);
      
      // Group by organization
      const orgId = team.organization;
      if (orgId) {
        if (!teamsByOrgAndName.has(orgId)) {
          teamsByOrgAndName.set(orgId, new Map());
        }
        const orgTeams = teamsByOrgAndName.get(orgId);
        orgTeams.set(team.name.toLowerCase().trim(), team);
      }
    });

    return {
      roles: {
        byId: rolesById,
        byName: rolesByName,
        all: roles
      },
      organizations: {
        byId: orgsById,
        byName: orgsByName,
        all: organizations
      },
      teams: {
        byId: teamsById,
        byOrgAndName: teamsByOrgAndName,
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
 * Resolve organization input (name or UUID) to organization ID
 * 
 * @param {string} input - Organization name or UUID
 * @param {Object} lookups - Lookup tables from buildLookups()
 * @returns {Object} { id: string|null, issue?: string }
 * 
 * @example
 * resolveOrganization('Sales EMEA', lookups) // { id: 'uuid-456' }
 * resolveOrganization('invalid-org', lookups) // { id: null, issue: 'Unknown organization "invalid-org"' }
 */
export const resolveOrganization = (input, lookups) => {
  if (!input || !lookups?.organizations) {
    return { id: null };
  }

  const trimmedInput = String(input).trim();
  
  // Check if it's already a valid UUID
  if (isValidUUID(trimmedInput)) {
    // Verify it exists
    if (lookups.organizations.byId.has(trimmedInput)) {
      return { id: trimmedInput };
    }
    return { 
      id: null, 
      issue: `Organization ID "${trimmedInput}" not found` 
    };
  }

  // Try to resolve by name (case-insensitive)
  const lowerInput = trimmedInput.toLowerCase();
  const org = lookups.organizations.byName.get(lowerInput);
  
  if (org) {
    return { id: org.id };
  }

  // Not found
  return { 
    id: null, 
    issue: `Unknown organization "${trimmedInput}"` 
  };
};

/**
 * Resolve team input (name or UUID) to team ID
 * Requires organization ID when resolving by name
 * 
 * @param {string} input - Team name or UUID
 * @param {string} orgId - Organization ID (required for name resolution)
 * @param {Object} lookups - Lookup tables from buildLookups()
 * @returns {Object} { id: string|null, issue?: string }
 * 
 * @example
 * resolveTeam('Sales Team', 'org-uuid', lookups) // { id: 'uuid-789' }
 * resolveTeam('Sales Team', null, lookups) // { id: null, issue: 'Team name requires organization' }
 */
export const resolveTeam = (input, orgId, lookups) => {
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

  // For name resolution, we need an organization
  if (!orgId) {
    return { 
      id: null, 
      issue: 'Team name requires organization to be specified' 
    };
  }

  // Get teams for this organization
  const orgTeams = lookups.teams.byOrgAndName.get(orgId);
  if (!orgTeams) {
    return { 
      id: null, 
      issue: `No teams found in the specified organization` 
    };
  }

  // Try to resolve by name (case-insensitive)
  const lowerInput = trimmedInput.toLowerCase();
  const team = orgTeams.get(lowerInput);
  
  if (team) {
    return { id: team.id };
  }

  // Not found in this organization
  return { 
    id: null, 
    issue: `Unknown team "${trimmedInput}" in the specified organization` 
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
      organizations: [],
      teams: []
    };
  }

  return {
    roles: lookups.roles?.all?.map(r => r.name).sort() || [],
    organizations: lookups.organizations?.all?.map(o => o.name).sort() || [],
    teams: lookups.teams?.all?.map(t => ({
      name: t.name,
      organization: lookups.organizations?.byId?.get(t.organization)?.name || 'Unknown'
    })).sort((a, b) => a.name.localeCompare(b.name)) || []
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

  // Resolve organization
  let orgId = null;
  if (userRow.organization) {
    const orgResult = resolveOrganization(userRow.organization, lookups);
    if (orgResult.id) {
      resolved.organization = orgResult.id;
      orgId = orgResult.id;
    } else {
      resolved.organization = null;
      if (orgResult.issue) {
        issues.push(orgResult.issue);
      }
    }
  }

  // Resolve team (needs organization if provided by name)
  if (userRow.team) {
    const teamResult = resolveTeam(userRow.team, orgId, lookups);
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
  resolveOrganization,
  resolveTeam,
  resolveUserRelations,
  getAvailableValues
};