// frontend/src/sections/activities/workspace/UserDrawerContent.jsx
//
// CT-USER — the PURE READ-ONLY fiche for an internal team member (an activity
// owner or invited user). Symmetric to ContactDrawerContent but for the User
// model (end_users.User): identity + platform Role + Team + Email, shown in the
// shared two-column CoordinateRow with "No …" placeholders when empty (the
// fiches' "always shown" principle).
//
// PURE READ — no edit pencil (user edit is admin-only elsewhere), and none of
// the deal-facing blocks a contact has: no "N activities", no DC role, no
// "See signals" (an internal member is not a deal decider). Built on
// DrawerContentLayout WITHOUT onSave/onCancel → no global action bar (CT-1);
// the title "Team member" comes from openDrawer. Theme tokens only, no hex/px.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import MailOutlined from "@ant-design/icons/MailOutlined";
import IdcardOutlined from "@ant-design/icons/IdcardOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";

// Project
import { useGetUser } from "api/admin/users";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import CoordinateRow from "components/display/CoordinateRow";

// ==============================|| HELPERS ||============================== //

function initials(user) {
  const f = (user?.first_name || "").trim();
  const l = (user?.last_name || "").trim();
  const two = `${f.charAt(0)}${l.charAt(0)}`.trim();
  if (two) return two.toUpperCase();
  const name = (user?.full_name || user?.email || "").trim();
  return name ? name.charAt(0).toUpperCase() : "?";
}

function fullName(user) {
  return (
    user?.full_name ||
    `${user?.first_name || ""} ${user?.last_name || ""}`.trim() ||
    user?.email ||
    "Team member"
  );
}

// A themed hairline rule (same form as the Contact fiche).
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

// ==============================|| USER DRAWER CONTENT ||============================== //

export default function UserDrawerContent({ userId }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  const { user, userLoading, userError } = useGetUser(userId);

  if (userLoading) {
    return (
      <DrawerContentLayout>
        <Box
          data-testid="user-loading"
          sx={{ display: "flex", justifyContent: "center", py: 4 }}
        >
          <CircularProgress size={theme.iconSizes.md} />
        </Box>
      </DrawerContentLayout>
    );
  }

  if (userError || !user) {
    return (
      <DrawerContentLayout>
        <Typography variant="body2" sx={{ color: aq.text.muted }}>
          This team member could not be loaded.
        </Typography>
      </DrawerContentLayout>
    );
  }

  return (
    <DrawerContentLayout>
      <Stack spacing={2}>
        {/* Identity — no edit pencil (read-only). */}
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
            {initials(user)}
          </Box>
          <Box sx={{ minWidth: 0, flexGrow: 1 }}>
            <Typography variant="subtitle1" color="text.primary" sx={{ fontWeight: "bold" }}>
              {fullName(user)}
            </Typography>
          </Box>
        </Stack>

        <Rule />

        {/* Platform role · team · email — always shown, two columns. */}
        <Stack spacing={1}>
          <CoordinateRow
            icon={IdcardOutlined}
            label="Role"
            value={user.role_name}
            placeholder="No role"
          />
          <CoordinateRow
            icon={TeamOutlined}
            label="Team"
            value={user.team_name}
            placeholder="No team"
          />
          <CoordinateRow
            icon={MailOutlined}
            label="Email"
            value={user.email}
            href={user.email ? `mailto:${user.email}` : undefined}
            ariaLabel={user.email}
            placeholder="No email"
          />
        </Stack>
      </Stack>
    </DrawerContentLayout>
  );
}

UserDrawerContent.propTypes = {
  /** UUID of the internal user (activity owner / invited) to show. */
  userId: PropTypes.string.isRequired,
};
