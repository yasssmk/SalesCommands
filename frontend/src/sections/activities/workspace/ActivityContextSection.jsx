// frontend/src/sections/activities/workspace/ActivityContextSection.jsx
//
// UX Activity S2a — the READ-ONLY Context card, themed via aphoriQ, copied from
// the mockup. One compact Surface card:
//   header: (i) "Context" (bold)
//   Details: Objective | Scheduled (bold values), then Description (bold)
//   ── hairline ──
//   People: Internal team | External contacts — bold name + inline suffix (no
//           avatar). External contact names look clickable (pointer + hover) but
//           carry no handler yet — the drawer is wired in a later sprint. No
//           email/phone on the rows.
//   ── hairline ──  (only when there is provenance)
//   Origin: a single provenance line (where the activity was born), a branch
//           icon + TWO separate accent links (context, then activity) to live
//           routes. The current campaign/DC rattachement is NOT shown here
//           (it lives in the header).
// Read-only: the only navigation is the accent links to live routes. No editing,
// no ComingSoon, no Previous/Next. Weights/colours/sizes come from the theme.

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

// Drawer — clicking a person opens its read-only fiche in the coque
// (external contact → Contact fiche; internal team member → User fiche).
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import ContactDrawerContent from "sections/activities/workspace/ContactDrawerContent";
import UserDrawerContent from "sections/activities/workspace/UserDrawerContent";

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

// ==============================|| SHARED SMALL PIECES ||============================== //

function TwoColRow({ children }) {
  return (
    <Box
      data-testid="ctx-grid"
      sx={{
        display: "grid",
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

// Column header: a muted label. (The inert "+" was removed in S2c-2.)
function ColumnHeader({ label }) {
  const aq = useTheme().aphoriQ;
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
      <Typography variant="caption" sx={{ color: aq.text.muted }}>
        {label}
      </Typography>
    </Stack>
  );
}

ColumnHeader.propTypes = { label: PropTypes.string.isRequired };

// An aphoriQ-accent navigation link to a live route (read-only).
function AccentLink({ href, bold = false, children }) {
  const aq = useTheme().aphoriQ;
  return (
    <Box
      component={Link}
      href={href}
      sx={{
        color: aq.accent,
        fontWeight: bold ? "bold" : "regular",
        textDecoration: "none",
        "&:hover": { textDecoration: "underline" },
      }}
    >
      {children}
    </Box>
  );
}

AccentLink.propTypes = { href: PropTypes.string.isRequired, bold: PropTypes.bool, children: PropTypes.node };

// ==============================|| ORIGIN — PROVENANCE (single line) ||============================== //

function ProvenanceLine({ activity }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const src = activity.source_activity_detail;
  const type = src.source_context?.type;
  const ctxName = src.source_context?.name;
  const ctxId = src.source_context?.id;
  const accountId = activity.account_detail?.id || activity.account;

  const titleNode = src.title
    ? src.id
      ? <AccentLink href={`/activities/${src.id}`}>{src.title}</AccentLink>
      : <Box component="span" sx={{ color: "text.primary" }}>{src.title}</Box>
    : null;

  const sep = <Box component="span" sx={{ color: aq.text.muted }}>{" › "}</Box>;

  let body;
  if (type === "CAMPAIGN") {
    body = (
      <>
        {"From campaign "}
        <AccentLink bold href={`/campaigns/${ctxId}`}>{ctxName}</AccentLink>
        {titleNode && <>{sep}{titleNode}</>}
      </>
    );
  } else if (type === "DECISION_CYCLE") {
    // No origin step in the payload (source_context = {type,id,name}) — omit it.
    body = (
      <>
        {"From Decision Cycle "}
        <AccentLink bold href={`/accounts/${accountId}/dc/${ctxId}?tab=timeline`}>{ctxName}</AccentLink>
        {titleNode && <>{sep}{titleNode}</>}
      </>
    );
  } else {
    body = <>{"From "}{titleNode || ctxName}</>;
  }

  return (
    <Stack direction="row" spacing={1} alignItems="flex-start">
      <Box sx={{ mt: 0.25, flexShrink: 0 }}>
        <BranchesOutlined style={{ fontSize: theme.iconSizes.sm, color: aq.accent, display: "flex" }} />
      </Box>
      <Typography variant="body2" sx={{ color: aq.text.muted, minWidth: 0 }}>
        {body}
      </Typography>
    </Stack>
  );
}

ProvenanceLine.propTypes = { activity: PropTypes.object };

// ==============================|| ACTIVITY CONTEXT SECTION ||============================== //

export default function ActivityContextSection({ activity }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const { openDrawer } = useWorkspaceDrawer();

  if (!activity) return null;

  const schedule = getSchedule(activity);
  const owner = activity.owner_detail;
  const invited = activity.invited_users_detail || [];
  const contacts = activity.contacts_detail || [];
  const hasProvenance = Boolean(activity.source_activity_detail);

  const emptyItalic = { color: aq.text.subtle, fontStyle: "italic" };

  return (
    <Surface level="level2" radius="lg" data-testid="ctx-card" sx={{ p: 2.5 }}>
      {/* Card title (bold) */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <InfoCircleOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.text.primary }} />
        <Typography variant="subtitle2" color="text.primary" sx={{ fontWeight: "bold" }}>
          Context
        </Typography>
      </Stack>

      <Stack spacing={2}>
        {/* Group 1 — Details */}
        <Stack spacing={1.5}>
          <TwoColRow>
            <LabeledValue
              dense
              strong
              label="Objective"
              value={activity.call_to_action}
              placeholder="Click to define an objective…"
            />
            <Box sx={{ textAlign: { md: "right" } }}>
              <LabeledValue dense strong label={schedule.label} value={schedule.value} />
            </Box>
          </TwoColRow>
          <LabeledValue
            dense
            strong
            label="Description"
            value={activity.description}
            placeholder="Click to add a description…"
          />
        </Stack>

        <GroupRule />

        {/* Group 2 — People (avatars, no coordinates) */}
        <TwoColRow>
          <Box>
            <ColumnHeader label="Internal team" />
            {owner && (
              <PersonRow
                interactive
                onClick={() =>
                  openDrawer(<UserDrawerContent userId={owner.id} />, { title: "Team member" })
                }
                name={personName(owner)}
                suffix="owner"
              />
            )}
            {invited.map((u) => (
              <PersonRow
                key={u.id}
                interactive
                onClick={() =>
                  openDrawer(<UserDrawerContent userId={u.id} />, { title: "Team member" })
                }
                name={personName(u)}
                suffix="invited"
              />
            ))}
            {!owner && invited.length === 0 && (
              <Typography variant="body2" sx={emptyItalic}>
                No internal team
              </Typography>
            )}
          </Box>

          <Box>
            <ColumnHeader label="External contacts" />
            {contacts.length > 0 ? (
              <Stack spacing={0.5}>
                {contacts.map((c) => (
                  <PersonRow
                    key={c.id}
                    interactive
                    onClick={() =>
                      openDrawer(
                        <ContactDrawerContent contactId={c.id} activity={activity} />,
                        { title: "Contact" },
                      )
                    }
                    name={personName(c)}
                    suffix={[c.job_title, c.department_name].filter(Boolean).join(" · ") || undefined}
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

        {/* Group 3 — Origin (provenance only, conditional) */}
        {hasProvenance && (
          <>
            <GroupRule />
            <ProvenanceLine activity={activity} />
          </>
        )}
      </Stack>
    </Surface>
  );
}

ActivityContextSection.propTypes = {
  activity: PropTypes.object,
};
