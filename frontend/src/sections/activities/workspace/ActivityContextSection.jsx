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

// Icons
import InfoCircleOutlined from "@ant-design/icons/InfoCircleOutlined";

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

// Responsive two-column grid row (1 column on narrow, 2 columns on md+).
function TwoColRow({ children }) {
  return (
    <Box
      data-testid="ctx-grid"
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
        columnGap: 3,
        rowGap: 1.5,
      }}
    >
      {children}
    </Box>
  );
}

TwoColRow.propTypes = { children: PropTypes.node };

// Small muted sub-heading inside the single card (e.g. "Internal team").
function SubLabel({ children }) {
  const theme = useTheme();
  return (
    <Typography
      variant="caption"
      sx={{ color: theme.aphoriQ.text.muted, display: "block", mb: 0.5 }}
    >
      {children}
    </Typography>
  );
}

SubLabel.propTypes = { children: PropTypes.node };

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
      <TwoColRow>
        <LabeledValue dense label="Decision cycle" value={dc.name} />
        <LabeledValue dense label="Step" value={stepValue} />
      </TwoColRow>
    );
  }

  if (campaign) {
    return (
      <TwoColRow>
        <LabeledValue dense label="Campaign" value={campaign.name} />
        <LabeledValue
          dense
          label="Sequence"
          value={
            campaign.sequence_position != null
              ? `Step ${campaign.sequence_position} · ${campaign.campaign_status}`
              : campaign.campaign_status
          }
        />
      </TwoColRow>
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

  const theme = useTheme();
  const aq = theme.aphoriQ;

  const emptyItalic = { color: aq.text.subtle, fontStyle: "italic" };

  return (
    <Surface level="level2" radius="lg" data-testid="ctx-card" sx={{ p: 2.5 }}>
      {/* Card title */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <InfoCircleOutlined style={{ fontSize: theme.iconSizes.sm, color: aq.text.muted }} />
        <Typography variant="subtitle2" sx={{ color: aq.text.muted }}>
          Context
        </Typography>
      </Stack>

      <Stack spacing={2}>
        {/* Row 1 — Objective (left) · Scheduled (right, right-aligned) */}
        <TwoColRow>
          <LabeledValue
            dense
            label="Objective"
            value={activity.call_to_action}
            placeholder="No objective defined"
          />
          <Box sx={{ textAlign: { md: "right" } }}>
            <LabeledValue dense label={schedule.label} value={schedule.value} />
          </Box>
        </TwoColRow>

        {/* Description — full width */}
        <LabeledValue dense label="Description" value={activity.description} />

        {/* People — Internal team (left) · External contacts (right) */}
        <TwoColRow>
          <Box>
            <SubLabel>Internal team</SubLabel>
            {owner && <PersonRow name={owner.name} secondary={owner.secondary} />}
            {invited.map((u) => {
              const line = ownerLine(u);
              return <PersonRow key={u.id} name={line?.name} secondary={line?.secondary} />;
            })}
            {!owner && invited.length === 0 && (
              <Typography variant="body2" sx={emptyItalic}>
                No internal team
              </Typography>
            )}
          </Box>

          <Box>
            <SubLabel>External contacts</SubLabel>
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
              <Typography variant="body2" sx={emptyItalic}>
                No contacts linked
              </Typography>
            )}
          </Box>
        </TwoColRow>

        {/* Linked context (rule a, compact) */}
        <LinkedContext activity={activity} />

        {/* Provenance — integrated info line, full width */}
        {hasProvenance && <Provenance activity={activity} />}
      </Stack>
    </Surface>
  );
}

ActivityContextSection.propTypes = {
  activity: PropTypes.object,
};
