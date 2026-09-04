// frontend/src/components/display/PersonRow.jsx
//
// A read-only person line for stacked people lists (activity owner, invited
// users, external contacts). One row: a bold name with an optional inline muted
// suffix (e.g. "owner", a department), plus optional muted/subtle extra lines.
// `interactive` makes the NAME look clickable (pointer + themed hover); pass
// `onClick` to actually wire the action (e.g. open the contact fiche). Both are
// optional and default off — the other usages stay unchanged.
// Themed via aphoriQ; no avatar, no remove chrome. No hardcoded hex/px.

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function PersonRow({ name, suffix, interactive = false, onClick, secondary, tertiary }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  if (!name && !suffix && !secondary && !tertiary) return null;

  // A wired onClick implies the interactive affordance even if the caller did
  // not set `interactive` explicitly.
  const clickable = interactive || Boolean(onClick);
  const interactiveSx = clickable
    ? { cursor: "pointer", "&:hover": { color: aq.accent, textDecoration: "underline" } }
    : undefined;

  // Keyboard access only when actually actionable.
  const nameProps = onClick
    ? {
        onClick,
        role: "button",
        tabIndex: 0,
        onKeyDown: (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick(e);
          }
        },
      }
    : {};

  return (
    <Stack spacing={0.25} sx={{ py: 0.5 }}>
      {(name || suffix) && (
        <Typography variant="body2" color="text.primary" sx={{ fontWeight: "bold" }}>
          <Box component="span" sx={interactiveSx} {...nameProps}>
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
  /** Click handler on the name — wires the action (and implies the affordance). */
  onClick: PropTypes.func,
  secondary: PropTypes.node,
  tertiary: PropTypes.node,
};
