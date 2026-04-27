// frontend/src/sections/accounts/signals/signalClusters.js
/**
 * Visual configuration for signal cluster UI.
 *
 * Centralized mapping of cluster-level enums to MUI colors, labels, icons
 * and helper text. Shared across SignalClusterCard, SignalClusterDetailDrawer
 * and any future cluster UI surface.
 *
 * Scope:
 *   - FRESHNESS_CONFIG       : cluster age buckets (FRESH / DORMANT / STALE)
 *   - PRIORITY_BUCKET_CONFIG : priority buckets (HIGH / MEDIUM / LOW)
 *   - IMPACT_LEVEL_CONFIG    : PainImpact level (BUSINESS / DEPARTMENT / PERSONAL)
 *   - HUMAN_IMPACT_CONFIG    : HumanImpact enum (FRUSTRATION / OVERLOAD / ...)
 *
 * Why /config semantics (even though the file lives under sections/):
 *   This module holds runtime-consumed lookup tables that include React-native
 *   elements (icons). It is intentionally free of JSX/hooks so it can be
 *   imported from anywhere without pulling rendering dependencies.
 *
 * Why duplicate IMPACT_LEVEL_CONFIG (also in PainCard):
 *   PainCard uses a local copy with the same values. Refactoring PainCard is
 *   out of Sprint 3 scope, but aligning values here ensures SignalClusterCard
 *   and SignalClusterDetailDrawer render impacts with colors consistent with
 *   PainCard when a PainCard is embedded in the drawer.
 *
 * Icon selection policy
 * ---------------------
 * Every icon imported below has been verified to resolve in this codebase.
 * Do NOT introduce a new icon here without first seeing it imported and
 * rendered successfully in another file — @ant-design/icons can resolve
 * non-existent paths to empty objects that crash React at render time.
 */

// ant-design icons
import ClockCircleOutlined from "@ant-design/icons/ClockCircleOutlined";
import MinusOutlined from "@ant-design/icons/MinusOutlined";
import PauseCircleOutlined from "@ant-design/icons/PauseCircleOutlined";
import RiseOutlined from "@ant-design/icons/RiseOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";
import WarningOutlined from "@ant-design/icons/WarningOutlined";

// ==============================|| FRESHNESS ||============================== //

/**
 * Cluster freshness buckets computed on the backend from the most recent
 * VALIDATED signal's age. See SignalClusterService._compute_lifecycle.
 *
 * Backend clamp: if at least one member references an active decision cycle
 * (outcome IS NULL or ON_HOLD), STALE is never returned — worst case is
 * DORMANT. The UI therefore never needs to "rescue" a STALE display.
 *
 * Shape per entry:
 *   color      : MUI palette key
 *   label      : short display label
 *   icon       : Ant Design icon component
 *   helperText : one-line explanation shown on hover/tooltip
 *   cta        : optional call-to-action shown when the state is negative
 */
export const FRESHNESS_CONFIG = {
  FRESH: {
    color: "success",
    label: "Fresh",
    icon: RiseOutlined,
    helperText: "Last confirmed within the past 30 days.",
    cta: null,
  },
  DORMANT: {
    color: "warning",
    label: "Dormant",
    icon: PauseCircleOutlined,
    helperText: "No confirmation in the past 30–90 days.",
    cta: "Re-confirm or archive",
  },
  STALE: {
    color: "error",
    label: "Stale",
    icon: ClockCircleOutlined,
    helperText: "No confirmation for over 90 days.",
    cta: "Re-confirm or archive",
  },
};

// ==============================|| PRIORITY BUCKET ||============================== //

/**
 * Priority buckets derived server-side from the priority score.
 * The raw score is exposed in the payload for debugging but never
 * surfaced in the UI — the bucket alone drives visual emphasis.
 *
 * Color rationale:
 *   HIGH   → error   (strongest visual weight, demands attention)
 *   MEDIUM → warning (noticeable but not alarming)
 *   LOW    → default (neutral, the card remains quiet)
 *
 * variant: passed through to MUI Chip — HIGH is filled for maximum
 * contrast, MEDIUM/LOW outlined to stay visually calm in dense lists.
 */
export const PRIORITY_BUCKET_CONFIG = {
  HIGH: {
    color: "error",
    label: "High",
    variant: "filled",
    icon: ThunderboltOutlined,
  },
  MEDIUM: {
    color: "warning",
    label: "Medium",
    variant: "outlined",
    icon: WarningOutlined,
  },
  LOW: {
    color: "default",
    label: "Low",
    variant: "outlined",
    icon: MinusOutlined,
  },
};

// ==============================|| IMPACT LEVEL ||============================== //

/**
 * PainImpact scope levels. Used to display the highest-observed level
 * across a cluster's impacts (max_impact_level field).
 *
 * Colors align with PainCard to keep the drawer visually consistent
 * when PainCards are embedded as cluster members.
 *
 *   BUSINESS   → warning (yellow/orange) — global / strategic concern
 *   DEPARTMENT → info    (blue)          — team-level concern
 *   PERSONAL   → error   (red)           — individual human concern
 */
export const IMPACT_LEVEL_CONFIG = {
  BUSINESS: {
    color: "warning",
    label: "Business",
  },
  DEPARTMENT: {
    color: "info",
    label: "Department",
  },
  PERSONAL: {
    color: "error",
    label: "Personal",
  },
};

// ==============================|| HUMAN IMPACT ||============================== //

/**
 * HumanImpact enum mapping — used by cluster UI to render the aggregated
 * human_impacts array (e.g. "FRUSTRATION ×3, OVERLOAD ×1").
 *
 * Values mirror the backend HumanImpact enum in app_modules/signals/constants.py.
 * If new values are added to the enum, keep this object in sync.
 */
export const HUMAN_IMPACT_CONFIG = {
  FRUSTRATION: { label: "Frustration" },
  OVERLOAD: { label: "Overload" },
  STRESS: { label: "Stress" },
  DEMOTIVATION: { label: "Demotivation" },
  CONFLICT: { label: "Conflict" },
};

// ==============================|| SIGNAL TYPE VISUALS ||============================== //

/**
 * Visual identity per cluster signal_type. Drives the type chip color
 * and the canonical-axes chip color across SignalClusterCard and
 * SignalClusterDetailDrawer.
 *
 * Color rationale:
 *   pain      → error (red)   — matches PainCard's identity
 *   objective → info  (blue)  — matches ObjectiveCard's identity
 *
 * The label is what the type chip displays (capitalised, single word).
 * If a future signal type joins the cluster service (people / tech_stack),
 * add an entry here to keep the cluster surface consistent.
 */
export const SIGNAL_TYPE_VISUALS = {
  pain: {
    color: "error",
    label: "Pain",
  },
  objective: {
    color: "info",
    label: "Objective",
  },
};

// ==============================|| TARGET DATE URGENCY ||============================== //

/**
 * Days threshold for the "soon" target_date bucket.
 *
 * MUST stay in sync with the backend constant
 * OBJECTIVE_TARGET_DATE_SOON_DAYS in services/signal_priority_service.py.
 * The backend uses this value to compute `has_target_date_soon`; the
 * frontend uses it to decide whether a not-yet-overdue date should be
 * rendered in the warning palette or the neutral palette.
 */
export const OBJECTIVE_TARGET_DATE_SOON_DAYS = 90;

// ==============================|| FALLBACKS ||============================== //

/**
 * Safe defaults returned by the resolve helpers below when the input
 * value is null, undefined, or unknown. Ensures the UI never receives
 * undefined properties that would crash chip rendering.
 */
const FRESHNESS_FALLBACK = {
  color: "default",
  label: "—",
  icon: MinusOutlined,
  helperText: "Freshness not computed yet.",
  cta: null,
};

const PRIORITY_FALLBACK = {
  color: "default",
  label: "—",
  variant: "outlined",
  icon: MinusOutlined,
};

const IMPACT_LEVEL_FALLBACK = {
  color: "default",
  label: "—",
};

const HUMAN_IMPACT_FALLBACK = { label: "Other" };

const SIGNAL_TYPE_FALLBACK = {
  color: "default",
  label: "Cluster",
};

/**
 * Default urgency entry returned when the cluster has no target_date.
 *
 * Note: the resolver uses null instead of this fallback when the input
 * list is empty — empty list means "no target date at all", and the UI
 * should hide the badge entirely rather than render a neutral state.
 * This fallback only applies when target_dates contains malformed strings
 * that fail to parse.
 */
const TARGET_DATE_URGENCY_FALLBACK = {
  bucket: "UNKNOWN",
  label: "Target date",
  color: "default",
  daysUntil: null,
  earliestDate: null,
};

// ==============================|| DEFENSIVE HELPERS ||============================== //

/**
 * Check whether a value is a valid React component reference.
 *
 * Accepted:
 *   - functions (stateless, forwardRef unwrapped, class constructors)
 *   - objects produced by React.forwardRef / React.memo (identified by
 *     their $$typeof symbol)
 *
 * Rejected:
 *   - null / undefined
 *   - empty objects ({}) — produced when @ant-design/icons resolves a
 *     non-existent icon path to an empty module export. Rendering such
 *     a value crashes React with "Element type is invalid: got object."
 */
function isValidIconComponent(candidate) {
  if (!candidate) return false;
  if (typeof candidate === "function") return true;
  if (typeof candidate === "object" && candidate.$$typeof) return true;
  return false;
}

/**
 * Normalise a resolved config entry: if its icon is not a valid component,
 * substitute the fallback's icon. This guards every consumer (SignalCluster
 * Card, SignalClusterDetailDrawer, any future consumer) against a broken
 * icon import causing a whole-tree render crash.
 */
function sanitizeConfigEntry(entry, fallback) {
  if (!entry) return fallback;
  if (isValidIconComponent(entry.icon)) return entry;
  return { ...entry, icon: fallback.icon };
}

// ==============================|| RESOLVERS ||============================== //

/**
 * Resolve freshness config with a safe default.
 *
 * @param {'FRESH'|'DORMANT'|'STALE'|null|undefined} status
 * @returns {{ color, label, icon, helperText, cta }}
 */
export function resolveFreshness(status) {
  if (!status) return FRESHNESS_FALLBACK;
  return sanitizeConfigEntry(FRESHNESS_CONFIG[status], FRESHNESS_FALLBACK);
}

/**
 * Resolve priority bucket config with a safe default.
 *
 * @param {'HIGH'|'MEDIUM'|'LOW'|null|undefined} bucket
 * @returns {{ color, label, variant, icon }}
 */
export function resolvePriority(bucket) {
  if (!bucket) return PRIORITY_FALLBACK;
  return sanitizeConfigEntry(PRIORITY_BUCKET_CONFIG[bucket], PRIORITY_FALLBACK);
}

/**
 * Resolve impact level config with a safe default.
 *
 * @param {'BUSINESS'|'DEPARTMENT'|'PERSONAL'|null|undefined} level
 * @returns {{ color, label }}
 */
export function resolveImpactLevel(level) {
  if (!level) return IMPACT_LEVEL_FALLBACK;
  return IMPACT_LEVEL_CONFIG[level] ?? IMPACT_LEVEL_FALLBACK;
}

/**
 * Resolve human impact label with a safe default.
 *
 * @param {string|null|undefined} type
 * @returns {{ label: string }}
 */
export function resolveHumanImpact(type) {
  if (!type) return HUMAN_IMPACT_FALLBACK;
  return HUMAN_IMPACT_CONFIG[type] ?? { label: type };
}

/**
 * Resolve cluster type visuals with a safe default.
 *
 * Used by SignalClusterCard and SignalClusterDetailDrawer to render the
 * type chip and the canonical-axes chip in the right palette. An
 * unknown signal_type is rendered with a generic "Cluster" chip so the
 * surface never crashes if a new type ships before the frontend
 * registers it.
 *
 * @param {'pain'|'objective'|string|null|undefined} signalType
 * @returns {{ color: string, label: string }}
 */
export function resolveSignalTypeVisuals(signalType) {
  if (!signalType) return SIGNAL_TYPE_FALLBACK;
  return SIGNAL_TYPE_VISUALS[signalType] ?? SIGNAL_TYPE_FALLBACK;
}

/**
 * Resolve scope level config (BUSINESS / DEPARTMENT / PERSONAL).
 *
 * Used by Objective cluster UI to render the `max_scope_level` chip.
 * Aliases IMPACT_LEVEL_CONFIG so that Pain's max_impact_level and
 * Objective's max_scope_level render with identical colors — the two
 * concepts share the same scope axis (ScopeLevel) on the backend.
 *
 *   BUSINESS   → warning (yellow/orange)
 *   DEPARTMENT → info    (blue)
 *   PERSONAL   → error   (red)
 *
 * @param {'BUSINESS'|'DEPARTMENT'|'PERSONAL'|null|undefined} level
 * @returns {{ color: string, label: string }}
 */
export function resolveScopeLevel(level) {
  if (!level) return IMPACT_LEVEL_FALLBACK;
  return IMPACT_LEVEL_CONFIG[level] ?? IMPACT_LEVEL_FALLBACK;
}

/**
 * Classify a list of target dates into an urgency bucket for the UI.
 *
 * Inputs come from the cluster payload:
 *   - target_dates         : sorted ISO yyyy-mm-dd[] (may be empty)
 *   - has_target_date_soon : backend-computed boolean (defensive cross-check)
 *
 * Algorithm:
 *   1. If target_dates is empty → return null (UI should hide the badge).
 *   2. Pick the EARLIEST date in target_dates (the list is sorted asc).
 *   3. Compare to today:
 *        diff < 0   → OVERDUE                 (error palette)
 *        diff = 0   → DUE_TODAY               (error palette)
 *        diff <= 90 → SOON ("In Nd")          (warning palette)
 *        else       → LATER ("In Nd")         (default palette)
 *
 * The `daysUntil` field is signed: negative = overdue, positive =
 * upcoming. The UI may format that into "Overdue by 3 days" or
 * "In 12 days" depending on the bucket.
 *
 * Returns null when there is nothing to display so the caller can
 * conditionally render the badge — distinct from the fallback shape
 * which only kicks in for malformed dates that fail to parse.
 *
 * @param {string[]|null|undefined} targetDates
 * @param {boolean} [hasTargetDateSoon]  Defensive — currently informative
 *                                       only; the bucket is derived from
 *                                       targetDates[0] which is the
 *                                       authoritative date.
 * @returns {{
 *   bucket: 'OVERDUE'|'DUE_TODAY'|'SOON'|'LATER'|'UNKNOWN',
 *   label: string,
 *   color: string,
 *   daysUntil: number|null,
 *   earliestDate: string|null
 * } | null}
 */
export function resolveTargetDateUrgency(targetDates, hasTargetDateSoon) {
  // Empty / missing → hide badge entirely.
  if (!Array.isArray(targetDates) || targetDates.length === 0) {
    return null;
  }

  // The list is server-sorted asc; the earliest date is index 0. We
  // still iterate defensively in case a non-sorted feed reaches us — the
  // cost is negligible and the safety is worth it.
  let earliestStr = null;
  let earliestTime = Number.POSITIVE_INFINITY;
  for (const raw of targetDates) {
    if (!raw) continue;
    const t = new Date(raw).getTime();
    if (Number.isNaN(t)) continue;
    if (t < earliestTime) {
      earliestTime = t;
      earliestStr = raw;
    }
  }

  // No parseable date — fall back to the neutral shape so the UI can
  // render something rather than crash, but flag the unknown bucket.
  if (!earliestStr) {
    return TARGET_DATE_URGENCY_FALLBACK;
  }

  // Day-precision comparison — strip the time portion of both anchors
  // so a target_date of "today" registers as DUE_TODAY regardless of
  // the current clock hour.
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const earliest = new Date(earliestTime);
  earliest.setHours(0, 0, 0, 0);

  const diffDays = Math.round(
    (earliest.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (diffDays < 0) {
    return {
      bucket: "OVERDUE",
      label: "Overdue",
      color: "error",
      daysUntil: diffDays,
      earliestDate: earliestStr,
    };
  }

  if (diffDays === 0) {
    return {
      bucket: "DUE_TODAY",
      label: "Due today",
      color: "error",
      daysUntil: 0,
      earliestDate: earliestStr,
    };
  }

  if (diffDays <= OBJECTIVE_TARGET_DATE_SOON_DAYS) {
    return {
      bucket: "SOON",
      label: `In ${diffDays}d`,
      color: "warning",
      daysUntil: diffDays,
      earliestDate: earliestStr,
    };
  }

  return {
    bucket: "LATER",
    label: `In ${diffDays}d`,
    color: "default",
    daysUntil: diffDays,
    earliestDate: earliestStr,
  };
}
