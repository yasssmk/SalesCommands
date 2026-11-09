// components/AsyncSelection/AsyncContactSelect.jsx

import PropTypes from 'prop-types';
import { useMemo } from 'react';

// project imports
import AsyncSelect from './AsyncSelect';
import { useGetContacts } from 'api/businessData/contacts';
import { useGetDCStakeholders } from 'api/accounts/decisionCycles';

// Sprint « Cycle de vie des contacts », 7d-1 — opt-in (prop
// stakeholdersCycleId): the same list also offers the NON-converted
// stakeholders of a decision cycle, both searched on the server, with no
// visible distinction. A stakeholder option carries _kind: 'stakeholder'; a
// converted stakeholder is offered once, under its contact (the contacts
// search). Without the prop: the standard behaviour, untouched.
const stakeholderLabel = (x) => x.display_name || x.full_name || x.department?.name || '';

function useContactsWithStakeholders({ filters = {}, ...options }) {
  const { stakeholders_cycle_id: cycleId, ...contactFilters } = filters;
  const contactsResult = useGetContacts({ ...options, filters: contactFilters });
  const { stakeholders, stakeholdersLoading } = useGetDCStakeholders(cycleId || null, {
    search: options.search || '',
    converted: false,
  });
  return useMemo(() => {
    const rows = (stakeholders || [])
      .filter((x) => !x.contact)
      .map((x) => ({ ...x, _kind: 'stakeholder' }));
    const contacts = contactsResult.contacts || [];
    return {
      ...contactsResult,
      contacts: rows.length ? [...contacts, ...rows] : contacts,
      contactsLoading: Boolean(contactsResult.contactsLoading || stakeholdersLoading),
    };
  }, [contactsResult, stakeholders, stakeholdersLoading]);
}

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
  stakeholdersCycleId,
  ...props
}) {
  // 7d-1: defined (an id, or null without a cycle) -> contacts + stakeholders.
  const withStakeholders = stakeholdersCycleId !== undefined;

  
  /**
   * Format contact label for Autocomplete
   * Format: "FirstName LastName (job_title)" or "FirstName LastName (email)"
   */
  const getContactLabel = (contact) => {
    if (!contact) return '';
    if (contact._kind === 'stakeholder') return stakeholderLabel(contact);
    
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
      useDataHook={withStakeholders ? useContactsWithStakeholders : useGetContacts}
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
      filters={withStakeholders ? { ...filters, stakeholders_cycle_id: stakeholdersCycleId } : filters}
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
  excludeIds: PropTypes.array,  // IDs to exclude from results
  // 7d-1: also offer the non-converted stakeholders of this decision cycle
  // (null: none — the account contacts only); undefined: standard behaviour.
  stakeholdersCycleId: PropTypes.string
};

export default AsyncContactSelect;