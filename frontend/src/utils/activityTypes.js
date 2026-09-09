// frontend/src/utils/activityTypes.js
//
// P5 — the UNIFIED front source of truth for ACTIVITY TYPE presentation
// (the glyph + its uniform colour role), mirroring utils/signalTypes.js
// (SIGNAL_ICON). One icon map plus a resolver so a type's icon is defined ONCE
// and read by every activity surface (header tile, mini/playlist cards, table,
// timeline, link/outcome modals) — no per-component copy, no divergence.
//
// (Lives under utils/ because that path is aliased project-wide; constants/ is
// not — same reason as signalTypes.js / outcomes.js.)
//
// The 7 slugs align 1:1 with the API source of truth (ACTIVITY_TYPES in
// api/accounts/activities.js): CALL, EMAIL, MEETING, DEMO, TASK, LINKEDIN, OTHER.

import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import MailOutlined from "@ant-design/icons/MailOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import DesktopOutlined from "@ant-design/icons/DesktopOutlined";
import CheckSquareOutlined from "@ant-design/icons/CheckSquareOutlined";
import LinkedinOutlined from "@ant-design/icons/LinkedinOutlined";
import QuestionCircleOutlined from "@ant-design/icons/QuestionCircleOutlined";

// ==============================|| ACTIVITY TYPE ICON (centralized) ||============================== //

// The single glyph per type — the correct 7-type mapping (DEMO present,
// LinkedIn = the Linkedin mark, not Mail). Components import this instead of
// pulling ant-design icons in directly and re-declaring a local map.
export const ACTIVITY_TYPE_ICON = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  DEMO: DesktopOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined,
};

// The UNIFORM colour ROLE for a type glyph / tile — one primary role for every
// type (no rainbow), re-tinted at branding. Doctrine: theme role, never a
// hardcoded colour. The header tile fills with this and draws the glyph in the
// role's contrastText.
export const ACTIVITY_TYPE_ICON_COLOR = "primary.main";

/**
 * The icon component for an activity type, falling back to OTHER for an unknown
 * or missing type.
 * @param {string} type - activity type slug (e.g. "CALL", "DEMO", "LINKEDIN")
 * @returns {React.ComponentType} the ant-design icon component.
 */
export function getActivityTypeIcon(type) {
  return ACTIVITY_TYPE_ICON[type] || ACTIVITY_TYPE_ICON.OTHER;
}
