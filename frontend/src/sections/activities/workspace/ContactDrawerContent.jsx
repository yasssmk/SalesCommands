// frontend/src/sections/activities/workspace/ContactDrawerContent.jsx
//
// CT-2b — the READ-ONLY Contact fiche injected into the WorkspaceDrawer coque
// (title "Contact" comes from openDrawer). Lives next to OutcomeDrawerContent /
// EditActivityContent: same drawer-content family, and it is activity-scoped
// (it needs the activity's decision_cycle to read DC people).
//
// STRICT separation of the three levels:
//   - Contact  (durable identity + coordinates) → useGetContact(contactId)
//   - Role     (deal-scoped) is READ from the contact's QUALIFIED entry in DC
//              people — never from a PeopleSignal or a cluster directly →
//              useGetDCPeople(activity.decision_cycle)
//   - Cluster  backend only, unused here.
//
// Built on DrawerContentLayout WITHOUT onSave/onCancel → no global action bar
// (CT-1). The fiche's own actions (Edit + "See signals") live in the BODY and
// are inert for now (Edit → CT-3; signals → future).
//
// Layout (maquette Drawer_People): identity (avatar + name + job · dept) — rule
// — coordinates (email / phone / linkedin, a line dropped when empty) —
// "Involved in N activities" encart (only inside a DC, from the qualified
// entry) — rule — decision role (only when a role is known). Theme tokens only,
// no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import MailOutlined from "@ant-design/icons/MailOutlined";
import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import LinkedinOutlined from "@ant-design/icons/LinkedinOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import RadarChartOutlined from "@ant-design/icons/RadarChartOutlined";

// Project
import { useGetContact } from "api/businessData/contacts";
import { useGetDCPeople } from "api/accounts/decisionCycles";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import Surface from "components/display/Surface";

// ==============================|| HELPERS ||============================== //

function initials(contact) {
  const f = (contact?.first_name || "").trim();
  const l = (contact?.last_name || "").trim();
  const two = `${f.charAt(0)}${l.charAt(0)}`.trim();
  if (two) return two.toUpperCase();
  const name = (contact?.full_name || contact?.email || "").trim();
  return name ? name.charAt(0).toUpperCase() : "?";
}

function fullName(contact) {
  return (
    contact?.full_name ||
    `${contact?.first_name || ""} ${contact?.last_name || ""}`.trim() ||
    contact?.email ||
    "Contact"
  );
}

// A themed hairline rule (same form as the Context card's GroupRule).
function Rule() {
  const aq = useTheme().aphoriQ;
  return (
    <Box
      sx={{
        borderTopStyle: "solid",
        borderTopWidth: aq.border.width.hairline,
        borderTopColor: aq.border.color,
      }}
    />
  );
}

// One coordinate line: icon + value. `href` makes the value an accent link
// (email / linkedin); otherwise it is plain text (phone). Renders nothing when
// the value is empty, so blank channels drop out of the stack.
function CoordinateLine({ icon: Icon, value, href, ariaLabel }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  if (!value) return null;

  const valueNode = href ? (
    <Box
      component="a"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={ariaLabel}
      sx={{
        color: aq.accent,
        textDecoration: "none",
        wordBreak: "break-word",
        "&:hover": { textDecoration: "underline" },
      }}
    >
      {value}
    </Box>
  ) : (
    <Typography variant="body2" color="text.primary" sx={{ wordBreak: "break-word" }}>
      {value}
    </Typography>
  );

  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Box sx={{ flexShrink: 0, display: "flex" }}>
        <Icon style={{ fontSize: theme.iconSizes.sm, color: aq.text.muted }} />
      </Box>
      {valueNode}
    </Stack>
  );
}

CoordinateLine.propTypes = {
  icon: PropTypes.elementType.isRequired,
  value: PropTypes.string,
  href: PropTypes.string,
  ariaLabel: PropTypes.string,
};

// ==============================|| CONTACT DRAWER CONTENT ||============================== //

export default function ContactDrawerContent({ contactId, activity }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  // Hooks are always called (no conditional hooks); the DC people fetch is a
  // no-op when the activity carries no decision_cycle (campaign activity).
  const { contact, contactLoading, contactError } = useGetContact(contactId);
  const cycleId = activity?.decision_cycle || null;
  const { people } = useGetDCPeople(cycleId);

  // The contact's QUALIFIED entry in DC people (the one that carries the role).
  const qualified = people?.qualified || [];
  const dcEntry =
    qualified.find((q) => q?.target_contact?.id === contactId) || null;

  // ---- loading / error (no crash, discreet) ----
  if (contactLoading) {
    return (
      <DrawerContentLayout>
        <Box
          data-testid="contact-loading"
          sx={{ display: "flex", justifyContent: "center", py: 4 }}
        >
          <CircularProgress size={theme.iconSizes.md} />
        </Box>
      </DrawerContentLayout>
    );
  }

  if (contactError || !contact) {
    return (
      <DrawerContentLayout>
        <Typography variant="body2" sx={{ color: aq.text.muted }}>
          This contact could not be loaded.
        </Typography>
      </DrawerContentLayout>
    );
  }

  const jobDept = [contact.job_title, contact.department_name].filter(Boolean).join(" · ");

  // Role is shown only when a qualified DC entry exists AND carries a role.
  const roleLabel = dcEntry ? dcEntry.role_display || dcEntry.role : null;
  const influenceLabel = dcEntry ? dcEntry.influence_display || dcEntry.influence : null;
  const showRole = Boolean(roleLabel);

  // Activities encart only inside a DC and when the contact is in DC people.
  const showActivities = Boolean(dcEntry) && typeof dcEntry.activity_count === "number";

  return (
    <DrawerContentLayout>
      <Stack spacing={2}>
        {/* Identity */}
        <Stack direction="row" spacing={2} alignItems="center">
          <Box
            aria-hidden
            sx={{
              flexShrink: 0,
              width: theme.spacing(6),
              height: theme.spacing(6),
              borderRadius: "50%",
              backgroundColor: aq.surface.level2,
              border: `${aq.border.width.hairline}px solid ${aq.border.color}`,
              color: aq.accent,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: "bold",
            }}
          >
            {initials(contact)}
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="subtitle1" color="text.primary" sx={{ fontWeight: "bold" }}>
              {fullName(contact)}
            </Typography>
            {jobDept && (
              <Typography variant="body2" sx={{ color: aq.text.muted }}>
                {jobDept}
              </Typography>
            )}
          </Box>
        </Stack>

        <Rule />

        {/* Coordinates — a line drops out when empty */}
        <Stack spacing={1}>
          <CoordinateLine
            icon={MailOutlined}
            value={contact.email}
            href={contact.email ? `mailto:${contact.email}` : undefined}
            ariaLabel={contact.email}
          />
          <CoordinateLine icon={PhoneOutlined} value={contact.phone_number} />
          <CoordinateLine
            icon={LinkedinOutlined}
            value={contact.linkedin}
            href={contact.linkedin || undefined}
            ariaLabel="LinkedIn profile"
          />
        </Stack>

        {/* Involved in N activities — from the qualified DC entry */}
        {showActivities && (
          <Surface data-testid="contact-activities" level="level1" radius="lg" sx={{ p: 1.5 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <TeamOutlined style={{ fontSize: theme.iconSizes.sm, color: aq.text.muted }} />
              <Typography variant="body2" color="text.primary">
                Involved in{" "}
                <Box component="span" sx={{ fontWeight: "bold" }}>
                  {dcEntry.activity_count}
                </Box>{" "}
                activit{dcEntry.activity_count === 1 ? "y" : "ies"} in this deal
              </Typography>
            </Stack>
          </Surface>
        )}

        {/* Decision role — read from DC people, absent when unknown */}
        {showRole && (
          <>
            <Rule />
            <Box data-testid="contact-role">
              <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
                Role in the decision
              </Typography>
              <Typography variant="body2" color="text.primary" sx={{ fontWeight: "bold" }}>
                {roleLabel}
                {influenceLabel && (
                  <Box component="span" sx={{ color: aq.text.muted, fontWeight: "regular" }}>
                    {" · "}
                    {influenceLabel}
                  </Box>
                )}
              </Typography>
            </Box>
          </>
        )}

        {/* Body actions — present but inert */}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ pt: 0.5 }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<EditOutlined />}
            onClick={() => {
              // wired in CT-3 (edit contact drawer)
            }}
          >
            Edit
          </Button>
          <Box
            component="span"
            data-testid="contact-signals-link"
            role="button"
            tabIndex={0}
            onClick={() => {
              // future: browse this contact's / department's signals in place
            }}
            sx={{
              color: aq.accent,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 0.5,
              "&:hover": { textDecoration: "underline" },
            }}
          >
            <RadarChartOutlined style={{ fontSize: theme.iconSizes.sm }} />
            See signals
          </Box>
        </Stack>
      </Stack>
    </DrawerContentLayout>
  );
}

ContactDrawerContent.propTypes = {
  /** UUID of the contact whose durable fiche is shown. */
  contactId: PropTypes.string.isRequired,
  /** The activity the fiche was opened from — supplies decision_cycle. */
  activity: PropTypes.object,
};
