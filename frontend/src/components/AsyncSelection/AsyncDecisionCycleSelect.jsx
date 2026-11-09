// components/AsyncSelection/AsyncDecisionCycleSelect.jsx
//
// Sprint « Cycle de vie des contacts », 8d-2 — ASYNC DECISION CYCLE SELECT: a
// thin wrapper of AsyncSelect (the model of AsyncContactSelect /
// AsyncAccountSelect) for choosing a decision cycle: a server search on the
// OPEN cycles (outcome IS NULL — the server twin of DecisionCycleCardsList's
// `!c.outcome`) of one account, newest update first (ordering=-updated_at),
// 20 per page, the cycle's name as label.
//
// @example
// <AsyncDecisionCycleSelect
//   accountId={accountId}
//   value={null}
//   onChange={(event, cycle) => setCycle(cycle)}
//   placeholder="Search decision cycles..."
// />

import PropTypes from 'prop-types';

// project imports
import AsyncSelect from './AsyncSelect';
import { useGetDecisionCycles } from 'api/accounts/decisionCycles';

function AsyncDecisionCycleSelect({
  accountId,
  value,
  onChange,
  label = '',
  placeholder = 'Search decision cycles...',
  disabled = false,
  error = false,
  helperText,
  pageSize = 20,
  ...props
}) {
  return (
    <AsyncSelect
      useDataHook={useGetDecisionCycles}
      dataKey="cycles"
      loadingKey="cyclesLoading"
      getOptionLabel={(cycle) => cycle?.name || ''}
      value={value}
      onChange={onChange}
      label={label}
      placeholder={placeholder}
      disabled={disabled}
      error={error}
      helperText={helperText}
      pageSize={pageSize}
      minSearchLength={0}
      filters={{ account: accountId, outcome__isnull: true }}
      ordering="-updated_at"
      {...props}
    />
  );
}

AsyncDecisionCycleSelect.propTypes = {
  /** The account whose open cycles are offered. */
  accountId: PropTypes.string,
  value: PropTypes.object,
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  pageSize: PropTypes.number,
};

export default AsyncDecisionCycleSelect;
