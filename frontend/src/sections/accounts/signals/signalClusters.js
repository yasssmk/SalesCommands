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
