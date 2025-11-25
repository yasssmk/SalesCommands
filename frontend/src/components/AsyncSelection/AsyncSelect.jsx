// components/AsyncSelection/AsyncSelect.jsx

import PropTypes from 'prop-types';
import { useState, useMemo, useEffect } from 'react';

// material-ui
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import CircularProgress from '@mui/material/CircularProgress';

// lodash
import { debounce } from 'lodash';

/**
 * ✅ ASYNC SELECT - Composant générique pour recherche serveur
 * 
 * Utilisable avec n'importe quel hook API (useGetUsers, useGetRoles, useGetTeams, etc.)
 * 
 * Features:
 * - Debounce automatique (300ms)
 * - Fusion de la valeur actuelle dans les options (mode edit)
 * - Pagination backend (20 résultats par défaut)
 * - Support complet des props MUI Autocomplete
 * 
 * @example
 * // Avec useGetUsers
 * <AsyncSelect
 *   useDataHook={useGetUsers}
 *   dataKey="users"
 *   loadingKey="usersLoading"
 *   getOptionLabel={(user) => `${user.first_name} ${user.last_name}`}
 *   value={selectedUser}
 *   onChange={setSelectedUser}
 *   label="Select User"
 * />
 * 
 * @example
 * // Avec useGetRoles
 * <AsyncSelect
 *   useDataHook={useGetRoles}
 *   dataKey="roles"
 *   loadingKey="rolesLoading"
 *   getOptionLabel={(role) => role.name}
 *   value={selectedRole}
 *   onChange={setSelectedRole}
 *   label="Select Role"
 * />
 */
function AsyncSelect({
  // Hook configuration
  useDataHook,           // Hook à utiliser (ex: useGetUsers)
  dataKey,               // Clé des résultats (ex: 'users')
  loadingKey,            // Clé du loading (ex: 'usersLoading')
  
  // Option formatting
  getOptionLabel,        // Fonction pour formatter le label
  isOptionEqualToValue,  // Fonction pour comparer les options (défaut: par id)
  
  // Value & onChange
  value,                 // Valeur actuelle (objet complet ou null)
  onChange,              // Callback(event, newValue)
  
  // UI customization
  label,                 // Label du champ
  placeholder,           // Placeholder
  disabled,              // Disabled state
  error,                 // Error state
  helperText,            // Helper text
  
  // Advanced
  pageSize = 20,         // Nombre de résultats par recherche
  minSearchLength = 0,   // Longueur min avant recherche (0 = immediate)
  debounceMs = 300,      // Délai de debounce
  filters = {},          // Additional filters to pass to hook
  
  // Pass-through MUI Autocomplete props
  ...autocompleteProps
}) {
  
  // ==================== STATE ====================
  
  const [inputValue, setInputValue] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  
  // ==================== DEBOUNCE ====================
  
  const debouncedSetSearch = useMemo(
    () => debounce((value) => {
      setDebouncedSearch(value);
    }, debounceMs),
    [debounceMs]
  );
  
  useEffect(() => {
    // Si inputValue est trop court, ne pas rechercher
    if (inputValue.length < minSearchLength && inputValue.length > 0) {
      setDebouncedSearch('');
      return;
    }
    
    debouncedSetSearch(inputValue);
    
    // Cleanup
    return () => debouncedSetSearch.cancel();
  }, [inputValue, minSearchLength, debouncedSetSearch]);
  
  // ==================== API CALL ====================
  
  const hookResult = useDataHook({
    page: 1,
    pageSize,
    search: debouncedSearch,
    filters
  });
  
  const data = hookResult[dataKey] || [];
  const loading = hookResult[loadingKey] || false;
  
  // ==================== OPTIONS FUSION ====================
  
  /**
   * Fusionne la valeur actuelle avec les résultats de recherche
   * Garantit que la valeur sélectionnée reste visible même si hors top 20
   */
  const options = useMemo(() => {
    const searchResults = data || [];
    
    // Si value existe ET n'est pas dans les résultats, l'ajouter en premier
    if (value && !searchResults.find(option => {
      const optionId = option?.id || option?.uuid || option;
      const valueId = value?.id || value?.uuid || value;
      return optionId === valueId;
    })) {
      return [value, ...searchResults];
    }
    
    return searchResults;
  }, [data, value]);
  
  // ==================== DEFAULT HANDLERS ====================
  
  const defaultIsOptionEqualToValue = (option, val) => {
    if (!option || !val) return false;
    const optionId = option?.id || option?.uuid;
    const valueId = val?.id || val?.uuid;
    return optionId === valueId;
  };
  
  // ==================== RENDER ====================
  
  return (
    <Autocomplete
      fullWidth
      options={options}
      value={value}
      onChange={onChange}
      inputValue={inputValue}
      onInputChange={(event, newInputValue) => {
        setInputValue(newInputValue);
      }}
      getOptionLabel={getOptionLabel}
      isOptionEqualToValue={isOptionEqualToValue || defaultIsOptionEqualToValue}
      loading={loading}
      disabled={disabled}
      noOptionsText={
        inputValue.length < minSearchLength && inputValue.length > 0
          ? `Type at least ${minSearchLength} characters`
          : 'No results found'
      }
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          placeholder={placeholder}
          error={error}
          helperText={helperText}
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <>
                {loading ? <CircularProgress color="inherit" size={20} /> : null}
                {params.InputProps.endAdornment}
              </>
            ),
          }}
        />
      )}
      {...autocompleteProps}
    />
  );
}

AsyncSelect.propTypes = {
  // Hook configuration
  useDataHook: PropTypes.func.isRequired,
  dataKey: PropTypes.string.isRequired,
  loadingKey: PropTypes.string.isRequired,
  
  // Option formatting
  getOptionLabel: PropTypes.func.isRequired,
  isOptionEqualToValue: PropTypes.func,
  
  // Value & onChange
  value: PropTypes.any,
  onChange: PropTypes.func.isRequired,
  
  // UI customization
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  
  // Advanced
  pageSize: PropTypes.number,
  minSearchLength: PropTypes.number,
  debounceMs: PropTypes.number,
  filters: PropTypes.object
};

export default AsyncSelect;