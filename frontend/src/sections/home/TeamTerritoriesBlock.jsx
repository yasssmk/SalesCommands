// frontend/src/sections/home/TeamTerritoriesBlock.jsx

'use client';

import PropTypes from 'prop-types';

import TeamAggregateBlock from './TeamAggregateBlock';

// ==============================|| TEAM TERRITORIES BLOCK — manager aggregate ||============================== //
//
// The compact territory-coverage "by team" view (territory_progress_by_team). A
// thin configuration of the shared TeamAggregateBlock: title only, NO "counts
// once" note. A territory has one owner (no executor), so it lands in exactly one
// team row and the global IS the sum of the rows — a "counts once" note would be
// false here (unlike campaigns). Rows are queue-framed ("X accounts to go") — a
// team's uncovered accounts are its actionable backlog.

export default function TeamTerritoriesBlock({ result = null, loading = false }) {
  return <TeamAggregateBlock title="Team territories" result={result} loading={loading} />;
}

TeamTerritoriesBlock.propTypes = {
  result: PropTypes.object,
  loading: PropTypes.bool,
};
