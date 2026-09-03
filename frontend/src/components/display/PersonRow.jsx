// frontend/src/components/display/PersonRow.jsx
//
// A read-only person line for stacked people lists (activity owner, invited
// users, external contacts). One row: a round initials avatar (neutral, themed),
// a bold name with an optional inline muted suffix (e.g. "owner", a department),
// an optional trailing node (e.g. a chevron), and optional muted/subtle extra
// lines. Themed via aphoriQ; no click/remove chrome (read-only). No hardcoded
// hex/px — weights/colours/sizes come from the theme.

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function PersonRow({ name, suffix, avatarText, trailing, secondary, tertiary }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  if (!name && !suffix && !avatarText && !secondary && !tertiary) return null;

  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ py: 0.5 }}>
      {avatarText && (
        <Avatar
          sx={{
            width: theme.spacing(3.5),
            height: theme.spacing(3.5),
            fontSize: theme.typography.caption.fontSize,
            bgcolor: aq.surface.level3,
            color: aq.text.muted,
            flexShrink: 0,
          }}
        >
          {avatarText}
        </Avatar>
      )}

      <Box sx={{ minWidth: 0, flexGrow: 1 }}>
        {(name || suffix) && (
          <Typography variant="body2" color="text.primary" sx={{ fontWeight: "bold" }}>
            {name}
            {suffix && (
              <Box component="span" sx={{ color: aq.text.muted, fontWeight: "regular" }}>
                {" · "}
                {suffix}
              </Box>
            )}
          </Typography>
        )}
        {secondary && (
          <Typography variant="caption" sx={{ color: aq.text.muted }}>
            {secondary}
          </Typography>
        )}
        {tertiary && (
          <Typography variant="caption" sx={{ color: aq.text.subtle }}>
            {tertiary}
          </Typography>
        )}
      </Box>

      {trailing && <Box sx={{ flexShrink: 0, display: "flex" }}>{trailing}</Box>}
    </Stack>
  );
}

PersonRow.propTypes = {
  name: PropTypes.node,
  /** Inline muted suffix after the name (e.g. "owner", a department). */
  suffix: PropTypes.node,
  /** Initials for the round avatar (omit for no avatar). */
  avatarText: PropTypes.string,
  /** Trailing node at the far right (e.g. a chevron). Inert unless it handles its own events. */
  trailing: PropTypes.node,
  secondary: PropTypes.node,
  tertiary: PropTypes.node,
};
