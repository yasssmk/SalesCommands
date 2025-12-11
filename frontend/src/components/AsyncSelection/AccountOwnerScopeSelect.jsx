// frontend/src/components/AsyncSelection/AccountOwnerScopeSelect.jsx

import PropTypes from 'prop-types';
import { useState, useMemo, useCallback } from 'react';

// material-ui
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import CircularProgress from '@mui/material/CircularProgress';
import ListSubheader from '@mui/material/ListSubheader';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';

// icons
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import GlobalOutlined from '@ant-design/icons/GlobalOutlined';

// lodash
import { debounce } from 'lodash';

// api
import { useGetUsers } from 'api/admin/users';

// ==============================|| CONSTANTS ||============================== //

/**
 * Fixed scope options (always at the top)
 */
const SCOPE_OPTIONS = [
  { 
    type: 'scope', 
    value: '', 
    label: 'All accounts',
    icon: GlobalOutlined,
    group: 'Scope'
  },
  { 
    type: 'scope', 
    value: 'mine', 
    label: 'My accounts',
    icon: UserOutlined,
    group: 'Scope'
  },
  { 
    type: 'scope', 
    value: 'team', 
    label: 'My team\'s accounts',
    icon: TeamOutlined,
    group: 'Scope'
  }
];

// ==============================|| ACCOUNT OWNER SCOPE SELECT ||============================== //

/**
 * Combined select for account ownership filtering.
 * 
 * Displays:
 * - Fixed scope options (All, Mine, Team) at the top
 * - Dynamic user list below (with search)
 * 
 * Value format:
 * - { type: 'scope', value: '' | 'mine' | 'team' }
 * - { type: 'user', value: { id, first_name, last_name, email, ... } }
 * 
 * @param {Object} value - Current selection
 * @param {Function} onChange - Callback when selection changes
 * @param {string} label - Input label
 * @param {string} placeholder - Input placeholder
 * @param {boolean} disabled - Disabled state
 * @param {string} size - Input size ('small' | 'medium')
 */
function AccountOwnerScopeSelect({
  value = null,
  onChange,
  label = 'Account Owner',
  placeholder = 'All accounts',
  disabled = false,
  size = 'small',
  ...props
}) {
  // Search state for users
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Fetch users with search
  const { users = [], usersLoading } = useGetUsers({
    page: 1,
    pageSize: 20,
    search: debouncedSearch
  });

  // Debounced search handler
  const debouncedSetSearch = useMemo(
    () => debounce((val) => setDebouncedSearch(val), 300),
    []
  );

  // Handle input change
  const handleInputChange = useCallback((event, newInputValue, reason) => {
    if (reason === 'input') {
      setSearchInput(newInputValue);
      debouncedSetSearch(newInputValue);
    }
  }, [debouncedSetSearch]);

  // Build options list: scopes + users
  const options = useMemo(() => {
    // Convert users to option format
    const userOptions = users.map(user => ({
      type: 'user',
      value: user,
      label: `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email,
      email: user.email,
      group: 'Users'
    }));

    return [...SCOPE_OPTIONS, ...userOptions];
  }, [users]);

  // Get option label for display
  const getOptionLabel = useCallback((option) => {
    if (!option) return '';
    return option.label || '';
  }, []);

  // Check if two options are equal
  const isOptionEqualToValue = useCallback((option, val) => {
    if (!option || !val) return false;
    if (option.type !== val.type) return false;
    
    if (option.type === 'scope') {
      return option.value === val.value;
    }
    
    if (option.type === 'user') {
      return option.value?.id === val.value?.id;
    }
    
    return false;
  }, []);

  // Group by function
  const groupBy = useCallback((option) => option.group, []);

  // Render option
  const renderOption = useCallback((props, option) => {
    const { key, ...otherProps } = props;
    
    // Generate unique key based on type and id/value
    const uniqueKey = option.type === 'scope' 
        ? `scope-${option.value || 'all'}` 
        : `user-${option.value?.id}`;
    
    if (option.type === 'scope') {
        const IconComponent = option.icon;
        return (
        <Box
            component="li"
            key={uniqueKey}
            {...otherProps}
            sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 1.5,
                py: 1,
                color: option.value === '' ? 'text.secondary' : 'text.primary',
                fontStyle: option.value === '' ? 'italic' : 'normal'
            }}
            >
            <IconComponent style={{ fontSize: 16, opacity: 0.7 }} />
            <Typography variant="body2">
                {option.label}
            </Typography>
            </Box>
        );
        }

    // User option
    return (
      <Box
        component="li"
        key={uniqueKey}
        {...otherProps}
        sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', py: 1 }}
      >
        <Typography variant="body2">
          {option.label}
        </Typography>
        {option.email && (
          <Typography variant="caption" color="text.secondary">
            {option.email}
          </Typography>
        )}
      </Box>
    );
  }, []);

  // Render group header
  const renderGroup = useCallback((params) => (
    <li key={params.key}>
      <ListSubheader
        component="div"
        sx={{
          bgcolor: 'grey.100',
          fontWeight: 600,
          fontSize: '0.75rem',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          lineHeight: '32px'
        }}
      >
        {params.group}
      </ListSubheader>
      <ul style={{ padding: 0 }}>{params.children}</ul>
    </li>
  ), []);

  // Handle selection change
  const handleChange = useCallback((event, newValue) => {
    onChange?.(event, newValue);
  }, [onChange]);

  // Filter options (keep all scopes, filter users by search)
  const filterOptions = useCallback((opts, { inputValue }) => {
    // Always show scope options
    const scopes = opts.filter(o => o.type === 'scope');
    
    // Users are already filtered server-side, show all
    const userOpts = opts.filter(o => o.type === 'user');
    
    return [...scopes, ...userOpts];
  }, []);

  return (
    <Autocomplete
      value={value}
      onChange={handleChange}
      inputValue={searchInput}
      onInputChange={handleInputChange}
      options={options}
      getOptionLabel={getOptionLabel}
      isOptionEqualToValue={isOptionEqualToValue}
      groupBy={groupBy}
      renderOption={renderOption}
      renderGroup={renderGroup}
      filterOptions={filterOptions}
      loading={usersLoading}
      disabled={disabled}
      size={size}
      blurOnSelect
      clearOnBlur={false}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          placeholder={placeholder}
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <>
                {usersLoading ? <CircularProgress color="inherit" size={18} /> : null}
                {params.InputProps.endAdornment}
              </>
            )
          }}
        />
      )}
      {...props}
    />
  );
}

AccountOwnerScopeSelect.propTypes = {
  value: PropTypes.shape({
    type: PropTypes.oneOf(['scope', 'user']),
    value: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    label: PropTypes.string
  }),
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  size: PropTypes.oneOf(['small', 'medium'])
};

export default AccountOwnerScopeSelect;