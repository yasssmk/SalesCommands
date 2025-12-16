// frontend/src/components/filters/MultiSelectFilter.jsx

import PropTypes from 'prop-types';

// material-ui
import Autocomplete from '@mui/material/Autocomplete';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';

// icons
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import CheckBoxIcon from '@mui/icons-material/CheckBox';

const icon = <CheckBoxOutlineBlankIcon fontSize="small" />;
const checkedIcon = <CheckBoxIcon fontSize="small" />;

// ==============================|| MULTI SELECT FILTER ||============================== //

/**
 * MultiSelectFilter - Reusable multi-select dropdown with chips
 * 
 * Uses MUI Autocomplete with multiple selection.
 * Displays selected values as chips.
 * 
 * @param {Array} options - Array of {value, label} objects
 * @param {Array} value - Array of selected values (strings)
 * @param {Function} onChange - Callback (newValues: string[]) => void
 * @param {string} label - Field label
 * @param {string} placeholder - Placeholder text when empty
 * @param {boolean} disabled - Disable the input
 * @param {boolean} loading - Show loading state
 * @param {string} noOptionsText - Text when no options match
 * @param {string} allLabel - Label for "All" state (e.g., "All types")
 */
function MultiSelectFilter({
  options = [],
  value = [],
  onChange,
  label,
  placeholder = 'Select...',
  disabled = false,
  loading = false,
  noOptionsText = 'No options',
  allLabel = 'All',
  size = 'medium',
  limitTags = 2,
  ...rest
}) {
  // Convert value array to option objects for Autocomplete
  const selectedOptions = options.filter(opt => value.includes(opt.value));

  const handleChange = (event, newValue) => {
    // Extract just the values (strings) from selected options
    const newValues = newValue.map(opt => opt.value);
    onChange?.(newValues);
  };

  return (
    <Autocomplete
      multiple
      id={`multiselect-${label?.toLowerCase().replace(/\s/g, '-') || 'filter'}`}
      options={options}
      disableCloseOnSelect
      getOptionLabel={(option) => option.label || option.value || ''}
      value={selectedOptions}
      onChange={handleChange}
      disabled={disabled}
      loading={loading}
      noOptionsText={noOptionsText}
      limitTags={limitTags}
      size={size}
      isOptionEqualToValue={(option, val) => option.value === val.value}
      renderOption={(props, option, { selected }) => {
        const { key, ...rest } = props;
        return (
          <Box component="li" key={key} {...rest}>
            <Checkbox
              icon={icon}
              checkedIcon={checkedIcon}
              style={{ marginRight: 8 }}
              checked={selected}
            />
            {option.label}
          </Box>
        );
      }}
      renderTags={(tagValue, getTagProps) =>
        tagValue.map((option, index) => {
          const { key, ...tagProps } = getTagProps({ index });
          return (
            <Chip
              key={key}
              label={option.label}
              size="small"
              {...tagProps}
            />
          );
        })
      }
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          placeholder={value.length === 0 ? placeholder : ''}
          InputLabelProps={{ shrink: true }}
        />
      )}
      {...rest}
    />
  );
}

MultiSelectFilter.propTypes = {
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired
    })
  ),
  value: PropTypes.arrayOf(PropTypes.string),
  onChange: PropTypes.func,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  loading: PropTypes.bool,
  noOptionsText: PropTypes.string,
  allLabel: PropTypes.string,
  size: PropTypes.oneOf(['small', 'medium']),
  limitTags: PropTypes.number
};

export default MultiSelectFilter;