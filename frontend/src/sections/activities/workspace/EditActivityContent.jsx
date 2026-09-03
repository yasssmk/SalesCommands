// frontend/src/sections/activities/workspace/EditActivityContent.jsx
//
// S2c-2.2 — the Activity EDIT drawer, injected as a SHELL-LESS node into the
// shared WorkspaceDrawer coque via openDrawer(<EditActivityContent activity=… />).
// The coque provides the shell (close button + padded scroll body + width); this
// node renders a bold "Edit activity" h3 title + FOUR stacked SECTION BOXES,
// separated by the header hairline filet:
//
//   (1) Title & type · (2) Date & time · (3) Objective & description ·
//   (4) People (owner · invited · contacts)
//
// Each section is a self-contained box (background.default ground, radius lg)
// that DISPLAYS the current values and carries an "Edit" button. In this step the
// Edit button is inert — per-section read↔edit + partial PATCH save lands in
// S2c-2.3 (cloning UnifiedDateSection's local read/edit mechanics). Edits stay
// scoped to CONTENT fields only (no status, no cycle/step). Themed via aphoriQ/
// MUI — no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";
import dayjs from "dayjs";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import EditOutlined from "@ant-design/icons/EditOutlined";

// Project
import { ACTIVITY_TYPE_LABELS } from "api/accounts/activities";
import LabeledValue from "components/display/LabeledValue";
import PersonRow from "components/display/PersonRow";

// ==============================|| HELPERS ||============================== //

function typeLabel(value) {
  return ACTIVITY_TYPE_LABELS[value] || value || "—";
}

function fmtDate(v) {
  return v ? dayjs(v).format("MMM D, YYYY") : null;
}

function fmtTime(t) {
  return t ? dayjs(`1970-01-01T${t}`).format("h:mm A") : null;
}

function personName(p) {
  if (!p) return null;
  return p.full_name || [p.first_name, p.last_name].filter(Boolean).join(" ") || p.email || null;
}

function scheduledDisplay(activity) {
  const date = fmtDate(activity?.scheduled_date);
  if (!date) return null;
  const time = fmtTime(activity?.scheduled_time);
  return time ? `${date} · ${time}` : date;
}

// ==============================|| SECTION SHELL ||============================== //

// The hairline filet, identical to the workspace header separator
// (WorkspaceHeader.jsx:104-108): a top border in the aphoriQ hairline width/color.
function Filet() {
  const aq = useTheme().aphoriQ;
  return (
    <Box
      data-testid="section-filet"
      sx={{
        borderTopStyle: "solid",
        borderTopWidth: aq.border.width.hairline,
        borderTopColor: aq.border.color,
      }}
    />
  );
}

// A section box: the page background ground + radius lg, a header row (muted
// title + an Edit button) and the read content. `onEdit` is wired in S2c-2.3;
// while undefined the Edit button is inert (renders, does nothing on click).
function SectionBox({ title, onEdit, children }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <Box
      data-testid="edit-section"
      sx={{
        backgroundColor: "background.default",
        borderRadius: `${aq.radius.lg}px`,
        p: 2,
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="caption" sx={{ color: aq.text.muted }}>
          {title}
        </Typography>
        <Button
          size="small"
          variant="text"
          onClick={onEdit}
          startIcon={<EditOutlined style={{ fontSize: theme.iconSizes.sm }} />}
        >
          Edit
        </Button>
      </Stack>
      <Stack spacing={1.5}>{children}</Stack>
    </Box>
  );
}

SectionBox.propTypes = {
  title: PropTypes.string.isRequired,
  onEdit: PropTypes.func,
  children: PropTypes.node,
};

// ==============================|| EDIT ACTIVITY CONTENT ||============================== //

export default function EditActivityContent({ activity }) {
  const aq = useTheme().aphoriQ;

  const scheduled = scheduledDisplay(activity);
  const due = fmtDate(activity?.due_date);
  const owner = personName(activity?.owner_detail);
  const invited = activity?.invited_users_detail || [];
  const contacts = activity?.contacts_detail || [];

  return (
    <Stack spacing={2}>
      <Typography variant="h3" component="h2" sx={{ fontWeight: "bold" }}>
        Edit activity
      </Typography>

      {/* (1) Title & type */}
      <SectionBox title="Title & type">
        <LabeledValue label="Title" value={activity?.title} placeholder="Untitled" strong />
        <LabeledValue label="Type" value={typeLabel(activity?.activity_type)} />
      </SectionBox>

      <Filet />

      {/* (2) Date & time */}
      <SectionBox title="Date & time">
        {scheduled && <LabeledValue label="Scheduled" value={scheduled} strong />}
        {due && <LabeledValue label="Due date" value={due} strong />}
        {!scheduled && !due && (
          <LabeledValue label="Date" placeholder="No date set" />
        )}
      </SectionBox>

      <Filet />

      {/* (3) Objective & description */}
      <SectionBox title="Objective & description">
        <LabeledValue label="Objective" value={activity?.call_to_action} placeholder="No objective set" />
        <LabeledValue
          label="Description"
          value={activity?.description}
          placeholder="No description added"
        />
      </SectionBox>

      <Filet />

      {/* (4) People */}
      <SectionBox title="People">
        <Box>
          <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
            Owner
          </Typography>
          {owner ? <PersonRow name={owner} suffix="owner" /> : (
            <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
              No owner
            </Typography>
          )}
        </Box>

        <Box>
          <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
            Invited users
          </Typography>
          {invited.length > 0 ? (
            invited.map((u) => <PersonRow key={u.id} name={personName(u)} />)
          ) : (
            <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
              None
            </Typography>
          )}
        </Box>

        <Box>
          <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
            Contacts
          </Typography>
          {contacts.length > 0 ? (
            contacts.map((c) => <PersonRow key={c.id} name={personName(c)} />)
          ) : (
            <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
              None
            </Typography>
          )}
        </Box>
      </SectionBox>
    </Stack>
  );
}

EditActivityContent.propTypes = {
  /** The activity to edit (its *_detail fields seed the displayed values). */
  activity: PropTypes.object.isRequired,
};
