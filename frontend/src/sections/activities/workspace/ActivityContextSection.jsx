// frontend/src/sections/activities/workspace/ActivityContextSection.jsx
//
// UX Activity S2a — the READ-ONLY Context card, themed via aphoriQ, matched to
// the mockup. One compact Surface card:
//   Details (Objective | Scheduled, then Description)
//   ── hairline ──
//   People (Internal team | External contacts, stacked, no avatars)
//   ── hairline ──  (only when there is an origin group)
//   Origin: provenance line (where the activity was born) + the current
//           campaign/DC rattachement line, under a branch icon.
// Read-only: the only navigation is the accent links to live routes
// (/campaigns/{id}, /accounts/{accountId}/dc/{cycleId}?tab=timeline,
// /activities/{id}). No editing, no chips, no avatars, no ComingSoon/prev-next.

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
import BranchesOutlined from "@ant-design/icons/BranchesOutlined";

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

function personName(p) {
  if (!p) return null;
  return p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.email || null;
}

function contactCoords(contact) {
  return [contact.email, contact.phone_number].filter(Boolean).join(" · ") || null;
}

// ==============================|| SHARED SMALL PIECES ||============================== //

// Responsive two-column grid row (1 column on narrow, 2 columns on md+).
function TwoColRow({ children }) {
  return (
    <Box
      data-testid="ctx-grid"
      sx={{
        display: "grid",
        // minmax(0, 1fr) tracks: long values (emails, phones) wrap inside their
        // cell instead of overflowing under the other column — no overlap.
        gridTemplateColumns: { xs: "minmax(0, 1fr)", md: "minmax(0, 1fr) minmax(0, 1fr)" },
        alignItems: "start",
        columnGap: 4,
        rowGap: 1.5,
      }}
    >
      {children}
    </Box>
  );
}

TwoColRow.propTypes = { children: PropTypes.node };

// A discreet hairline rule separating the card's groups (aphoriQ border token).
function GroupRule() {
  const theme = useTheme();
  return (
    <Box
      data-testid="ctx-sep"
      sx={{
        borderTopStyle: "solid",
        borderTopWidth: theme.aphoriQ.border.width.hairline,
        borderTopColor: theme.aphoriQ.border.color,
      }}
    />
  );
}

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

// An aphoriQ-accent navigation link to a live route (read-only, no drawer).
function AccentLink({ href, children }) {
  const aq = useTheme().aphoriQ;
  return (
    <Box
      component={Link}
      href={href}
      sx={{
        color: aq.accent,
        textDecoration: "none",
        "&:hover": { textDecoration: "underline" },
      }}
    >
      {children}
    </Box>
  );
}

AccentLink.propTypes = { href: PropTypes.string.isRequired, children: PropTypes.node };

// ==============================|| ORIGIN — PROVENANCE LINE ||============================== //

// Where the activity was BORN (source_activity_detail). Caller guarantees the
// payload is non-null. Three cases: CAMPAIGN / DECISION_CYCLE / MANUAL.
function ProvenanceLine({ activity }) {
  const aq = useTheme().aphoriQ;
  const src = activity.source_activity_detail;
  const type = src.source_context?.type;
  const ctxName = src.source_context?.name;
  const ctxId = src.source_context?.id;
  const accountName = activity.account_detail?.company_name;
  const accountId = activity.account_detail?.id || activity.account;

  // The source activity title, linked when its id is present.
  const titleNode = src.title
    ? src.id
      ? <AccentLink href={`/activities/${src.id}`}>{src.title}</AccentLink>
      : <Box component="span" sx={{ color: "text.primary" }}>{src.title}</Box>
    : null;

  let body;
  if (type === "CAMPAIGN") {
    body = (
      <>
        {"From campaign "}
        <AccentLink href={`/campaigns/${ctxId}`}>{ctxName}</AccentLink>
        {accountName && (
          <>
            {" › "}
            <Box component="span" sx={{ color: "text.primary" }}>{accountName}</Box>
          </>
        )}
        {titleNode && (
          <>
            {" — "}
            {titleNode}
          </>
        )}
      </>
    );
  } else if (type === "DECISION_CYCLE") {
    body = (
      <>
        {"From "}
        <AccentLink href={`/accounts/${accountId}/dc/${ctxId}?tab=timeline`}>{ctxName}</AccentLink>
        {titleNode && (
          <>
            {" — "}
            {titleNode}
          </>
        )}
      </>
    );
  } else {
    body = <>{"From "}{titleNode || ctxName}</>;
  }

  return (
    <Typography variant="body2" sx={{ color: aq.text.muted }}>
      {body}
    </Typography>
  );
}

ProvenanceLine.propTypes = { activity: PropTypes.object };

// ==============================|| ORIGIN — CURRENT RATTACHEMENT LINE ||============================== //

// The current campaign / decision-cycle rattachement, inline (dot-separated).
// Rule (a): a decision cycle takes priority and is exclusive over the campaign.
function LinkedInline({ activity }) {
  const aq = useTheme().aphoriQ;
  const dc = activity.decision_cycle_detail;
  const step = activity.decision_step_detail;
  const campaign = activity.campaign_detail;
  const accountId = activity.account_detail?.id || activity.account;
  const contactName = personName(activity.contacts_detail?.[0]);

  let parts;
  if (dc) {
    parts = [
      <AccentLink key="dc" href={`/accounts/${accountId}/dc/${dc.id}?tab=timeline`}>{dc.name}</AccentLink>,
      step?.name || null,
      step?.stage_display || null,
    ];
  } else if (campaign) {
    parts = [
      <AccentLink key="cmp" href={`/campaigns/${campaign.id}`}>{campaign.name}</AccentLink>,
      campaign.sequence_position != null ? `Step ${campaign.sequence_position}` : null,
      campaign.campaign_status || null,
      contactName,
    ];
  } else {
    return null;
  }

  const items = parts.filter(Boolean);
  return (
    <Typography variant="body2" sx={{ color: aq.text.muted }}>
      {items.map((p, i) => (
        <Box component="span" key={i}>
          {i > 0 && " · "}
          {p}
        </Box>
      ))}
    </Typography>
  );
}

LinkedInline.propTypes = { activity: PropTypes.object };

// ==============================|| ACTIVITY CONTEXT SECTION ||============================== //

export default function ActivityContextSection({ activity }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  if (!activity) return null;

  const schedule = getSchedule(activity);
  const owner = activity.owner_detail;
  const invited = activity.invited_users_detail || [];
  const contacts = activity.contacts_detail || [];

  const hasProvenance = Boolean(activity.source_activity_detail);
  const hasLinked = Boolean(activity.decision_cycle_detail || activity.campaign_detail);
  const hasOrigin = hasProvenance || hasLinked;

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
        {/* Group 1 — Details */}
        <Stack spacing={1.5}>
          <TwoColRow>
            <LabeledValue
              dense
              label="Objective"
              value={activity.call_to_action}
              placeholder="Click to define an objective…"
            />
            <Box sx={{ textAlign: { md: "right" } }}>
              <LabeledValue dense label={schedule.label} value={schedule.value} />
            </Box>
          </TwoColRow>
          <LabeledValue dense label="Description" value={activity.description} />
        </Stack>

        <GroupRule />

        {/* Group 2 — People (no avatars) */}
        <TwoColRow>
          <Box>
            <SubLabel>Internal team</SubLabel>
            {owner && (
              <PersonRow name={personName(owner)} suffix="owner" secondary={owner.email} />
            )}
            {invited.map((u) => (
              <PersonRow key={u.id} name={personName(u)} suffix="invited" secondary={u.email} />
            ))}
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
                    name={personName(c)}
                    suffix={c.department_name || undefined}
                    tertiary={contactCoords(c)}
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

        {/* Group 3 — Origin: provenance + current rattachement (branch icon) */}
        {hasOrigin && (
          <>
            <GroupRule />
            <Stack direction="row" spacing={1} alignItems="flex-start">
              <Box sx={{ mt: 0.25, flexShrink: 0 }}>
                <BranchesOutlined
                  style={{ fontSize: theme.iconSizes.sm, color: aq.text.muted, display: "flex" }}
                />
              </Box>
              <Stack spacing={0.25} sx={{ minWidth: 0 }}>
                {hasProvenance && <ProvenanceLine activity={activity} />}
                {hasLinked && <LinkedInline activity={activity} />}
              </Stack>
            </Stack>
          </>
        )}
      </Stack>
    </Surface>
  );
}

ActivityContextSection.propTypes = {
  activity: PropTypes.object,
};
