// frontend/src/sections/territories/TerritorySelector.jsx

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import FormControl from '@mui/material/FormControl';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// icons
import GlobalOutlined from '@ant-design/icons/GlobalOutlined';
import BankOutlined from '@ant-design/icons/BankOutlined';
import ContactsOutlined from '@ant-design/icons/ContactsOutlined';

// api
import { TERRITORY_TYPES } from 'api/territories';

// ==============================|| TERRITORY SELECTOR ||============================== //

/**
 * Territory Selector Component
 * 
 * Dropdown to select the current territory.
 * Phase 1: Simple select with hardcoded territories
 * Future: Add create/edit/delete actions
 */
export default function TerritorySelector({ 
  territories = [], 
  selectedId, 
  onChange,
  disabled = false 
}) {
  
  const selectedTerritory = territories.find(t => t.id === selectedId);

  const handleChange = (event) => {
    onChange?.(event.target.value);
  };

  // Get icon based on territory type
  const getTypeIcon = (type) => {
    if (type === TERRITORY_TYPES.ACCOUNT) {
      return <BankOutlined style={{ fontSize: 16 }} />;
    }
    if (type === TERRITORY_TYPES.CONTACT) {
      return <ContactsOutlined style={{ fontSize: 16 }} />;
    }
    return <GlobalOutlined style={{ fontSize: 16 }} />;
  };

  return (
    <Stack direction="row" spacing={2} alignItems="center">
      <GlobalOutlined style={{ fontSize: 20, color: '#8c8c8c' }} />
      
      <FormControl size="small" sx={{ minWidth: 200 }}>
        <Select
          value={selectedId || ''}
          onChange={handleChange}
          disabled={disabled}
          displayEmpty
          renderValue={(value) => {
            if (!value || !selectedTerritory) {
              return (
                <Typography color="text.secondary">
                  Select territory
                </Typography>
              );
            }
            return (
              <Stack direction="row" spacing={1} alignItems="center">
                {getTypeIcon(selectedTerritory.type)}
                <Typography variant="body1">
                  {selectedTerritory.name}
                </Typography>
              </Stack>
            );
          }}
        >
          {territories.map((territory) => (
            <MenuItem key={territory.id} value={territory.id}>
              <Stack direction="row" spacing={1.5} alignItems="center">
                {getTypeIcon(territory.type)}
                <Box>
                  <Typography variant="body1">
                    {territory.name}
                  </Typography>
                  {territory.description && (
                    <Typography variant="caption" color="text.secondary">
                      {territory.description}
                    </Typography>
                  )}
                </Box>
              </Stack>
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Territory description - shown next to selector */}
      {selectedTerritory?.description && (
        <Typography variant="body2" color="text.secondary" sx={{ display: { xs: 'none', md: 'block' } }}>
          {selectedTerritory.description}
        </Typography>
      )}
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

TerritorySelector.propTypes = {
  territories: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      type: PropTypes.oneOf(['account', 'contact']).isRequired,
      description: PropTypes.string
    })
  ),
  selectedId: PropTypes.string,
  onChange: PropTypes.func,
  disabled: PropTypes.bool
};