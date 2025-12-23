// frontend/src/sections/territories/workspace/TerritoryTabs.jsx

'use client';

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Skeleton from '@mui/material/Skeleton';

// ==============================|| TAB CONFIGURATION ||============================== //

export const WORKSPACE_TABS = [
  { id: 'summary', label: 'Summary' },
  { id: 'list', label: 'List' },
  { id: 'activities', label: 'Activities' }
];

export const DEFAULT_TAB = 'list';

// ==============================|| TERRITORY TABS - LOADING ||============================== //

function TerritoryTabsSkeleton() {
  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
      <Skeleton variant="rectangular" width="100%" height={48} />
    </Box>
  );
}

// ==============================|| TERRITORY TABS ||============================== //

/**
 * Territory Tabs Component
 * 
 * Navigation tabs for the Territory Workspace:
 * - Summary: Territory description and filters (placeholder)
 * - List: Accounts in this territory
 * - Activities: Activity history (placeholder)
 * 
 * @param {Object} props
 * @param {string} props.activeTab - Currently active tab ID
 * @param {Function} props.onTabChange - Callback when tab changes (receives new tab ID)
 * @param {boolean} props.loading - Loading state
 */
export default function TerritoryTabs({ activeTab, onTabChange, loading }) {
  // ==============================|| LOADING STATE ||============================== //

  if (loading) {
    return <TerritoryTabsSkeleton />;
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
        aria-label="Territory workspace tabs"
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
            id={`territory-tab-${tab.id}`}
            aria-controls={`territory-tabpanel-${tab.id}`}
          />
        ))}
      </Tabs>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

TerritoryTabs.propTypes = {
  activeTab: PropTypes.string,
  onTabChange: PropTypes.func.isRequired,
  loading: PropTypes.bool
};