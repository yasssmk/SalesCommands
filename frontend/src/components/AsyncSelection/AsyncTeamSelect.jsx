// components/AsyncSelection/AsyncTeamSelect.jsx

import PropTypes from "prop-types";

// project imports
import AsyncSelect from "./AsyncSelect";
import { useGetTeams } from "api/admin/teams";

/**
 * ASYNC TEAM SELECT — specialised wrapper for team selection.
 *
 * Mirrors AsyncUserSelect: server-side search as you type (debounced),
 * paginated results, current value merged so the selection keeps its label.
 * Backend search is TeamViewSet.search_fields = ['name', 'description'].
 *
 * @example
 * <AsyncTeamSelect
 *   value={selectedTeam}                 // team object or null
 *   onChange={(event, team) => setTeam(team)}   // MUI (event, newValue)
 *   label="Team"
 * />
 */
function AsyncTeamSelect({
  value,
  onChange,
  label = "Select Team",
  placeholder = "Search by team name...",
  disabled = false,
  error = false,
  helperText,
  filters = {},
  pageSize = 20,
  ...props
}) {
  const getTeamLabel = (team) => {
    if (!team) return "";
    return team.name || "Unknown Team";
  };

  return (
    <AsyncSelect
      useDataHook={useGetTeams}
      dataKey="teams"
      loadingKey="teamsLoading"
      getOptionLabel={getTeamLabel}
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

AsyncTeamSelect.propTypes = {
  value: PropTypes.object, // team object or null
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  filters: PropTypes.object,
  pageSize: PropTypes.number,
};

export default AsyncTeamSelect;
