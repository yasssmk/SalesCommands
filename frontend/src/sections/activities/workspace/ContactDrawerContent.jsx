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
// Built on DrawerContentLayout in read mode with only onEdit → the shared
// bottom action bar shows a single Edit button (no Save/Cancel/Validate/Reject),
// like every other drawer (P-CONTACT-EDIT). "See signals" stays a body link
// (inert for now).
//
// Layout — the numbered sections of the edit drawer (EditContactContent; lot 3
// / 13a, TD-239, PO « ce design pour TOUS les drawers »): §1 Identity (avatar +
// name + job · dept) — §2 Contact (email / phone / linkedin, placeholders) —
// §3 Role in the decision (the role, placeholder when unknown, then the
// "Involved in N activities" encart inside a DC) — then "See signals". Theme
// tokens only, no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import MailOutlined from "@ant-design/icons/MailOutlined";
import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import LinkedinOutlined from "@ant-design/icons/LinkedinOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import { SIGNAL_ICON } from "utils/signalTypes";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { useGetContact } from "api/businessData/contacts";
import { useGetDCPeople } from "api/accounts/decisionCycles";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SectionHeader from "components/display/SectionHeader";
import Surface from "components/display/Surface";
import CoordinateRow from "components/display/CoordinateRow";
import EditContactContent from "sections/activities/workspace/EditContactContent";
import PersonSignalsContent, { personSignalsTitle } from "sections/activities/workspace/PersonSignalsContent";

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

// ==============================|| CONTACT DRAWER CONTENT ||============================== //

export default function ContactDrawerContent({ contactId, activity, stakeholder }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const { openDrawer } = useWorkspaceDrawer();

  // Hooks are always called (no conditional hooks); the DC people fetch is a
  // no-op when the activity carries no decision_cycle (campaign activity).
  // 8g-6: a STAKEHOLDER fiche reads its data from the stakeholder itself —
  // both fetches are no-ops then (null keys).
  const { contact: fetchedContact, contactLoading, contactError } = useGetContact(
    stakeholder ? null : contactId,
  );
  const cycleId = activity?.decision_cycle || null;
  const { people } = useGetDCPeople(stakeholder ? null : cycleId);
  // A non-converted stakeholder as the fiche's person: its name (or its
  // department, a department-only stakeholder), no coordinates.
  const contact = stakeholder
    ? {
        full_name: stakeholder.display_name || stakeholder.department?.name || "",
        department_name:
          stakeholder.display_name && stakeholder.department ? stakeholder.department.name : null,
      }
    : fetchedContact;

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
  const inDC = Boolean(cycleId) && !stakeholder;

  // ---- loading / error (no crash, discreet) ----
  if (!stakeholder && contactLoading) {
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

  if (!stakeholder && (contactError || !contact)) {
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
  // A stakeholder carries its own (read on its current signal, server-side).
  const roleLabel = stakeholder
    ? stakeholder.role_display || null
    : qualifiedEntry
      ? qualifiedEntry.role_display || qualifiedEntry.role
      : null;
  const influenceLabel = stakeholder
    ? stakeholder.influence_display || null
    : qualifiedEntry
      ? qualifiedEntry.influence_display || qualifiedEntry.influence
      : null;

  // Deal activity count: whichever entry carries the contact (qualified OR
  // unqualified), else 0. The encart shows for any contact inside a DC.
  const activityCount =
    qualifiedEntry?.activity_count ?? unqualifiedEntry?.activity_count ?? 0;

  // P-CONTACT-EDIT — Edit now lives in the shared bottom action bar (like every
  // other drawer) instead of an inline ✎ pencil; the action is unchanged.
  const handleEdit = () =>
    openDrawer(<EditContactContent contactId={contactId} activity={activity} />, {
      title: "Edit contact",
    });

  // 8g-6 — « See signals »: the signals from conversations with this person
  // (PersonSignalsContent, mounted — so requested — only now); its Back
  // re-opens this fiche.
  const personName = fullName(contact);
  const reopenFiche = () =>
    openDrawer(
      <ContactDrawerContent contactId={contactId} activity={activity} stakeholder={stakeholder} />,
      { title: stakeholder ? "Stakeholder" : "Contact" },
    );
  const handleSeeSignals = () =>
    openDrawer(
      <PersonSignalsContent
        accountId={activity?.account}
        contactId={stakeholder ? undefined : contactId}
        stakeholderId={stakeholder?.id}
        personName={personName}
        currentActivityId={activity?.id}
        onBack={reopenFiche}
      />,
      { title: personSignalsTitle(personName) },
    );

  return (
    // A stakeholder has no edit (no bar); a contact's Edit is in the bar.
    <DrawerContentLayout readActions={stakeholder ? undefined : { onEdit: handleEdit }}>
      <Stack spacing={2}>
        {/* ---- SECTION 1 — Identity: avatar | name block (grows). Edit moved to
            the bottom bar. Numbered sections = the edit drawer's
            (EditContactContent — lot 3 / 13a, TD-239). ---- */}
        <SectionHeader index={1} title="Identity" subtitle="Who the contact is." />
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
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Contact: the 3 coordinate lines are ALWAYS shown,
            two columns, with a "No …" placeholder when a channel is empty. ---- */}
        <SectionHeader index={2} title="Contact" subtitle="How to reach them." />
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


        <Divider />

        {/* ---- SECTION 3 — Role in the decision: ALWAYS present; a placeholder
            invites qualifying the contact when no role is known yet. Then the
            deal involvement (inside a DC). ---- */}
        <SectionHeader index={3} title="Role in the decision" subtitle="Their role in this decision cycle." />
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

        {/* Bottom action — « See signals » (8g-6). */}
        <Box
          component="span"
          data-testid="contact-signals-link"
          role="button"
          tabIndex={0}
          onClick={handleSeeSignals}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              handleSeeSignals();
            }
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
          <SIGNAL_ICON style={{ fontSize: theme.iconSizes.sm }} />
          See signals
        </Box>
      </Stack>
    </DrawerContentLayout>
  );
}

ContactDrawerContent.propTypes = {
  /** UUID of the contact whose durable fiche is shown. */
  contactId: PropTypes.string,
  /** The activity the fiche was opened from — supplies decision_cycle. */
  activity: PropTypes.object,
  /** 8g-6: a NON-converted stakeholder (activity.stakeholders_detail) — the
      fiche shows it instead of fetching a contact: same sections, its name
      (or department), its role, « See signals »; no coordinates, no Edit. */
  stakeholder: PropTypes.shape({
    id: PropTypes.string.isRequired,
    display_name: PropTypes.string,
    department: PropTypes.shape({ name: PropTypes.string }),
    role_display: PropTypes.string,
    influence_display: PropTypes.string,
  }),
};
