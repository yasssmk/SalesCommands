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
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
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
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { useGetContact } from "api/businessData/contacts";
import { useGetDCPeople } from "api/accounts/decisionCycles";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import Surface from "components/display/Surface";
import CoordinateRow from "components/display/CoordinateRow";
import EditContactContent from "sections/activities/workspace/EditContactContent";

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

// ==============================|| CONTACT DRAWER CONTENT ||============================== //

export default function ContactDrawerContent({ contactId, activity }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const { openDrawer } = useWorkspaceDrawer();

  // Hooks are always called (no conditional hooks); the DC people fetch is a
  // no-op when the activity carries no decision_cycle (campaign activity).
  const { contact, contactLoading, contactError } = useGetContact(contactId);
  const cycleId = activity?.decision_cycle || null;
  const { people } = useGetDCPeople(cycleId);

  // The contact in DC people. The role lives on the QUALIFIED entry
  // (target_contact); activity_count lives on BOTH the qualified and the
  // unqualified entry (contact) — a contact with a role and one without both
  // have a deal activity count. Look the contact up in both lists.
  const qualified = people?.qualified || [];
  const unqualified = people?.unqualified || [];
  const qualifiedEntry =
    qualified.find((q) => q?.target_contact?.id === contactId) || null;
  const unqualifiedEntry =
    unqualified.find((u) => u?.contact?.id === contactId) || null;
  const inDC = Boolean(cycleId);

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

  // Role comes from the qualified entry; may be absent (unqualified / no DC).
  const roleLabel = qualifiedEntry
    ? qualifiedEntry.role_display || qualifiedEntry.role
    : null;
  const influenceLabel = qualifiedEntry
    ? qualifiedEntry.influence_display || qualifiedEntry.influence
    : null;

  // Deal activity count: whichever entry carries the contact (qualified OR
  // unqualified), else 0. The encart shows for any contact inside a DC.
  const activityCount =
    qualifiedEntry?.activity_count ?? unqualifiedEntry?.activity_count ?? 0;

  return (
    <DrawerContentLayout>
      <Stack spacing={2}>
        {/* Identity — avatar | name block (grows) | Edit ✎ (far right).
            The pencil is a direct child of this flex row and the middle block
            grows, so the pencil is pushed to the far right. */}
        <Stack direction="row" spacing={2} alignItems="center" data-testid="contact-identity-row">
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
          <Box sx={{ minWidth: 0, flexGrow: 1 }}>
            <Typography variant="subtitle1" color="text.primary" sx={{ fontWeight: "bold", minWidth: 0 }}>
              {fullName(contact)}
            </Typography>
            {jobDept && (
              <Typography variant="body2" sx={{ color: aq.text.muted }}>
                {jobDept}
              </Typography>
            )}
          </Box>
          {/* Edit ✎ — inert for now (opens the edit contact drawer in CT-3). */}
          <IconButton
            size="small"
            data-testid="contact-edit"
            aria-label="Edit contact"
            onClick={() =>
              openDrawer(<EditContactContent contactId={contactId} />, { title: "Edit contact" })
            }
            sx={{ color: aq.text.muted, flexShrink: 0, alignSelf: "flex-start" }}
          >
            <EditOutlined style={{ fontSize: theme.iconSizes.sm }} />
          </IconButton>
        </Stack>

        <Rule />

        {/* Coordinates — the 3 lines are ALWAYS shown, two columns, with a
            "No …" placeholder when a channel is empty. */}
        <Stack spacing={1}>
          <CoordinateRow
            icon={MailOutlined}
            label="Email"
            value={contact.email}
            href={contact.email ? `mailto:${contact.email}` : undefined}
            ariaLabel={contact.email}
            placeholder="No email"
          />
          <CoordinateRow
            icon={PhoneOutlined}
            label="Phone"
            value={contact.phone_number}
            placeholder="No phone"
          />
          <CoordinateRow
            icon={LinkedinOutlined}
            label="LinkedIn"
            value={contact.linkedin}
            href={contact.linkedin || undefined}
            ariaLabel="LinkedIn profile"
            placeholder="No LinkedIn"
          />
        </Stack>

        {/* Involved in N activities — shown for any contact inside a DC (even
            0). Absent outside a DC (campaign activity → no deal, no count). */}
        {inDC && (
          <Surface data-testid="contact-activities" level="level1" radius="lg" sx={{ p: 1.5 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <TeamOutlined style={{ fontSize: theme.iconSizes.sm, color: aq.text.muted }} />
              <Typography variant="body2" color="text.primary">
                Involved in{" "}
                <Box component="span" sx={{ fontWeight: "bold" }}>
                  {activityCount}
                </Box>{" "}
                activit{activityCount === 1 ? "y" : "ies"} in this deal
              </Typography>
            </Stack>
          </Surface>
        )}

        {/* Decision role — ALWAYS present (rule + block); a placeholder invites
            qualifying the contact when no role is known yet. */}
        <Rule />
        <Box data-testid="contact-role">
          <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
            Role in the decision
          </Typography>
          {roleLabel ? (
            <Typography variant="body2" color="text.primary" sx={{ fontWeight: "bold" }}>
              {roleLabel}
              {influenceLabel && (
                <Box component="span" sx={{ color: aq.text.muted, fontWeight: "regular" }}>
                  {" · "}
                  {influenceLabel}
                </Box>
              )}
            </Typography>
          ) : (
            <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
              No role defined
            </Typography>
          )}
        </Box>

        {/* Bottom action — the only one in the body, inert for now. */}
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
            alignSelf: "flex-start",
            "&:hover": { textDecoration: "underline" },
          }}
        >
          <RadarChartOutlined style={{ fontSize: theme.iconSizes.sm }} />
          See signals
        </Box>
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
