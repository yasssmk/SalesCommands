// frontend/src/components/display/CoordinateRow.jsx
//
// One coordinate ROW, two columns: (icon + label) on the left, value on the
// right. The row is ALWAYS rendered — an empty channel shows a discreet
// placeholder ("No email"…) so the user sees what is missing (the fiches'
// "always shown" principle). `href` makes a present value an accent link
// (email / linkedin); otherwise it is plain text (phone). Shared by the Contact
// and User fiches. Theme tokens only, no hardcoded hex/px.

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function CoordinateRow({ icon: Icon, label, value, href, ariaLabel, placeholder }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const hasValue = Boolean(value);

  let valueNode;
  if (!hasValue) {
    valueNode = (
      <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
        {placeholder}
      </Typography>
    );
  } else if (href) {
    valueNode = (
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
    );
  } else {
    valueNode = (
      <Typography variant="body2" color="text.primary" sx={{ wordBreak: "break-word" }}>
        {value}
      </Typography>
    );
  }

  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "minmax(0, auto) minmax(0, 1fr)",
        alignItems: "center",
        columnGap: 2,
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center">
        <Box sx={{ flexShrink: 0, display: "flex" }}>
          <Icon style={{ fontSize: theme.iconSizes.sm, color: aq.text.muted }} />
        </Box>
        <Typography variant="caption" sx={{ color: aq.text.muted }}>
          {label}
        </Typography>
      </Stack>
      <Box sx={{ textAlign: "right", minWidth: 0 }}>{valueNode}</Box>
    </Box>
  );
}

CoordinateRow.propTypes = {
  /** Ant-design icon component for the channel. */
  icon: PropTypes.elementType.isRequired,
  /** Left-column label (e.g. "Email"). */
  label: PropTypes.string.isRequired,
  /** The value; when empty the placeholder is shown instead. */
  value: PropTypes.string,
  /** When set (and value present), render the value as an accent link. */
  href: PropTypes.string,
  ariaLabel: PropTypes.string,
  /** Muted italic text shown when the value is empty (e.g. "No email"). */
  placeholder: PropTypes.string.isRequired,
};
