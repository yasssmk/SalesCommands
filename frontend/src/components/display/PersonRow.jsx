// frontend/src/components/display/PersonRow.jsx
//
// A read-only person line for stacked people lists (activity owner, invited
// users, external contacts). One row per person: a primary name with an optional
// inline muted suffix (e.g. "owner", a department), an optional muted secondary
// line (e.g. email) and an optional subtle tertiary line (e.g. coordinates).
// Themed via aphoriQ; no avatar and no click/remove chrome (read-only). Consumes
// only theme tokens (no hex/px).

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function PersonRow({ name, suffix, secondary, tertiary }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  if (!name && !suffix && !secondary && !tertiary) return null;

  return (
    <Stack spacing={0.25} sx={{ py: 0.5 }}>
      {(name || suffix) && (
        <Typography variant="body2" color="text.primary">
          {name}
          {suffix && (
            <Box component="span" sx={{ color: aq.text.muted }}>
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
  secondary: PropTypes.node,
  tertiary: PropTypes.node,
};
