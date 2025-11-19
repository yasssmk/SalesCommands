// components/AsyncSelection/AsyncUserSelect.jsx

import PropTypes from 'prop-types';

// project imports
import AsyncSelect from './AsyncSelect';
import { useGetUsers } from 'api/admin/users';

/**
 * ✅ ASYNC USER SELECT - Wrapper spécialisé pour sélection d'utilisateurs
 * 
 * Utilise AsyncSelect avec configuration pré-définie pour users
 * 
 * Features:
 * - Recherche serveur (email, first_name, last_name, role__name, team__name)
 * - Debounce automatique (300ms)
 * - Affiche: "FirstName LastName (email, role)"
 * - Support mode edit (valeur actuelle toujours visible)
 * 
 * @example
 * // Mode Create (value = null)
 * <AsyncUserSelect
 *   value={null}
 *   onChange={(newUser) => setSelectedUser(newUser)}
 *   label="Select Manager"
 *   placeholder="Search by name or email..."
 * />
 * 
 * @example
 * // Mode Edit (value = user object)
 * <AsyncUserSelect
 *   value={team.manager}  // {id: 123, first_name: 'John', ...}
 *   onChange={(newUser) => setFormValues({...formValues, manager: newUser})}
 *   label="Manager"
 * />
 */
function AsyncUserSelect({
  value,
  onChange,
  label = 'Select User',
  placeholder = 'Search by name or email...',
  disabled = false,
  error = false,
  helperText,
  ...props
}) {
  
  /**
   * Formatte le label d'un user pour l'Autocomplete
   * Format: "FirstName LastName (email, role)"
   */
  const getUserLabel = (user) => {
    if (!user) return '';
    
    const name = `${user.first_name || ''} ${user.last_name || ''}`.trim();
    const email = user.email || '';
    const role = user.role_name || user.role?.name || '';
    
    if (name && email && role) {
      return `${name} (${email}, ${role})`;
    } else if (name && email) {
      return `${name} (${email})`;
    } else if (email) {
      return email;
    }
    
    return name || 'Unknown User';
  };
  
  return (
    <AsyncSelect
      useDataHook={useGetUsers}
      dataKey="users"
      loadingKey="usersLoading"
      getOptionLabel={getUserLabel}
      value={value}
      onChange={onChange}
      label={label}
      placeholder={placeholder}
      disabled={disabled}
      error={error}
      helperText={helperText}
      pageSize={20}
      minSearchLength={0}
      {...props}
    />
  );
}

AsyncUserSelect.propTypes = {
  value: PropTypes.object,      // User object or null
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  error: PropTypes.bool,
  helperText: PropTypes.string
};

export default AsyncUserSelect;