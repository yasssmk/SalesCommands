// frontend/src/sections/activities/workspace/EditActivityContent.jsx
//
// SE-b — the Activity EDIT drawer, rebuilt on the shared DrawerContentLayout +
// InlineEditableValue. It is a SHELL-LESS node injected into the WorkspaceDrawer
// coque. ONE content box holds the field groups, separated by internal hairline
// filets; each field edits on a single CLICK (no textual "Edit", no per-group
// title). A single GLOBAL Save PATCHes the modified CONTENT fields via
// updateActivity; Cancel closes the coque.
//
// Groups: (1) Title + Type · (2) Date & time (scheduled|due exclusive toggle,
// mechanics cloned from UnifiedDateSection) · (3) Objective + Description ·
// (4) People — editable owner (single required slot) / invited / contacts
// (min 1), all draft-only until the global Save.
//
// Formik + Yup (title required, at-least-one-date, owner required, contacts
// min 1); no hardcoded hex/px.
//
// Sprint Next steps 5.8d — CREATION mode (mode="create"): the SAME form, a
// second submit (createActivity, or createActivityWithEntities with a contact
// created on the fly — InlineContactForm). Pre-filled by
// activityDefaultsFromNextStep (the single 2.2b source; + the cited names'
// account contacts, the others recalled as "Mentioned"). Extra fields: the
// decision cycle (pre-filled from the context, modifiable) and its step (the
// next step's proposal, else the cycle's current step). The owner is the
// user's name, read-only (the server makes the creator the owner). Save is
// disabled only by an invalid form.

"use client";

import PropTypes from "prop-types";
import { useEffect, useMemo, useRef, useState } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";
import dayjs from "dayjs";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import FormHelperText from "@mui/material/FormHelperText";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import CheckOutlined from "@ant-design/icons/CheckOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { TimePicker } from "@mui/x-date-pickers/TimePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import {
  createActivity,
  createActivityWithEntities,
  updateActivity,
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
} from "api/accounts/activities";
import {
  useGetDecisionCyclesByAccount,
  useGetDecisionStepsByCycle,
} from "api/accounts/decisionCycles";
import { useNextStepCitedContacts } from "api/signals/signals";
import { useAuth } from "hooks/useAuth";
import { activityDefaultsFromNextStep } from "utils/activityTypes";
import { InlineContactForm } from "sections/accounts/activities/components";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import PersonRow from "components/display/PersonRow";
import AsyncUserSelect from "components/AsyncSelection/AsyncUserSelect";
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";

// ==============================|| VALIDATION ||============================== //

const FIELD_RULES = {
  title: Yup.string().trim().required("Title is required").max(255, "Title must be at most 255 characters"),
  activity_type: Yup.string().required("Activity type is required"),
  // No length cap: the Objective column is unbounded (Sprint Next steps 2.2a, R3).
  call_to_action: Yup.string().nullable(),
  // No length cap: the Description column is unbounded (Sprint Next steps 2.2b).
  description: Yup.string().nullable(),
  scheduled_date: Yup.date()
    .nullable()
    .typeError("Please select a valid date")
    .when("due_date", {
      is: (dueDate) => !dueDate,
      then: (schema) => schema.required("A scheduled date or a due date is required"),
      otherwise: (schema) => schema.nullable(),
    }),
  due_date: Yup.date().nullable().typeError("Please select a valid date"),
};

const DATE_PAIR = [["scheduled_date", "due_date"]];

const validationSchema = Yup.object(
  {
    ...FIELD_RULES,
    // owner is NOT NULL backend — Formik keeps the invariant, never sends null.
    owner: Yup.object().nullable().required("An owner is required"),
    contacts: Yup.array().min(1, "At least one contact is required"),
  },
  DATE_PAIR,
);

// Creation: the owner is the creator (read-only, never sent); at least one
// contact — selected, or created on the fly; a step once a cycle is chosen.
const createValidationSchema = Yup.object(
  {
    ...FIELD_RULES,
    contacts: Yup.array().when("inline_contact", {
      is: (inline) => Boolean(inline),
      then: (schema) => schema,
      otherwise: (schema) => schema.min(1, "At least one contact is required"),
    }),
    decision_step_id: Yup.string().when("decision_cycle_id", {
      is: (cycle) => Boolean(cycle),
      then: (schema) => schema.required("Please select a step for this cycle"),
      otherwise: (schema) => schema.nullable(),
    }),
  },
  DATE_PAIR,
);

// ==============================|| HELPERS ||============================== //

const TYPE_OPTIONS = Object.entries(ACTIVITY_TYPES).map(([key, value]) => ({
  value,
  label: ACTIVITY_TYPE_LABELS[key],
}));

function fmtDate(v) {
  return v ? dayjs(v).format("YYYY-MM-DD") : null;
}
function readDate(v) {
  return v ? dayjs(v).format("MMM D, YYYY") : null;
}
function readTime(t) {
  return t ? dayjs(t).format("h:mm A") : null;
}
function personName(p) {
  return p?.full_name || [p?.first_name, p?.last_name].filter(Boolean).join(" ") || p?.email || null;
}

// ==============================|| INTERNAL FILET ||============================== //

// The same hairline separator as the workspace header, used BETWEEN groups.
function Filet() {
  const aq = useTheme().aphoriQ;
  return (
    <Box
      data-testid="group-filet"
      sx={{
        borderTopStyle: "solid",
        borderTopWidth: aq.border.width.hairline,
        borderTopColor: aq.border.color,
      }}
    />
  );
}

// A discreet muted marker that a field is set by the campaign (no loud lock).
function LockedHint() {
  const aq = useTheme().aphoriQ;
  return (
    <Typography component="span" variant="caption" sx={{ color: aq.text.subtle, ml: 0.75 }}>
      · set by the campaign
    </Typography>
  );
}

// ==============================|| DATE GROUP ||============================== //

// Read: label ("Scheduled" / "Due date") + the current date (+time). A single CLICK
// flips to an inline toggle (scheduled|due, exclusive) + the active picker(s).
// Switching the toggle clears the OTHER date (and scheduled_time when leaving
// scheduled) — mechanics cloned from UnifiedDateSection.
function DateGroup({ values, setFieldValue, locked = false }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const [editing, setEditing] = useState(false);
  const [mode, setMode] = useState(values.scheduled_date || !values.due_date ? "scheduled" : "due");
  // Snapshot of the draft (date/time/mode) captured on entering edit — ✗ restores it.
  const startRef = useRef(null);

  const startEdit = () => {
    if (locked) return;
    startRef.current = {
      scheduled_date: values.scheduled_date,
      scheduled_time: values.scheduled_time,
      due_date: values.due_date,
      mode,
    };
    setEditing(true);
  };

  // ✓ — keep the current draft, just return to read (no PATCH; the global Save owns it).
  const confirm = () => setEditing(false);

  // ✗ — restore the pre-edit draft (date/time/mode) and return to read.
  const cancel = () => {
    const s = startRef.current;
    if (s) {
      setFieldValue("scheduled_date", s.scheduled_date);
      setFieldValue("scheduled_time", s.scheduled_time);
      setFieldValue("due_date", s.due_date);
      setMode(s.mode);
    }
    setEditing(false);
  };

  const handleMode = (_e, val) => {
    if (!val) return;
    setMode(val);
    if (val === "due") {
      setFieldValue("scheduled_date", null);
      setFieldValue("scheduled_time", null);
    } else {
      setFieldValue("due_date", null);
    }
  };

  if (editing) {
    const pickerLabel = mode === "scheduled" ? "Scheduled date" : "Due date";
    return (
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Stack spacing={1.5}>
          <ToggleButtonGroup value={mode} exclusive onChange={handleMode} size="small">
            <ToggleButton value="scheduled">Scheduled</ToggleButton>
            <ToggleButton value="due">Due Date</ToggleButton>
          </ToggleButtonGroup>

          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <DatePicker
                label={pickerLabel}
                value={mode === "scheduled" ? values.scheduled_date : values.due_date}
                onChange={(v) => {
                  if (mode === "scheduled") {
                    setFieldValue("scheduled_date", v);
                    if (!v) setFieldValue("scheduled_time", null);
                  } else {
                    setFieldValue("due_date", v);
                  }
                }}
                slotProps={{ textField: { fullWidth: true, size: "small" } }}
              />
            </Box>
            {mode === "scheduled" && (
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <TimePicker
                  label="Scheduled time"
                  value={values.scheduled_time}
                  onChange={(v) => setFieldValue("scheduled_time", v)}
                  disabled={!values.scheduled_date}
                  slotProps={{ textField: { fullWidth: true, size: "small" } }}
                />
              </Box>
            )}
          </Stack>

          {/* ✓ validate (keep draft) / ✗ discard (restore) — local read/edit only. */}
          <Stack direction="row" justifyContent="flex-end" spacing={0.5}>
            <IconButton
              size="small"
              onClick={confirm}
              data-testid="date-confirm"
              aria-label="Confirm date"
              sx={{ color: "success.main" }}
            >
              <CheckOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
            <IconButton
              size="small"
              onClick={cancel}
              data-testid="date-cancel"
              aria-label="Discard date changes"
              sx={{ color: "error.main" }}
            >
              <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
          </Stack>
        </Stack>
      </LocalizationProvider>
    );
  }

  const isScheduled = Boolean(values.scheduled_date) || !values.due_date;
  const dateVal = isScheduled ? readDate(values.scheduled_date) : readDate(values.due_date);
  const timeVal = isScheduled ? readTime(values.scheduled_time) : null;
  const display = dateVal ? (timeVal ? `${dateVal} · ${timeVal}` : dateVal) : null;

  return (
    <Box>
      <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
        {isScheduled ? "Scheduled" : "Due date"}
        {locked && <LockedHint />}
      </Typography>
      <Box
        data-testid="inline-read-date"
        onClick={startEdit}
        sx={{ cursor: locked ? "default" : "pointer", py: 0.25 }}
      >
        {display ? (
          <Typography variant="body2" color="text.primary">
            {display}
          </Typography>
        ) : (
          <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
            No date set
          </Typography>
        )}
      </Box>
    </Box>
  );
}

DateGroup.propTypes = {
  values: PropTypes.object.isRequired,
  setFieldValue: PropTypes.func.isRequired,
  locked: PropTypes.bool,
};

// ==============================|| PEOPLE PLACEHOLDER (SE-c) ||============================== //

// Read-only for now — owner / invited / contacts. SE-c replaces this with the
// editable owner slot + removable invited/contacts + AsyncSelects.
// A person line with a remove ✕. Editable rows for owner / invited / contacts.
function PersonEditRow({ name, suffix, onRemove, removeTestId }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
      <Box sx={{ minWidth: 0 }}>
        <PersonRow name={name} suffix={suffix} />
      </Box>
      <IconButton
        size="small"
        onClick={onRemove}
        data-testid={removeTestId}
        aria-label={`Remove ${name}`}
        sx={{ color: aq.text.muted }}
      >
        <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
      </IconButton>
    </Stack>
  );
}

PersonEditRow.propTypes = {
  name: PropTypes.string,
  suffix: PropTypes.string,
  onRemove: PropTypes.func.isRequired,
  removeTestId: PropTypes.string.isRequired,
};

// The editable People section — draft only; the drawer's global Save PATCHes.
// owner: single required slot (× empties it visually, but Formik keeps owner
// required so a null owner_id is never sent). invited: optional removable list.
// contacts: removable list, min 1 (Formik blocks Save when empty).
function PeopleSection({
  values,
  setFieldValue,
  errors,
  accountId,
  locked = false,
  ownerReadOnly = false,
  allowInlineContact = false,
  mentionedNames = [],
}) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const [addOwner, setAddOwner] = useState(false);
  const [addInvited, setAddInvited] = useState(false);
  const [addContact, setAddContact] = useState(false);
  const [addInlineContact, setAddInlineContact] = useState(false);

  const caption = (t, withHint = false) => (
    <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.5 }}>
      {t}
      {withHint && locked && <LockedHint />}
    </Typography>
  );
  const emptyLine = (t) => (
    <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
      {t}
    </Typography>
  );
  const addButton = (onClick, testId, label) => (
    <Button
      variant="text"
      size="small"
      onClick={onClick}
      data-testid={testId}
      startIcon={<PlusOutlined style={{ fontSize: theme.iconSizes.sm }} />}
      sx={{ color: aq.accent, px: 0, justifyContent: "flex-start", textTransform: "none" }}
    >
      {label}
    </Button>
  );

  const invited = values.invited || [];
  const contacts = values.contacts || [];
  const ownerSuffix = values.owner?.email || undefined;

  return (
    <Stack data-testid="people-section" spacing={1.5}>
      {/* Activity owner — single required slot. Read « First Last · email »:
          the name (bold) + the email in the muted suffix (5.8g); never
          "owner" — the caption says it. */}
      <Box data-testid="activity-owner">
        {caption("Activity owner", true)}
        {ownerReadOnly ? (
          // Creation: the creator is the owner (server rule) — named, read-only.
          <PersonRow name={personName(values.owner)} suffix={ownerSuffix} />
        ) : locked ? (
          values.owner ? <PersonRow name={personName(values.owner)} suffix={ownerSuffix} /> : emptyLine("No owner")
        ) : values.owner ? (
          <PersonEditRow
            name={personName(values.owner)}
            suffix={ownerSuffix}
            onRemove={() => setFieldValue("owner", null)}
            removeTestId="remove-owner"
          />
        ) : addOwner ? (
          <AsyncUserSelect
            data-testid="owner-select"
            value={null}
            excludeIds={invited.map((u) => u.id)}
            onChange={(_event, user) => {
              setFieldValue("owner", user || null);
              setAddOwner(false);
            }}
            label=""
            placeholder="Search a user…"
          />
        ) : (
          addButton(() => setAddOwner(true), "add-owner", "Add owner")
        )}
        {Boolean(errors.owner) && <FormHelperText error>{errors.owner}</FormHelperText>}
      </Box>

      {/* Invited — optional removable list */}
      <Box>
        {caption("Invited")}
        {locked
          ? (invited.length ? invited.map((u) => <PersonRow key={u.id} name={personName(u)} />) : emptyLine("None"))
          : invited.map((u) => (
              <PersonEditRow
                key={u.id}
                name={personName(u)}
                onRemove={() => setFieldValue("invited", invited.filter((x) => x.id !== u.id))}
                removeTestId={`remove-invited-${u.id}`}
              />
            ))}
        {!locked && (addInvited ? (
          <AsyncUserSelect
            data-testid="invited-select"
            value={null}
            excludeIds={[...invited.map((u) => u.id), values.owner?.id].filter(Boolean)}
            onChange={(_event, user) => {
              // dedup guard — never push a user already invited (belt + braces)
              if (user && !invited.some((x) => x.id === user.id)) {
                setFieldValue("invited", [...invited, user]);
              }
              setAddInvited(false);
            }}
            label=""
            placeholder="Search users…"
          />
        ) : (
          addButton(() => setAddInvited(true), "add-invited", "Add teammate")
        ))}
      </Box>

      {/* External contacts — removable list, min 1 */}
      <Box>
        {caption("External contacts")}
        {locked
          ? (contacts.length
              ? contacts.map((c) => (
                  <PersonRow key={c.id} name={personName(c)} suffix={c.department_name || undefined} />
                ))
              : emptyLine("None"))
          : contacts.map((c) => (
              <PersonEditRow
                key={c.id}
                name={personName(c)}
                suffix={c.department_name || undefined}
                onRemove={() => setFieldValue("contacts", contacts.filter((x) => x.id !== c.id))}
                removeTestId={`remove-contact-${c.id}`}
              />
            ))}
        {!locked && addContact && (
          <AsyncContactSelect
            data-testid="contact-select"
            value={null}
            excludeIds={contacts.map((c) => c.id)}
            onChange={(_event, contact) => {
              // dedup guard — never push a contact already selected (belt + braces)
              if (contact && !contacts.some((x) => x.id === contact.id)) {
                setFieldValue("contacts", [...contacts, contact]);
              }
              setAddContact(false);
            }}
            filters={{ account_id: accountId }}
            label=""
            placeholder="Search contacts…"
          />
        )}
        {/* Creation: a contact created on the fly (create-with-entities). */}
        {allowInlineContact && values.inline_contact && (
          <PersonEditRow
            name={personName(values.inline_contact)}
            suffix="new contact"
            onRemove={() => setFieldValue("inline_contact", null)}
            removeTestId="remove-inline-contact"
          />
        )}
        {allowInlineContact && !values.inline_contact && addInlineContact && (
          <InlineContactForm
            onSave={(contact) => {
              setFieldValue("inline_contact", contact);
              setAddInlineContact(false);
            }}
            onCancel={() => setAddInlineContact(false)}
          />
        )}
        {/* The add actions — one row, the standard gap between actions (the
            drawer's: theme spacing 1), never stuck together (5.8g). */}
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" data-testid="contact-add-actions">
          {!locked && !addContact && addButton(() => setAddContact(true), "add-contact", "Add contact")}
          {allowInlineContact && !values.inline_contact && !addInlineContact &&
            addButton(() => setAddInlineContact(true), "add-inline-contact", "New contact")}
        </Stack>
        {/* Creation from a next step: the names cited no contact matched. */}
        {mentionedNames.length > 0 && (
          <Typography
            variant="caption"
            data-testid="mentioned-names"
            sx={{ color: aq.text.muted, display: "block", mt: 0.5 }}
          >
            {`Mentioned: ${mentionedNames.join(", ")}`}
          </Typography>
        )}
        {!locked && Boolean(errors.contacts) && <FormHelperText error>{errors.contacts}</FormHelperText>}
      </Box>
    </Stack>
  );
}

PeopleSection.propTypes = {
  locked: PropTypes.bool,
  /** Creation: the owner (the creator) is shown, not editable. */
  ownerReadOnly: PropTypes.bool,
  /** Creation: a contact can be created on the fly (InlineContactForm). */
  allowInlineContact: PropTypes.bool,
  /** Creation from a next step: the cited names no contact matched. */
  mentionedNames: PropTypes.arrayOf(PropTypes.string),
  values: PropTypes.object.isRequired,
  setFieldValue: PropTypes.func.isRequired,
  errors: PropTypes.object.isRequired,
  accountId: PropTypes.string,
};

// ==============================|| EDIT ACTIVITY CONTENT ||============================== //

// The creation waits for its defaults (Sprint Next steps 5.8e): the names cited
// with their account contacts are read first, the drawer's loading indicator
// meanwhile; the form mounts once, with its final initial values, and is never
// re-initialised afterwards (a typing is never lost).
export default function EditActivityContent(props) {
  if (props.mode !== "create") return <ActivityForm {...props} />;
  return <CreateActivityGate {...props} />;
}

function CreateActivityGate(props) {
  const theme = useTheme();
  const { citedContacts, citedLoading } = useNextStepCitedContacts(props.nextStep?.id ?? null);
  if (citedLoading) {
    return (
      <DrawerContentLayout>
        <Box
          data-testid="activity-create-loading"
          sx={{ display: "flex", justifyContent: "center", py: 4 }}
        >
          <CircularProgress size={theme.iconSizes.md} />
        </Box>
      </DrawerContentLayout>
    );
  }
  return <ActivityForm {...props} citedContacts={citedContacts} />;
}

CreateActivityGate.propTypes = { nextStep: PropTypes.object };

function ActivityForm({
  activity,
  onSaved,
  mode = "edit",
  accountId: createAccountId,
  decisionCycleId,
  nextStep,
  activityType,
  citedContacts = [],
  onCreated,
  onCancel,
}) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { user } = useAuth();
  const isCreate = mode === "create";
  const accountId = isCreate
    ? createAccountId
    : activity?.account_detail?.id || activity?.account || null;
  // COND-1 — a campaign activity has date / contacts / owner / invited set by the
  // campaign: those fields are locked (read-only) and never sent in the PATCH.
  // A NEW activity is never a campaign activity.
  const isCampaign = !isCreate && Boolean(activity?.campaign_detail);

  // Creation: the defaults, computed ONCE — the gate mounted this form with the
  // names cited and their account contacts (TD-279 rule, server) already read.
  const [defaults] = useState(() =>
    isCreate ? activityDefaultsFromNextStep(nextStep, { activityType, citedContacts }) : null,
  );

  // Memoized so the reference is STABLE across renders — with a fresh inline
  // object each render, enableReinitialize's compare (fresh dayjs objects) is
  // fragile and can reset the form under a picker interaction. Keyed on the
  // frozen activity's id (the injected node snapshots the activity).
  const initialValues = useMemo(
    () =>
      isCreate
        ? {
            title: defaults.title,
            activity_type: defaults.activity_type,
            scheduled_date: defaults.scheduled_date ? dayjs(defaults.scheduled_date) : null,
            scheduled_time: null,
            due_date: defaults.due_date ? dayjs(defaults.due_date) : null,
            call_to_action: defaults.call_to_action,
            description: defaults.description,
            owner: user || null,
            invited: [],
            contacts: defaults.contacts,
            inline_contact: null,
            decision_cycle_id: decisionCycleId || "",
            // The next step's proposed step (a step of its own cycle — the
            // server checks it), else the cycle's current one (effect below).
            decision_step_id:
              decisionCycleId && nextStep?.suggested_decision_step
                ? String(nextStep.suggested_decision_step)
                : "",
          }
        : {
            title: activity?.title || "",
            activity_type: activity?.activity_type || "",
            scheduled_date: activity?.scheduled_date ? dayjs(activity.scheduled_date) : null,
            scheduled_time: activity?.scheduled_time ? dayjs(`2000-01-01T${activity.scheduled_time}`) : null,
            due_date: activity?.due_date ? dayjs(activity.due_date) : null,
            call_to_action: activity?.call_to_action || "",
            description: activity?.description || "",
            owner: activity?.owner_detail || null,
            invited: activity?.invited_users_detail || [],
            contacts: activity?.contacts_detail || [],
          },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activity?.id, defaults],
  );

  const submitCreate = async (values) => {
    const payload = {
      title: values.title.trim(),
      activity_type: values.activity_type,
      status: "PLANNED",
      description: values.description?.trim() || null,
      call_to_action: values.call_to_action?.trim() || null,
      scheduled_date: fmtDate(values.scheduled_date),
      scheduled_time:
        values.scheduled_date && values.scheduled_time
          ? dayjs(values.scheduled_time).format("HH:mm:ss")
          : null,
      due_date: fmtDate(values.due_date),
      contact_ids: (values.contacts || []).map((c) => c.id),
      invited_user_ids: (values.invited || []).map((u) => u.id),
      account_id: accountId,
      decision_cycle_id: values.decision_cycle_id || null,
      decision_step_id: values.decision_step_id || null,
    };
    if (nextStep?.id) payload.next_step_signal_id = nextStep.id;
    return values.inline_contact
      ? createActivityWithEntities({
          activity: payload,
          inline_contact: values.inline_contact,
          inline_cycle: null,
          inline_step_stage: null,
        })
      : createActivity(payload);
  };

  const formik = useFormik({
    // Edit: follows the activity; creation: never re-initialised after mount.
    enableReinitialize: !isCreate,
    validationSchema: isCreate ? createValidationSchema : validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      if (isCreate) {
        try {
          const result = await submitCreate(values);
          if (result?.success) {
            displaySuccessSnackbar("Activity created");
            if (onCreated) onCreated(result.data);
            else closeDrawer();
          } else {
            displayErrorSnackbar(result);
          }
        } catch (err) {
          displayErrorSnackbar(err);
        } finally {
          setSubmitting(false);
        }
        return;
      }
      // Always-editable fields.
      const payload = {
        title: values.title.trim(),
        activity_type: values.activity_type,
        call_to_action: values.call_to_action?.trim() || null,
        description: values.description?.trim() || null,
      };
      // Campaign-locked fields — only sent for a non-campaign activity (the
      // backend also refuses them on a campaign activity).
      if (!isCampaign) {
        payload.scheduled_date = fmtDate(values.scheduled_date);
        payload.scheduled_time =
          values.scheduled_date && values.scheduled_time
            ? dayjs(values.scheduled_time).format("HH:mm:ss")
            : null;
        payload.due_date = fmtDate(values.due_date);
        payload.owner_id = values.owner?.id ?? null;
        payload.invited_user_ids = (values.invited || []).map((u) => u.id);
        payload.contact_ids = (values.contacts || []).map((c) => c.id);
      }
      try {
        const result = await updateActivity(activity.id, payload);
        if (result?.success) {
          displaySuccessSnackbar("Activity updated");
          onSaved?.();
          closeDrawer();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setSubmitting(false);
      }
    },
  });

  const { values, errors, setFieldValue } = formik;

  // Creation: the account's cycles, and the chosen cycle's steps.
  const { cycles } = useGetDecisionCyclesByAccount(isCreate ? accountId : null);
  const { steps } = useGetDecisionStepsByCycle(isCreate ? values.decision_cycle_id : null);
  const cycleOptions = useMemo(
    () => (cycles || []).map((c) => ({ value: String(c.id), label: c.name })),
    [cycles],
  );
  const stepOptions = useMemo(
    () =>
      [...(steps || [])]
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        .map((st) => ({ value: String(st.id), label: st.name })),
    [steps],
  );
  // The step: the next step's proposal when it is a step of the chosen cycle,
  // else the cycle's CURRENT step (mirror of the backend default,
  // next_step_materialization.py — as ActivityModal).
  useEffect(() => {
    if (!isCreate || values.decision_step_id || !steps?.length) return;
    const proposed = steps.find((st) => String(st.id) === String(nextStep?.suggested_decision_step));
    const chosen = proposed || steps.find((st) => st.is_current);
    if (chosen) setFieldValue("decision_step_id", String(chosen.id));
  }, [isCreate, steps, values.decision_step_id, nextStep?.suggested_decision_step, setFieldValue]);

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => (onCancel ? onCancel() : closeDrawer())}
      saveDisabled={
        isCreate
          ? !formik.isValid || formik.isSubmitting
          : !formik.isValid || !formik.dirty || formik.isSubmitting
      }
    >
      <Stack spacing={1.5} data-testid={isCreate ? "activity-create" : undefined}>
        {/* (1) Title + Type */}
        <InlineEditableValue
          name="title"
          label="Title"
          value={values.title}
          onChange={(v) => setFieldValue("title", v)}
          placeholder="Untitled"
          error={Boolean(errors.title)}
          helperText={errors.title}
        />
        <InlineEditableValue
          name="type"
          label="Type"
          type="select"
          options={TYPE_OPTIONS}
          value={values.activity_type}
          onChange={(v) => setFieldValue("activity_type", v)}
        />

        {/* Creation: the decision cycle (pre-filled, modifiable) and its step. */}
        {isCreate && (
          <>
            <InlineEditableValue
              name="decision_cycle"
              label="Decision cycle"
              type="select"
              options={[{ value: "", label: "No decision cycle" }, ...cycleOptions]}
              value={values.decision_cycle_id}
              onChange={(v) => {
                setFieldValue("decision_cycle_id", v);
                setFieldValue("decision_step_id", "");
              }}
              placeholder="No decision cycle"
            />
            {values.decision_cycle_id && (
              <InlineEditableValue
                name="decision_step"
                label="DC step"
                type="select"
                options={stepOptions}
                value={values.decision_step_id}
                onChange={(v) => setFieldValue("decision_step_id", v)}
                placeholder="No step"
                error={Boolean(errors.decision_step_id)}
                helperText={errors.decision_step_id}
              />
            )}
          </>
        )}

        <Filet />

        {/* (2) Date & time */}
        <DateGroup values={values} setFieldValue={setFieldValue} locked={isCampaign} />
        {Boolean(errors.scheduled_date) && (
          <Typography variant="caption" color="error">
            {errors.scheduled_date}
          </Typography>
        )}

        <Filet />

        {/* (3) Objective + Description */}
        <InlineEditableValue
          name="objective"
          label="Objective"
          value={values.call_to_action}
          onChange={(v) => setFieldValue("call_to_action", v)}
          placeholder="No objective set"
        />
        <InlineEditableValue
          name="description"
          label="Description"
          type="textarea"
          value={values.description}
          onChange={(v) => setFieldValue("description", v)}
          placeholder="No description added"
        />

        <Filet />

        {/* (4) People — editable owner / invited / contacts (draft + global save) */}
        <PeopleSection
          values={values}
          setFieldValue={setFieldValue}
          errors={errors}
          accountId={accountId}
          locked={isCampaign}
          ownerReadOnly={isCreate}
          allowInlineContact={isCreate}
          mentionedNames={isCreate ? defaults.mentionedNames : []}
        />
      </Stack>
    </DrawerContentLayout>
  );
}

ActivityForm.propTypes = {
  activity: PropTypes.object,
  onSaved: PropTypes.func,
  mode: PropTypes.oneOf(["edit", "create"]),
  accountId: PropTypes.string,
  decisionCycleId: PropTypes.string,
  nextStep: PropTypes.object,
  activityType: PropTypes.string,
  /** Create: the names cited with their account contact (read by the gate). */
  citedContacts: PropTypes.arrayOf(PropTypes.object),
  onCreated: PropTypes.func,
  onCancel: PropTypes.func,
};

EditActivityContent.propTypes = {
  /** The activity to edit (its *_detail fields seed the values). Edit mode. */
  activity: PropTypes.object,
  /** Optional callback fired after a successful save (before the coque closes). */
  onSaved: PropTypes.func,
  /** "edit" (default) or "create" (Sprint Next steps 5.8d). */
  mode: PropTypes.oneOf(["edit", "create"]),
  /** Create: the account of the new activity. */
  accountId: PropTypes.string,
  /** Create: the decision cycle pre-filled from the context (modifiable). */
  decisionCycleId: PropTypes.string,
  /** Create: the next step the activity is created from (pre-fill + provenance). */
  nextStep: PropTypes.object,
  /** Create: the type imposed by the entry point. */
  activityType: PropTypes.string,
  /** Create: fired with the created activity (the caller decides what follows). */
  onCreated: PropTypes.func,
  /** Optional Cancel handler (default: the coque closes). */
  onCancel: PropTypes.func,
};
