// frontend/src/sections/activities/workspace/ActivityContextSection.jsx
//
// UX Activity S2a — the READ-ONLY Context display, themed via aphoriQ. Replaces
// the legacy ActivityOverviewTab in the Context block. Order: Objective ·
// Scheduled · Description · Internal team (owner + invited) · External contacts
// (stacked) · Linked context (DC-priority-exclusive, rule a) · Provenance (an
// integrated info line, not an Alert). No editing, no chips, no navigation
// (except the provenance link to the live /activities/{id} route). ComingSoon
// and Previous/Next activity are intentionally absent.
//
// Presentation-only bricks (Surface, LabeledValue, PersonRow) are shared in
// components/display so the upcoming edit / contact drawers reuse them; this
// section only orchestrates them for the activity Context.

"use client";

import PropTypes from "prop-types";
import Link from "next/link";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Primitives
import Surface from "components/display/Surface";
import LabeledValue from "components/display/LabeledValue";
import PersonRow from "components/display/PersonRow";

// ==============================|| FORMAT HELPERS ||============================== //

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatTime(timeStr) {
  if (!timeStr) return null;
  try {
    return new Date(`1970-01-01T${timeStr}`).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return timeStr;
  }
}

// Prefer a scheduled date (+ time), else a due date. Returns { label, value }.
function getSchedule(activity) {
  if (activity?.scheduled_date) {
    const date = formatDate(activity.scheduled_date);
    const time = formatTime(activity.scheduled_time);
    return { label: "Scheduled", value: time ? `${date} · ${time}` : date };
  }
  if (activity?.due_date) {
    return { label: "Due date", value: formatDate(activity.due_date) };
  }
  return { label: "Scheduled", value: null };
}

function ownerLine(user) {
  if (!user) return null;
  return { name: user.full_name || user.email, secondary: user.email };
}

function contactSecondary(contact) {
  return [contact.job_title, contact.department_name].filter(Boolean).join(" · ") || null;
}

function contactTertiary(contact) {
  return [contact.email, contact.phone_number].filter(Boolean).join(" · ") || null;
}

// ==============================|| SECTION CARD ||============================== //

function ContextCard({ title, children }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <Surface level="level2" radius="lg" data-testid="ctx-card" sx={{ p: 2.5 }}>
      <Typography
        variant="subtitle2"
        sx={{ color: aq.text.muted, mb: 1.5, display: "block" }}
      >
        {title}
      </Typography>
      {children}
    </Surface>
  );
}

ContextCard.propTypes = {
  title: PropTypes.string.isRequired,
  children: PropTypes.node,
};

// ==============================|| LINKED CONTEXT (rule a) ||============================== //

function LinkedContext({ activity }) {
  const dc = activity?.decision_cycle_detail;
  const step = activity?.decision_step_detail;
  const campaign = activity?.campaign_detail;

  // Rule (a): a decision cycle takes priority and is exclusive — the campaign is
  // never shown alongside it.
  if (dc) {
    const stepValue = step
      ? step.stage_display
        ? `${step.name} · ${step.stage_display}`
        : step.name
      : null;
    return (
      <Stack spacing={1.5}>
        <LabeledValue label="Decision cycle" value={dc.name} />
        <LabeledValue label="Step" value={stepValue} />
      </Stack>
    );
  }

  if (campaign) {
    return (
      <Stack spacing={1.5}>
        <LabeledValue label="Campaign" value={campaign.name} />
        <LabeledValue label="Campaign status" value={campaign.campaign_status} />
        <LabeledValue
          label="Sequence"
          value={campaign.sequence_position != null ? `Step ${campaign.sequence_position}` : null}
        />
      </Stack>
    );
  }

  return (
    <Typography variant="body2" sx={{ color: (t) => t.aphoriQ.text.subtle, fontStyle: "italic" }}>
      Not linked to a campaign or decision cycle.
    </Typography>
  );
}

LinkedContext.propTypes = { activity: PropTypes.object };

// ==============================|| PROVENANCE (integrated line) ||============================== //

function Provenance({ activity }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const src = activity?.source_activity_detail;
  if (!src) return null;

  const type = src.source_context?.type;
  const prefix =
    type === "CAMPAIGN"
      ? "From campaign"
      : type === "DECISION_CYCLE"
        ? "From decision cycle"
        : "Created manually";

  // The label to display: the source activity title when there is one, else the
  // context name (campaign / cycle name).
  const label = src.title || src.source_context?.name || null;

  return (
    <Typography variant="body2" sx={{ color: aq.text.muted }}>
      {prefix}
      {label ? ": " : ""}
      {label &&
        (src.id ? (
          <Box
            component={Link}
            href={`/activities/${src.id}`}
            sx={{ color: aq.accent, textDecoration: "none", "&:hover": { textDecoration: "underline" } }}
          >
            {label}
          </Box>
        ) : (
          <Box component="span" sx={{ color: "text.primary" }}>
            {label}
          </Box>
        ))}
    </Typography>
  );
}

Provenance.propTypes = { activity: PropTypes.object };

// ==============================|| ACTIVITY CONTEXT SECTION ||============================== //

export default function ActivityContextSection({ activity }) {
  if (!activity) return null;

  const schedule = getSchedule(activity);
  const owner = ownerLine(activity.owner_detail);
  const invited = activity.invited_users_detail || [];
  const contacts = activity.contacts_detail || [];
  const hasProvenance = Boolean(activity.source_activity_detail);

  return (
    <Stack spacing={2}>
      {/* Details */}
      <ContextCard title="Details">
        <Stack spacing={1.5}>
          <LabeledValue
            label="Objective"
            value={activity.call_to_action}
            placeholder="No objective defined"
          />
          <LabeledValue label={schedule.label} value={schedule.value} />
          <LabeledValue label="Description" value={activity.description} />
        </Stack>
      </ContextCard>

      {/* People */}
      <ContextCard title="People">
        <Stack spacing={2}>
          <Box>
            <Typography variant="caption" sx={{ color: (t) => t.aphoriQ.text.muted, display: "block", mb: 0.5 }}>
              Internal team
            </Typography>
            {owner && <PersonRow name={owner.name} secondary={owner.secondary} />}
            {invited.map((u) => {
              const line = ownerLine(u);
              return <PersonRow key={u.id} name={line?.name} secondary={line?.secondary} />;
            })}
            {!owner && invited.length === 0 && (
              <Typography variant="body2" sx={{ color: (t) => t.aphoriQ.text.subtle, fontStyle: "italic" }}>
                No internal team
              </Typography>
            )}
          </Box>

          <Box>
            <Typography variant="caption" sx={{ color: (t) => t.aphoriQ.text.muted, display: "block", mb: 0.5 }}>
              External contacts
            </Typography>
            {contacts.length > 0 ? (
              <Stack spacing={0.5}>
                {contacts.map((c) => (
                  <PersonRow
                    key={c.id}
                    name={c.full_name || `${c.first_name || ""} ${c.last_name || ""}`.trim()}
                    secondary={contactSecondary(c)}
                    tertiary={contactTertiary(c)}
                  />
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" sx={{ color: (t) => t.aphoriQ.text.subtle, fontStyle: "italic" }}>
                No contacts linked
              </Typography>
            )}
          </Box>
        </Stack>
      </ContextCard>

      {/* Linked context + provenance */}
      <ContextCard title="Linked context">
        <Stack spacing={1.5}>
          <LinkedContext activity={activity} />
          {hasProvenance && <Provenance activity={activity} />}
        </Stack>
      </ContextCard>
    </Stack>
  );
}

ActivityContextSection.propTypes = {
  activity: PropTypes.object,
};
