// frontend/src/sections/admin/users/userCSVConfig.js

/**
 * CSV Import Configuration for Users
 * 
 * Centralizes all user-specific CSV import settings:
 * - Column definitions
 * - Validation rules
 * - Guidelines for users
 * - API endpoints
 * - Data preparation logic
 * 
 * This configuration is consumed by the generic CSV import system
 * and can be duplicated for other entities (Account, Contact, Lead, etc.)
 */

// Validation & Preparation
import {
  getUserCSVColumns,
  getUserCSVGuidelines,
  validateUserCSVData,
  prepareUserDataForAPI,
  generateSampleCSV
} from './userCSVValidation';

// Resolvers (entity-specific)
import { buildLookups } from './resolvers';

// API
import { createBulkUsers } from 'api/admin/users';

// ==============================|| USER CSV IMPORT CONFIGURATION ||============================== //

/**
 * Complete configuration object for User CSV import
 * 
 * @property {string} entity - Entity name (singular, lowercase)
 * @property {string} entityPlural - Entity name (plural, lowercase)
 * @property {string} entityDisplay - Entity name for display (capitalized)
 * @property {Function} getColumns - Returns column definitions
 * @property {Function} getGuidelines - Returns import guidelines
 * @property {Function} validateData - Validates parsed CSV data
 * @property {Function} prepareForAPI - Prepares validated data for API
 * @property {Function} generateSample - Generates sample CSV content
 * @property {Function} buildLookups - Builds lookup tables for name resolution
 * @property {Function} bulkCreate - API function for bulk creation
 * @property {Object} options - Additional options
 */
export const userCSVConfig = {
  // ==============================|| ENTITY INFO ||============================== //
  
  entity: 'user',
  entityPlural: 'users',
  entityDisplay: 'User',
  entityDisplayPlural: 'Users',
  
  // ==============================|| COLUMN & GUIDELINES ||============================== //
  
  /**
   * Get CSV column definitions
   * @returns {Array<{key: string, label: string, required: boolean}>}
   */
  getColumns: getUserCSVColumns,
  
  /**
   * Get import guidelines for users
   * @returns {Array<string>}
   */
  getGuidelines: getUserCSVGuidelines,
  
  // ==============================|| VALIDATION & PREPARATION ||============================== //
  
  /**
   * Validate parsed CSV data
   * @param {Array} data - Parsed CSV rows
   * @param {Object} lookups - Lookup tables for name resolution
   * @returns {Object} { validRows, invalidRows, stats, allErrors }
   */
  validateData: validateUserCSVData,
  
  /**
   * Prepare validated rows for API submission
   * @param {Array} validatedRows - Rows that passed validation
   * @returns {Array} API-ready payload
   */
  prepareForAPI: prepareUserDataForAPI,
  
  /**
   * Generate sample CSV content
   * @param {Object} lookups - Optional lookup tables for real values
   * @returns {string} CSV content as string
   */
  generateSample: generateSampleCSV,
  
  // ==============================|| LOOKUPS (Entity-Specific) ||============================== //
  
  /**
   * Build lookup tables for name resolution
   * Fetches roles, organizations, teams from API
   * @returns {Promise<Object>} { roles, organizations, teams }
   */
  buildLookups: buildLookups,
  
  // ==============================|| API ENDPOINTS ||============================== //
  
  /**
   * Bulk create API function
   * @param {Array} data - Array of user objects
   * @param {string} mode - 'partial' or 'all_or_nothing'
   * @returns {Promise<Object>} { success, results: { success, failed, skipped } }
   */
  bulkCreate: createBulkUsers,
  
  // ==============================|| OPTIONS ||============================== //
  
  options: {
    /**
     * Batch size for bulk operations
     * Larger batches = faster but more memory
     * Smaller batches = slower but safer
     */
    batchSize: 50,
    
    /**
     * Delay between batches (ms)
     * Prevents overwhelming the API
     */
    batchDelay: 50,
    
    /**
     * Sample CSV filename
     */
    sampleFilename: 'users_import_sample.csv',
    
    /**
     * Enable retry functionality for failed imports
     */
    enableRetry: true,
    
    /**
     * Show success details in import report
     */
    showSuccessDetails: true,
    
    /**
     * Maximum rows to show in data preview
     */
    previewMaxRows: 10,
    
    /**
     * Maximum errors to show in validation summary
     */
    maxErrorsDisplay: 10
  }
};

// ==============================|| DEFAULT EXPORT ||============================== //

export default userCSVConfig;