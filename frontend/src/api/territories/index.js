// frontend/src/api/territories/index.js

/**
 * Territories API - Phase 1 (Hardcoded)
 * 
 * This file contains static territory definitions for MVP.
 * Future phases will add:
 * - Backend API endpoints
 * - SWR hooks for CRUD operations
 * - Filter definitions persistence
 * 
 * Territory types:
 * - 'account': Shows accounts list, uses useGetAccounts
 * - 'contact': Shows contacts list, uses useGetContacts (future)
 */

// ==============================|| TERRITORY TYPES ||============================== //

export const TERRITORY_TYPES = {
  ACCOUNT: 'account',
  CONTACT: 'contact'
};

// ==============================|| DEFAULT TERRITORIES ||============================== //

/**
 * Built-in territories available to all users
 * These cannot be deleted or modified
 */
export const TERRITORIES = [
  {
    id: 'all-accounts',
    name: 'All Accounts',
    type: TERRITORY_TYPES.ACCOUNT,
    description: 'All company accounts in your organization',
    isDefault: true,
    isBuiltIn: true,
    filters: {} // No filters = all records
  },
  {
    id: 'all-contacts',
    name: 'All Contacts',
    type: TERRITORY_TYPES.CONTACT,
    description: 'All contacts in your organization',
    isDefault: false,
    isBuiltIn: true,
    filters: {}
  }
];

// ==============================|| DEFAULT SELECTION ||============================== //

/**
 * Default territory ID when page loads
 */
export const DEFAULT_TERRITORY_ID = 'all-accounts';

// ==============================|| HELPERS ||============================== //

/**
 * Get territory by ID
 * @param {string} id - Territory ID
 * @returns {Object|undefined} Territory object or undefined
 */
export const getTerritoryById = (id) => {
  return TERRITORIES.find(t => t.id === id);
};

/**
 * Get territories by type
 * @param {string} type - Territory type ('account' or 'contact')
 * @returns {Array} Filtered territories
 */
export const getTerritoriesByType = (type) => {
  return TERRITORIES.filter(t => t.type === type);
};

// ==============================|| FUTURE: SWR HOOKS ||============================== //

/**
 * TODO Phase 2: Add these hooks when backend API is ready
 * 
 * export function useGetTerritories(options = {}) { ... }
 * export function useGetTerritory(id) { ... }
 * export async function createTerritory(payload) { ... }
 * export async function updateTerritory(id, payload) { ... }
 * export async function deleteTerritory(id) { ... }
 */