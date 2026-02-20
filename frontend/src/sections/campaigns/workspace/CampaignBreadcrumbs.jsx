// frontend/src/sections/campaigns/workspace/CampaignBreadcrumbs.jsx
/**
 * Campaign Breadcrumbs builder.
 *
 * Pattern: components/WorkspaceBreadcrumb buildActivityBreadcrumbs
 */

// ==============================|| BUILD CAMPAIGN BREADCRUMBS ||============================== //

/**
 * @param {Object} params
 * @param {string} params.campaignName - Campaign name for last breadcrumb
 * @returns {Array} Breadcrumb items for WorkspaceBreadcrumb
 */
export function buildCampaignBreadcrumbs({ campaignName }) {
  return [
    { label: 'Campaigns', href: '/campaigns' },
    { label: campaignName || 'Campaign' }
  ];
}