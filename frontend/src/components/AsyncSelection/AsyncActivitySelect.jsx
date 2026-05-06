// frontend/src/components/AsyncSelection/AsyncActivitySelect.jsx
/**
 * ASYNC ACTIVITY SELECT — Wrapper for activity selection.
 *
 * Uses AsyncSelect with pre-configured settings for Activities.
 *
 * Features:
 *   - Server-side search (typically by subject / type / date on the backend)
 *   - Automatic debounce (300ms, inherited from AsyncSelect)
 *   - Displays: "<Type> — <Date> — <Subject|Contact>"
 *   - Stable React keys via `getOptionKey={activity.id}` — composite
 *     labels are not unique enough (two distinct activities can share
 *     the same "<Type> — <Date> — <Subject>" tuple), and MUI's default
 *     fallback to `getOptionLabel` for the key would trigger React's
 *     "Encountered two children with the same key" warning. Passing
 *     activity.id (always unique) eliminates the collision.
 *   - Supports edit mode (current value always visible even if out of page 1)
 *   - Account-scoped filtering via `filters={{ account_id }}` — REQUIRED
 *     when used inside a signal form to prevent cross-account data leakage.
 *
 * @example
 * // Scoped to a specific account (recommended in signal forms)
 * <AsyncActivitySelect
 *   value={formik.values.source_activity}
 *   onChange={(_e, activity) =>
 *     formik.setFieldValue('source_activity', activity)
 *   }
 *   filters={{ account_id: accountId }}
 *   label="Source Activity *"
 * />
 *
 * @example
 * // Global (no account scope — all activities visible to the user)
 * <AsyncActivitySelect
 *   value={selectedActivity}
 *   onChange={(_e, activity) => setSelectedActivity(activity)}
 *   label="Activity"
 * />
 */

import PropTypes from "prop-types";

// project imports
import AsyncSelect from "./AsyncSelect";
import { useGetActivities } from "api/accounts/activities";

// ==============================|| HELPERS ||============================== //

/**
 * Format an activity label for the Autocomplete option.
 *
 * Priority order — fallbacks chosen to always produce something readable:
 *   1. "<Type> — <Date> — <Subject>"  when subject present
 *   2. "<Type> — <Date> — <Contact>"  when contact name resolvable
 *   3. "<Type> — <Date>"              bare minimum
 *   4. "Unknown Activity"             absolute last resort
 *
 * Date preference — we want the "when did this happen" semantic date, not
 * the created_at audit date. Order reflects that:
 *   completed_at > scheduled_date > due_date > created_at
 */
function getActivityLabel(activity) {
  if (!activity) return "";

  // --- Type display ---
  // Backend returns `activity_type_display` on detail serializers; list
  // serializers may only have `activity_type` (raw enum value). We try the
  // human label first, then fall back to the raw value.
  const typeLabel =
    activity.activity_type_display || activity.activity_type || "Activity";

  // --- Date ---
  const rawDate =
    activity.completed_at ||
    activity.scheduled_date ||
    activity.due_date ||
    activity.created_at;

  let dateStr = "";
  if (rawDate) {
    try {
      // Display ISO yyyy-mm-dd — locale-independent, compact, sortable.
      // If the backend returns a full ISO timestamp, take the date portion.
      dateStr = new Date(rawDate).toISOString().slice(0, 10);
    } catch {
      dateStr = String(rawDate).slice(0, 10);
    }
  }

  // --- Detail (subject or primary contact name) ---
  const subject = activity.subject || activity.title;
  let detail = subject;
  if (!detail) {
    // Try to resolve a contact name from various shapes the API may return.
    const contact =
      activity.primary_contact || activity.contact || activity.source_contact;
    if (contact) {
      const name =
        `${contact.first_name || ""} ${contact.last_name || ""}`.trim();
      if (name) detail = name;
    }
  }

  // --- Assemble ---
  const parts = [typeLabel];
  if (dateStr) parts.push(dateStr);
  if (detail) parts.push(detail);

  const label = parts.join(" — ");
  return label || "Unknown Activity";
}

// ==============================|| ASYNC ACTIVITY SELECT ||============================== //

function AsyncActivitySelect({
  value,
  onChange,
  label = "Activity",
  placeholder = "Search activities…",
  disabled = false,
  error = false,
  helperText,
  filters = {},
  pageSize = 20,
  excludeIds = [],
  ...props
}) {
  /**
   * Filter out excluded IDs (e.g., activities already linked elsewhere).
   * Applied AFTER server-side filtering — this is purely UI-level dedup.
   */
  const filterOptions = (options) => {
    if (!excludeIds || excludeIds.length === 0) return options;
    return options.filter((opt) => !excludeIds.includes(opt.id));
  };

  return (
    <AsyncSelect
      useDataHook={useGetActivities}
      dataKey="activities"
      loadingKey="activitiesLoading"
      getOptionLabel={getActivityLabel}
      getOptionKey={(option) => option?.id ?? getActivityLabel(option)}
      filterOptions={filterOptions}
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

// ==============================|| PROP TYPES ||============================== //

AsyncActivitySelect.propTypes = {
  /** Full activity object ({ id, activity_type, ... }) or null */
  value: PropTypes.object,
  /** MUI Autocomplete onChange — receives (event, value, reason, details) */
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  /** e.g. { account_id: 'uuid' } — scopes server-side search */
  filters: PropTypes.object,
  pageSize: PropTypes.number,
  /** UUIDs to hide from results (e.g. activities already attached) */
  excludeIds: PropTypes.array,
};

export default AsyncActivitySelect;
