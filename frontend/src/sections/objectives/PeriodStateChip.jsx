// frontend/src/sections/objectives/PeriodStateChip.jsx
//
// Period-state chip for an objective, driven by the API's derived `state`
// (PAST / CURRENT / FUTURE). Colours come from the theme (MUI Chip `color`),
// never a literal. Mirrors the SignalStatusChip config pattern.

import PropTypes from 'prop-types';
import Chip from '@mui/material/Chip';

const STATE_CONFIG = {
  PAST: { color: 'default', label: 'Past' },
  CURRENT: { color: 'success', label: 'Current' },
  FUTURE: { color: 'info', label: 'Future' },
};

export default function PeriodStateChip({ state, size = 'small', ...rest }) {
  const config = STATE_CONFIG[state];
  if (!config) return null;
  return <Chip size={size} variant="light" color={config.color} label={config.label} {...rest} />;
}

PeriodStateChip.propTypes = {
  state: PropTypes.oneOf(['PAST', 'CURRENT', 'FUTURE']),
  size: PropTypes.string,
};
