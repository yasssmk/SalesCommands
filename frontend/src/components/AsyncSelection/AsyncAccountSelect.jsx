// frontend/src/components/AsyncSelection/AsyncAccountSelect.jsx

import PropTypes from 'prop-types';

// project imports
import AsyncSelect from './AsyncSelect';
import { useGetAccounts } from 'api/admin/accounts';

/**
 * ASYNC ACCOUNT SELECT - Wrapper for account selection
 * 
 * Uses AsyncSelect with pre-configured settings for CompanyAccounts.
 * 
 * Features:
 * - Server-side search (company_name, industry, city, country)
 * - Automatic debounce (300ms)
 * - Displays: "Company Name (City, Country)"
 * - Supports edit mode (current value always visible)
 * 
 * @example
 * // Create mode (value = null)
 * <AsyncAccountSelect
 *   value={null}
 *   onChange={(newAccount) => setSelectedAccount(newAccount)}
 *   label="Parent Company"
 *   placeholder="Search by company name..."
 * />
 * 
 * @example
 * // Edit mode (value = account object)
 * <AsyncAccountSelect
 *   value={account.parent_company}
 *   onChange={(newAccount) => setFieldValue('parent', newAccount)}
 *   label="Parent Company"
 *   excludeIds={[currentAccountId]}
 * />
 */
function AsyncAccountSelect({
  value,
  onChange,
  label = 'Select Account',
  placeholder = 'Search by company name...',
  disabled = false,
  error = false,
  helperText,
  filters = {},
  pageSize = 20,
  excludeIds = [],
  ...props
}) {
  
  /**
   * Format account label for Autocomplete
   * Format: "Company Name (City, Country)"
   */
  const getAccountLabel = (account) => {
    if (!account) return '';
    
    const name = account.company_name || '';
    const city = account.city || '';
    const country = account.country || '';
    
    if (name && city && country) {
      return `${name} (${city}, ${country})`;
    } else if (name && city) {
      return `${name} (${city})`;
    } else if (name && country) {
      return `${name} (${country})`;
    }
    
    return name || 'Unknown Account';
  };

  /**
   * Filter out excluded IDs (e.g., current account when selecting parent)
   */
  const filterOptions = (options) => {
    if (!excludeIds || excludeIds.length === 0) return options;
    return options.filter(opt => !excludeIds.includes(opt.id));
  };
  
  return (
    <AsyncSelect
      useDataHook={useGetAccounts}
      dataKey="accounts"
      loadingKey="accountsLoading"
      getOptionLabel={getAccountLabel}
      filterOptions={filterOptions}
      value={value}
      onChange={onChange}
      label={label}
      placeholder={placeholder}
      disabled={disabled}
      error={error}
      helperText={helperText}
      pageSize={pageSize}
      minSearchLength={0}
      filters={filters}
      {...props}
    />
  );
}

AsyncAccountSelect.propTypes = {
  value: PropTypes.object,
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  filters: PropTypes.object,
  pageSize: PropTypes.number,
  excludeIds: PropTypes.array
};

export default AsyncAccountSelect;