// frontend/src/components/display/PersonRow.jsx
//
// A read-only person line for stacked people lists (activity owner, invited
// users, external contacts). One row per person: a primary name, an optional
// muted secondary line (e.g. job title · department, or email), and an optional
// subtle tertiary line (e.g. coordinates). Themed via aphoriQ; no click/remove
// chrome (read-only). Consumes only theme tokens (no hex/px).

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function PersonRow({ name, secondary, tertiary }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  if (!name && !secondary && !tertiary) return null;

  return (
    <Stack spacing={0.25} sx={{ py: 0.5 }}>
      {name && (
        <Typography variant="body2" color="text.primary">
          {name}
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
  secondary: PropTypes.node,
  tertiary: PropTypes.node,
};
