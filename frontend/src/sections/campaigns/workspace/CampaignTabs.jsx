// frontend/src/sections/campaigns/workspace/CampaignTabs.jsx
/**
 * Campaign Workspace — Tab definitions.
 *
 * Pattern: sections/activities/workspace/ActivityTabs.jsx
 */

// ==============================|| CAMPAIGN TABS ||============================== //

export const CAMPAIGN_TABS = [
  { id: 'overview', label: 'Overview', disabled: true },
  { id: 'accounts', label: 'Accounts' },
  { id: 'activities', label: 'Activities' },
  { id: 'members', label: 'Members' }
];

export const DEFAULT_TAB = 'overview';