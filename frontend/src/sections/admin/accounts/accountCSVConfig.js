// frontend/src/sections/admin/accounts/accountCSVConfig.js

/**
 * CSV Import Configuration for Accounts
 * 
 * Centralizes all account-specific CSV import settings:
 * - Column definitions
 * - Validation rules
 * - Guidelines for users
 * - API endpoints
 * - Data preparation logic
 */

// Validation & Preparation
import {
  getAccountCSVColumns,
  getAccountCSVGuidelines,
  validateAccountCSVData,
  prepareAccountDataForAPI,
  generateSampleCSV
} from './AccountCSVValidation';

// Resolvers (entity-specific)
import { buildLookups } from './resolvers';

// API
import { bulkCreateAccounts } from 'api/admin/accounts';

// ==============================|| ACCOUNT CSV IMPORT CONFIGURATION ||============================== //

export const accountCSVConfig = {
  // ==============================|| ENTITY INFO ||============================== //
  
  entity: 'account',
  entityPlural: 'accounts',
  entityDisplay: 'Account',
  entityDisplayPlural: 'Accounts',
  identifierField: { key: 'company_name', label: 'Company Name' },
  
  // ==============================|| COLUMN & GUIDELINES ||============================== //
  
  /**
   * Get CSV column definitions
   * @returns {Array<{key: string, label: string, required: boolean}>}
   */
  getColumns: getAccountCSVColumns,
  
  /**
   * Get import guidelines for accounts
   * @returns {Array<string>}
   */
  getGuidelines: getAccountCSVGuidelines,
  
  // ==============================|| VALIDATION & PREPARATION ||============================== //
  
  /**
   * Validate parsed CSV data
   * @param {Array} data - Parsed CSV rows
   * @param {Object} lookups - Lookup tables for name resolution
   * @returns {Object} { validRows, invalidRows, stats, allErrors }
   */
  validateData: validateAccountCSVData,
  
  /**
   * Prepare validated rows for API submission
   * @param {Array} validatedRows - Rows that passed validation
   * @returns {Array} API-ready payload
   */
  prepareForAPI: prepareAccountDataForAPI,
  
  /**
   * Generate sample CSV content
   * @param {Object} lookups - Optional lookup tables for real values
   * @returns {string} CSV content as string
   */
  generateSample: generateSampleCSV,
  
  // ==============================|| LOOKUPS (Entity-Specific) ||============================== //
  
  /**
   * Build lookup tables for name resolution
   * Fetches types, classifications, users from API
   * @returns {Promise<Object>} { types, classifications, users }
   */
  buildLookups: buildLookups,
  
  // ==============================|| API ENDPOINTS ||============================== //
  
  /**
   * Bulk create API function
   * @param {Array} data - Array of account objects
   * @param {string} mode - 'partial' or 'strict'
   * @returns {Promise<Object>} { success, results: { success, failed, skipped } }
   */
  bulkCreate: bulkCreateAccounts,
  
  // ==============================|| OPTIONS ||============================== //
  
  options: {
    /**
     * Batch size for bulk operations
     */
    batchSize: 50,
    
    /**
     * Delay between batches (ms)
     */
    batchDelay: 50,
    
    /**
     * Sample CSV filename
     */
    sampleFilename: 'accounts_import_sample.csv',
    
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

export default accountCSVConfig;