// frontend/src/components/filters/OwnerScopeTabs.jsx

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';

// project imports
import { OWNER_SCOPES } from 'hooks/useOwnerScope';

// ==============================|| SCOPE LABELS ||============================== //

const SCOPE_LABELS = {
  [OWNER_SCOPES.MINE]: 'Mine',
  [OWNER_SCOPES.TEAM]: 'My Team',
  [OWNER_SCOPES.ALL]: 'All'
};

// ==============================|| OWNER SCOPE TABS ||============================== //

/**
 * OwnerScopeTabs - Tab navigation for owner scope filtering
 * 
 * Displays tabs for filtering by owner scope (Mine, My Team, All).
 * Background matches page background for visual separation from content card.
 * 
 * @param {string} value - Current scope value ('mine' | 'team' | 'all')
 * @param {Function} onChange - Callback when scope changes
 * @param {Array} visibleOptions - Array of visible scope options based on user role
 */
export default function OwnerScopeTabs({ value, onChange, visibleOptions = [] }) {

  // ==============================|| HANDLERS ||============================== //

  const handleChange = (event, newValue) => {
    onChange?.(newValue);
  };

  // ==============================|| RENDER ||============================== //

  // Don't render if only one option
  if (visibleOptions.length <= 1) {
    return null;
  }

  return (
    <Box
      sx={{
        width: '100%',
        bgcolor: 'background.default',
        borderBottom: 1,
        borderColor: 'divider',
        mb: 3
      }}
    >
      <Tabs
        value={value}
        onChange={handleChange}
        aria-label="Owner scope filter"
        sx={{
          minHeight: 42,
          '& .MuiTab-root': {
            minHeight: 42,
            textTransform: 'none',
            fontWeight: 500,
            fontSize: '0.875rem',
            px: 2,
            py: 1
          },
          '& .MuiTabs-indicator': {
            height: 2
          }
        }}
      >
        {visibleOptions.map((scope) => (
          <Tab
            key={scope}
            value={scope}
            label={SCOPE_LABELS[scope]}
            id={`owner-scope-tab-${scope}`}
            aria-controls={`owner-scope-tabpanel-${scope}`}
          />
        ))}
      </Tabs>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

OwnerScopeTabs.propTypes = {
  value: PropTypes.oneOf(Object.values(OWNER_SCOPES)).isRequired,
  onChange: PropTypes.func.isRequired,
  visibleOptions: PropTypes.arrayOf(
    PropTypes.oneOf(Object.values(OWNER_SCOPES))
  ).isRequired
};