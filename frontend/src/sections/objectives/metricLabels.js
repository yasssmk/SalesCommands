// frontend/src/sections/objectives/metricLabels.js
//
// The five canonical Sales metrics (backend MetricKey). Values are the stable
// identifiers sent to / received from the API; labels are the human-readable
// display strings; `monetary` marks the two value metrics (amount formatting).
//
// There were six. LEADS was removed with its backend metric (PO): it counted a
// third population — decision cycles carrying a scheduled-meeting activity —
// that is neither a cycle count nor a meeting count. `metricLabel` falls back
// to the raw value, so an objective stored under the retired key still renders
// its identifier instead of an empty cell.

export const METRICS = [
  { value: 'DECISION_CYCLES', label: 'Decision cycles', monetary: false },
  { value: 'MEETINGS', label: 'Meetings', monetary: false },
  { value: 'NEW_LOGOS', label: 'New logos', monetary: false },
  { value: 'PIPELINE_VALUE', label: 'Pipeline value', monetary: true },
  { value: 'REVENUE_WON', label: 'Won value', monetary: true },
];

const BY_VALUE = METRICS.reduce((acc, m) => {
  acc[m.value] = m;
  return acc;
}, {});

export function metricLabel(value) {
  return BY_VALUE[value]?.label || value || '';
}

export function isMonetaryMetric(value) {
  return Boolean(BY_VALUE[value]?.monetary);
}
