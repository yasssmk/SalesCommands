// frontend/src/sections/home/TeamCampaignsBlock.jsx

'use client';

import PropTypes from 'prop-types';

import TeamAggregateBlock from './TeamAggregateBlock';

// ==============================|| TEAM CAMPAIGNS BLOCK — manager aggregate ||============================== //
//
// The compact campaign "by team" view (campaign_progress_by_team). A thin
// configuration of the shared TeamAggregateBlock: title + the "counts once"
// note, because a campaign owned by one team and run by another lands in BOTH
// team rows but counts ONCE globally — so the global is not the sum of the rows.

const GLOBAL_TOOLTIP =
  'Shared campaigns (owned by one team, run by another) count once here, so the global is not the sum of the team rows.';

const GLOBAL_NOTE = { caption: 'Shared campaigns count once', tooltip: GLOBAL_TOOLTIP };

export default function TeamCampaignsBlock({ result = null, loading = false }) {
  return (
    <TeamAggregateBlock
      title="Team campaigns"
      result={result}
      loading={loading}
      emptyText="No active campaigns."
      globalNote={GLOBAL_NOTE}
    />
  );
}

TeamCampaignsBlock.propTypes = {
  result: PropTypes.object,
  loading: PropTypes.bool,
};
