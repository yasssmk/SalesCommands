// components/AsyncSelection/AsyncContactSelect.jsx

import PropTypes from 'prop-types';

// project imports
import AsyncSelect from './AsyncSelect';
import { useGetContacts } from 'api/businessData/contacts';

/**
 * ASYNC CONTACT SELECT - Wrapper for contact selection
 * 
 * Uses AsyncSelect with pre-configured settings for Contacts.
 * 
 * Features:
 * - Server-side search (first_name, last_name, email, job_title)
 * - Automatic debounce (300ms)
 * - Displays: "FirstName LastName (job_title)"
 * - Supports edit mode (current value always visible)
 * - Optional account filter for scoped selection
 * 
 * @example
 * // Select from all contacts
 * <AsyncContactSelect
 *   value={null}
 *   onChange={(event, contact) => setSelectedContact(contact)}
 *   placeholder="Search contacts..."
 * />
 * 
 * @example
 * // Select from specific account's contacts only
 * <AsyncContactSelect
 *   value={null}
 *   onChange={(event, contact) => setSelectedContact(contact)}
 *   filters={{ account_id: accountId }}
 *   placeholder="Search account contacts..."
 * />
 */
function AsyncContactSelect({
  value,
  onChange,
  label = '',
  placeholder = 'Search contacts...',
  disabled = false,
  error = false,
  helperText,
  filters = {},
  pageSize = 20,
  excludeIds = [],
  ...props
}) {
  
  /**
   * Format contact label for Autocomplete
   * Format: "FirstName LastName (job_title)" or "FirstName LastName (email)"
   */
  const getContactLabel = (contact) => {
    if (!contact) return '';
    
    const name = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
    const jobTitle = contact.job_title || '';
    const email = contact.email || '';
    
    if (name && jobTitle) {
      return `${name} (${jobTitle})`;
    } else if (name && email) {
      return `${name} (${email})`;
    } else if (name) {
      return name;
    } else if (email) {
      return email;
    }
    
    return 'Unknown Contact';
  };

  /**
   * Filter out excluded IDs (e.g., already selected contacts)
   */
  const filterOptions = (options) => {
    if (!excludeIds || excludeIds.length === 0) return options;
    return options.filter(opt => !excludeIds.includes(opt.id));
  };
  
  return (
    <AsyncSelect
      useDataHook={useGetContacts}
      dataKey="contacts"
      loadingKey="contactsLoading"
      getOptionLabel={getContactLabel}
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

AsyncContactSelect.propTypes = {
  // A single contact object, or an array of them when `multiple` is passed
  // through to the underlying MUI Autocomplete (via AsyncSelect).
  value: PropTypes.oneOfType([PropTypes.object, PropTypes.array]),
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  filters: PropTypes.object,    // { account_id: 'uuid' } to filter by account
  pageSize: PropTypes.number,
  excludeIds: PropTypes.array   // IDs to exclude from results
};

export default AsyncContactSelect;