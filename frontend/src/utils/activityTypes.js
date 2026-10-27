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

import {
  getNextStepCitedNames,
  getNextStepUsablePeople,
} from "sections/activities/signals/utils/signalDisplay";

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

// ==============================|| NEXT STEP → ACTIVITY CONVERSION ||============================== //
//
// Sprint Next steps 2.2b — MIRROR of backend/app_modules/activities/constants.py
// (SCHEDULED_DATE_ACTIVITY_TYPES, NEXT_STEP_OBJECTIVE_PARTS_SEPARATOR,
// NEXT_STEP_SUCCESS_CRITERION_LABEL), used by the ActivityModal pre-fill so the
// form shows what the server would fill. Keep both sides in sync.

// D6: for these types the next step's date is WHEN the activity happens
// (scheduled_date); for every other type it is a deadline (due_date).
export const SCHEDULED_DATE_ACTIVITY_TYPES = new Set(["MEETING", "CALL", "DEMO"]);

export const NEXT_STEP_OBJECTIVE_PARTS_SEPARATOR = "\n\n";
export const NEXT_STEP_SUCCESS_CRITERION_LABEL = "Success criterion: ";

/**
 * The Objective (call_to_action) composed from a next step: its objective, then
 * its success criterion under its label ("" when it has neither).
 * @param {Object} nextStep - a NextStepSignal payload
 * @returns {string}
 */
export function nextStepObjective(nextStep) {
  const parts = [];
  if (nextStep?.suggested_objective) parts.push(nextStep.suggested_objective);
  if (nextStep?.suggested_success_criterion) {
    parts.push(NEXT_STEP_SUCCESS_CRITERION_LABEL + nextStep.suggested_success_criterion);
  }
  return parts.join(NEXT_STEP_OBJECTIVE_PARTS_SEPARATOR);
}

// ==============================|| ACTIVITY PRE-FILL FROM A NEXT STEP ||============================== //
//
// Sprint Next steps 5.8d — activityDefaultsFromNextStep: the SINGLE source of the
// activity pre-fill from a next step (2.2b), used by ActivityModal and the coque
// creation drawer. PO rule (5.8c): a next step CITES names, used only to create
// the activity — as contacts for the types below, in the description otherwise.

// The types whose cited names become the activity's contacts.
export const CITED_NAMES_AS_CONTACTS_TYPES = new Set(["MEETING", "CALL", "EMAIL"]);

export const NEXT_STEP_DESCRIPTION_PARTS_SEPARATOR = "\n\n";
export const NEXT_STEP_MENTIONED_LABEL = "Mentioned: ";
export const NEXT_STEP_INTERNAL_LABEL = "Internal: ";

const uniqueById = (contacts) => {
  const seen = new Set();
  return contacts.filter((c) => c?.id && !seen.has(c.id) && seen.add(c.id));
};

/**
 * The activity values a next step brings.
 * @param {Object} nextStep - a NextStepSignal payload
 * @param {Object} [context]
 * @param {string} [context.activityType] - the type imposed by the entry point
 * @param {Array<{name, contact}>} [context.citedContacts] - the names cited with
 *   the account contact the server matched (GET .../cited-contacts/, TD-279 rule)
 * @returns {{title, activity_type, scheduled_date, due_date, call_to_action,
 *   description, contacts, mentionedNames}} — dates as YYYY-MM-DD or null;
 *   contacts = contact objects; mentionedNames = names cited without a contact.
 */
export function activityDefaultsFromNextStep(nextStep, context = {}) {
  const activityType =
    context.activityType || nextStep?.suggested_activity_type || "MEETING";
  const date = nextStep?.suggested_due_date || null;
  const scheduled = SCHEDULED_DATE_ACTIVITY_TYPES.has(activityType);
  const citedAsContacts = CITED_NAMES_AS_CONTACTS_TYPES.has(activityType);

  // 2.2b: the next step's contacts, then its People's contacts.
  const baseContacts = [
    ...(nextStep?.suggested_contacts || []),
    ...getNextStepUsablePeople(nextStep).map((p) => p.target_contact).filter(Boolean),
  ];

  const cited = context.citedContacts || [];
  const contacts = citedAsContacts
    ? uniqueById([...baseContacts, ...cited.map((c) => c.contact).filter(Boolean)])
    : uniqueById(baseContacts);
  const mentionedNames = citedAsContacts
    ? cited.filter((c) => !c.contact).map((c) => c.name)
    : [];

  const citedNames = getNextStepCitedNames(nextStep);
  const internalNames = (nextStep?.suggested_internal_names || []).filter(Boolean);
  const description = [
    nextStep?.suggested_topics || "",
    !citedAsContacts && citedNames.length
      ? NEXT_STEP_MENTIONED_LABEL + citedNames.join(", ")
      : "",
    internalNames.length ? NEXT_STEP_INTERNAL_LABEL + internalNames.join(", ") : "",
  ]
    .filter(Boolean)
    .join(NEXT_STEP_DESCRIPTION_PARTS_SEPARATOR);

  return {
    title: nextStep?.suggested_title || "",
    activity_type: activityType,
    scheduled_date: scheduled ? date : null,
    due_date: scheduled ? null : date,
    call_to_action: nextStepObjective(nextStep),
    description,
    contacts,
    mentionedNames,
  };
}
