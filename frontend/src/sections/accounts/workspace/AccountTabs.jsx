// src/sections/accounts/workspace/AccountTabs.jsx

'use client';

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Skeleton from '@mui/material/Skeleton';

// ==============================|| TAB CONFIGURATION ||============================== //

export const WORKSPACE_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'decision-cycle', label: 'Decision Cycle' },
  { id: 'activities', label: 'Activities' },
  { id: 'contacts', label: 'Contacts' },
  { id: 'signals', label: 'Signals' }
];

export const DEFAULT_TAB = 'overview';

// ==============================|| ACCOUNT TABS - LOADING ||============================== //

function AccountTabsSkeleton() {
  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
      <Skeleton variant="rectangular" width="100%" height={48} />
    </Box>
  );
}

// ==============================|| ACCOUNT TABS ||============================== //

/**
 * Account Tabs Component
 * 
 * Navigation tabs for the Account Workspace:
 * - Summary: Overview and key information
 * - Buying Process: Steps and stakeholders
 * - Activities: Account activities history
 * - Contacts: Account contacts
 * - Signals: Alerts and signals
 * 
 * @param {Object} props
 * @param {string} props.activeTab - Currently active tab ID
 * @param {Function} props.onTabChange - Callback when tab changes (receives new tab ID)
 * @param {boolean} props.loading - Loading state
 */
export default function AccountTabs({ activeTab, onTabChange, loading }) {
  // ==============================|| LOADING STATE ||============================== //

  if (loading) {
    return <AccountTabsSkeleton />;
  }

  // ==============================|| HANDLERS ||============================== //

  const handleChange = (event, newValue) => {
    if (onTabChange) {
      onTabChange(newValue);
    }
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
      <Tabs
        value={activeTab || DEFAULT_TAB}
        onChange={handleChange}
        aria-label="Account workspace tabs"
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        sx={{
          minHeight: 48,
          '& .MuiTab-root': {
            minHeight: 48,
            textTransform: 'none',
            fontWeight: 500,
            fontSize: '0.875rem',
            px: 2
          },
          '& .MuiTabs-indicator': {
            height: 2
          }
        }}
      >
        {WORKSPACE_TABS.map((tab) => (
          <Tab
            key={tab.id}
            value={tab.id}
            label={tab.label}
            id={`account-tab-${tab.id}`}
            aria-controls={`account-tabpanel-${tab.id}`}
          />
        ))}
      </Tabs>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

AccountTabs.propTypes = {
  activeTab: PropTypes.string,
  onTabChange: PropTypes.func.isRequired,
  loading: PropTypes.bool
};