// frontend/src/components/display/PersonRow.jsx
//
// A read-only person line for stacked people lists (activity owner, invited
// users, external contacts). One row: a bold name with an optional inline muted
// suffix (e.g. "owner", a department), plus optional muted/subtle extra lines.
// `interactive` makes the NAME look clickable (pointer + themed hover) WITHOUT
// any handler — the actual action is wired by the caller in a later sprint.
// Themed via aphoriQ; no avatar, no click/remove chrome. No hardcoded hex/px.

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function PersonRow({ name, suffix, interactive = false, secondary, tertiary }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  if (!name && !suffix && !secondary && !tertiary) return null;

  const interactiveSx = interactive
    ? { cursor: "pointer", "&:hover": { color: aq.accent, textDecoration: "underline" } }
    : undefined;

  return (
    <Stack spacing={0.25} sx={{ py: 0.5 }}>
      {(name || suffix) && (
        <Typography variant="body2" color="text.primary" sx={{ fontWeight: "bold" }}>
          <Box component="span" sx={interactiveSx}>
            {name}
          </Box>
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
    </Stack>
  );
}

PersonRow.propTypes = {
  name: PropTypes.node,
  /** Inline muted suffix after the name (e.g. "owner", a department). */
  suffix: PropTypes.node,
  /** Make the name look clickable (pointer + hover). No handler is attached. */
  interactive: PropTypes.bool,
  secondary: PropTypes.node,
  tertiary: PropTypes.node,
};
