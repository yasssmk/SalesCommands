// frontend/src/config/features.js

/**
 * CENTRALIZED FEATURE FLAGS CONFIGURATION
 * 
 * This file manages all feature toggles for the application.
 * Use these flags to control the visibility and availability of WIP features.
 * 
 * ENVIRONMENTS:
 * - Development: Show disabled WIP items with "Coming Soon" redirects
 * - Production: Hide all WIP items completely
 * 
 * USAGE:
 * import { FEATURES, isFeatureEnabled } from 'config/features';
 */

// ==============================|| ENVIRONMENT DETECTION ||============================== //

const isDevelopment = process.env.NODE_ENV === 'development';
const isProduction = process.env.NODE_ENV === 'production';

// Override from environment variables (optional)
const showWipOverride = process.env.NEXT_PUBLIC_SHOW_WIP === 'true';

// ==============================|| FEATURE FLAGS ||============================== //

/**
 * Main feature flags object
 * Add new features here as they are developed
 */
export const FEATURES = {
  // Global WIP visibility control
  SHOW_WIP_ITEMS: isDevelopment || showWipOverride,
  
  // ============================================
  // DASHBOARD
  // ============================================
  DASHBOARD: false, // Main dashboard - Coming soon
  
  // ============================================
  // GO-TO-MARKET FEATURES
  // ============================================
  ACTION_CENTER: false,    // Workboard/Action center - Coming soon
  TERRITORIES: true,       // Territory management - Active
  CAMPAIGNS: false,        // Campaign management - Coming soon
  SALES_PLAN: false,       // Sales planning - Coming soon
  
  // ============================================
  // BUSINESS DATA FEATURES
  // ============================================
  ACCOUNT_MANAGEMENT: true,   // Account CRUD - Active
  CONTACTS_MANAGEMENT: true, // Contact management - Coming soon
  PRODUCTS_MANAGEMENT: false, // Product catalog - Coming soon
  
  // ============================================
  // ADMINISTRATION FEATURES
  // ============================================
  USER_MANAGEMENT: true,         // User CRUD - Active
  TEAM_MANAGEMENT: true,         // Team management - Active
  ROLES_PERMISSIONS: true,       // Roles & permissions - Active
  
  // ============================================
  // SYSTEM FEATURES (future)
  // ============================================
  AUDIT_LOGS: false,
  API_KEYS: false,
  INTEGRATIONS: false,
  WEBHOOKS: false,
};
// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Check if a feature is enabled
 * @param {string} featureName - Name of the feature from FEATURES object
 * @returns {boolean} Whether the feature is enabled
 */
export const isFeatureEnabled = (featureName) => {
  return FEATURES[featureName] === true;
};

/**
 * Check if a feature should be visible (even if disabled)
 * @param {string} featureName - Name of the feature from FEATURES object
 * @returns {boolean} Whether to show the feature (possibly disabled)
 */
export const isFeatureVisible = (featureName) => {
  if (FEATURES[featureName] === true) return true;
  return FEATURES.SHOW_WIP_ITEMS;
};

/**
 * Get the URL for a feature (either real or coming-soon)
 * @param {string} featureName - Name of the feature
 * @param {string} realUrl - The actual URL when feature is ready
 * @param {string} section - Section name for coming-soon context
 * @returns {string} URL to use
 */
export const getFeatureUrl = (featureName, realUrl, section = 'app') => {
  if (isFeatureEnabled(featureName)) {
    return realUrl;
  }
  const feature = featureName.toLowerCase().replace(/_/g, '-');
  return `/coming-soon-wip?feature=${feature}&section=${section}`;
};

/**
 * Get feature status for display
 * @param {string} featureName - Name of the feature
 * @returns {object} Status object with state and message
 */
export const getFeatureStatus = (featureName) => {
  const enabled = isFeatureEnabled(featureName);
  const visible = isFeatureVisible(featureName);
  
  if (enabled) {
    return {
      state: 'ready',
      message: null,
      disabled: false,
      className: 'feature-ready'
    };
  }
  
  if (visible) {
    return {
      state: 'wip',
      message: 'Coming soon',
      disabled: true,
      className: 'feature-wip'
    };
  }
  
  return {
    state: 'hidden',
    message: null,
    disabled: true,
    className: 'feature-hidden'
  };
};

// ==============================|| DEVELOPMENT HELPERS ||============================== //

/**
 * Log all feature states (development only)
 */
export const logFeatureStates = () => {
  if (!isDevelopment) return;
  
  console.group('🚀 Feature Flags Status');
  Object.entries(FEATURES).forEach(([key, value]) => {
    const emoji = value ? '✅' : '🚧';
    console.log(`${emoji} ${key}: ${value}`);
  });
  console.groupEnd();
};

// Auto-log in development on module load
if (isDevelopment) {
  console.log('🔧 Feature flags loaded - call window.logFeatureStates() to see all flags');
  
  // Expose development helpers to window for console access
  if (typeof window !== 'undefined') {
    window.logFeatureStates = logFeatureStates;
    window.FEATURES = FEATURES;
    window.isFeatureEnabled = isFeatureEnabled;
    
    // Log initial state
    console.log('💡 Development helpers available:');
    console.log('  - window.logFeatureStates() : Show all feature flags');
    console.log('  - window.FEATURES : Access feature flags object');
    console.log('  - window.isFeatureEnabled(name) : Check if feature is enabled');
  }
}

export default FEATURES;