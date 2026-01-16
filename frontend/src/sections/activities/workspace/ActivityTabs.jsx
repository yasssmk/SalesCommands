'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';

// ==============================|| ACTIVITY TABS CONFIG ||============================== //

export const ACTIVITY_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'preparation', label: 'Preparation' },
  { id: 'outcome', label: 'Outcome' },
  { id: 'transcript', label: 'Transcript' },
  { id: 'signals', label: 'Signals' }
];

export const DEFAULT_TAB = 'overview';

// ==============================|| ACTIVITY TABS ||============================== //

export default function ActivityTabs({ activeTab, onTabChange }) {
  const handleChange = (event, newValue) => {
    onTabChange(newValue);
  };

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
      <Tabs
        value={activeTab}
        onChange={handleChange}
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        aria-label="activity workspace tabs"
      >
        {ACTIVITY_TABS.map((tab) => (
          <Tab
            key={tab.id}
            value={tab.id}
            label={tab.label}
            id={`activity-tab-${tab.id}`}
            aria-controls={`activity-tabpanel-${tab.id}`}
          />
        ))}
      </Tabs>
    </Box>
  );
}

ActivityTabs.propTypes = {
  activeTab: PropTypes.string.isRequired,
  onTabChange: PropTypes.func.isRequired
};
