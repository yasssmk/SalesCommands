// frontend/src/config/formatters.js

import { format, formatDistanceToNow, isDate, parseISO } from 'date-fns';

// Choose a single, consistent display format for the app.
// Feel free to change this once and it will reflect everywhere.
export const DEFAULT_DATETIME_FORMAT = "yyyy-MM-dd HH:mm"; // e.g., 2025-08-16 14:05
export const DEFAULT_DATE_FORMAT = "yyyy-MM-dd";
export const DEFAULT_TIME_FORMAT = "HH:mm";

/**
 * Safely coerce various inputs to a Date.
 * Accepts Date, ISO string, or timestamp (ms).
 */
function toDate(value) {
  if (!value && value !== 0) return null;
  if (isDate(value)) return value;
  if (typeof value === 'number') return new Date(value);
  if (typeof value === 'string') {
    // Try ISO first (backend usually returns ISO strings)
    const parsed = parseISO(value);
    return isNaN(parsed) ? new Date(value) : parsed;
  }
  return null;
}

/**
 * Format date & time with a consistent pattern.
 * Returns fallback (default: '—') if value is falsy or invalid.
 */
export function formatDateTime(value, fallback = '—', pattern = DEFAULT_DATETIME_FORMAT) {
  const d = toDate(value);
  if (!d || isNaN(d)) return fallback;
  try {
    return format(d, pattern);
  } catch {
    return fallback;
  }
}

/**
 * Format date only.
 */
export function formatDateOnly(value, fallback = '—', pattern = DEFAULT_DATE_FORMAT) {
  return formatDateTime(value, fallback, pattern);
}

/**
 * Format time only.
 */
export function formatTimeOnly(value, fallback = '—', pattern = DEFAULT_TIME_FORMAT) {
  return formatDateTime(value, fallback, pattern);
}

/**
 * Human-friendly relative time (e.g., "3 hours ago").
 */
export function formatRelativeTime(value, fallback = '—') {
  const d = toDate(value);
  if (!d || isNaN(d)) return fallback;
  try {
    return formatDistanceToNow(d, { addSuffix: true });
  } catch {
    return fallback;
  }
}
