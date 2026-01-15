// frontend/src/sections/accounts/decision-cycles/DecisionStepTabs.jsx

'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Badge from '@mui/material/Badge';

// ==============================|| DECISION STEP TABS CONFIG ||============================== //

export const DECISION_STEP_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'activities', label: 'Activities' },
  { id: 'contacts', label: 'Contacts' },
  { id: 'signals', label: 'Signals', disabled: true },
  { id: 'ai-prep', label: 'AI Preparation', disabled: true }
];

export const DEFAULT_TAB = 'overview';

// ==============================|| DECISION STEP TABS ||============================== //

/**
 * Decision Step workspace tabs component
 * 
 * Tabs:
 * - Overview: Step details, completeness score, manager notes
 * - Activities: Linked activities list
 * - Contacts: Related contacts
 * - Signals: (Phase 3 - disabled)
 * - AI Preparation: (Phase 3 - disabled)
 * 
 * @param {string} activeTab - Currently active tab id
 * @param {function} onTabChange - Callback when tab changes
 * @param {object} step - Step data (for badge counts)
 */
export default function DecisionStepTabs({ activeTab, onTabChange, step }) {
  const handleChange = (event, newValue) => {
    onTabChange(newValue);
  };

  // Get activity count for badge
  const activityCount = step?.activities?.length || step?.activity_count || 0;
  
  // Get contact count for badge
  const contactCount = step?.step_contacts?.length || 0;

  // Render tab label with optional badge
  const renderTabLabel = (tab) => {
    if (tab.id === 'activities' && activityCount > 0) {
      return (
        <Badge badgeContent={activityCount} color="primary" max={99}>
          {tab.label}
        </Badge>
      );
    }
    if (tab.id === 'contacts' && contactCount > 0) {
      return (
        <Badge badgeContent={contactCount} color="secondary" max={99}>
          {tab.label}
        </Badge>
      );
    }
    return tab.label;
  };

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
      <Tabs
        value={activeTab}
        onChange={handleChange}
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        aria-label="decision step workspace tabs"
      >
        {DECISION_STEP_TABS.map((tab) => (
          <Tab
            key={tab.id}
            value={tab.id}
            label={renderTabLabel(tab)}
            id={`decision-step-tab-${tab.id}`}
            aria-controls={`decision-step-tabpanel-${tab.id}`}
            disabled={tab.disabled}
            sx={tab.disabled ? { opacity: 0.5 } : undefined}
          />
        ))}
      </Tabs>
    </Box>
  );
}

DecisionStepTabs.propTypes = {
  activeTab: PropTypes.string.isRequired,
  onTabChange: PropTypes.func.isRequired,
  step: PropTypes.object
};
