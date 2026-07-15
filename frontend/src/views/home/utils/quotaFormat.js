// frontend/src/views/home/utils/quotaFormat.js

// Shared quota-attainment display helpers, used by both the Rep "Where I am"
// block and the Manager per-member quota cards.

// Revenue target types are money; conversion is a rate; the rest are counts.
const MONEY_TYPES = new Set(['closed_won', 'pipeline']);

export function unitFor(targetType) {
  if (MONEY_TYPES.has(targetType)) return '$';
  if (targetType === 'conversion_rate') return '%';
  return '';
}

export function labelForType(targetType) {
  if (!targetType) return 'Quota';
  return targetType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function fmtVal(n, unit) {
  const v = Math.round((Number(n) || 0) * 100) / 100;
  if (unit === '$') return `$${v.toLocaleString()}`;
  return `${v}${unit}`;
}
