// frontend/src/components/display/LabeledValue.jsx
//
// A read-only "label above value" pair, themed via aphoriQ. The label is muted
// (theme.aphoriQ.text.muted); the value is body text in the primary colour.
// Renders nothing when there is no value and no placeholder — so empty fields
// simply drop out of a stacked layout. Consumes only theme tokens (no hex/px).

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

export default function LabeledValue({ label, value, placeholder, dense = false, strong = false, children }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  const content = children ?? value;
  const isEmpty =
    content === null || content === undefined || content === "";
  if (isEmpty && !placeholder) return null;

  return (
    <Box>
      <Typography
        variant="caption"
        sx={{ color: aq.text.muted, display: "block", mb: dense ? 0 : 0.25 }}
      >
        {label}
      </Typography>
      {isEmpty ? (
        <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
          {placeholder}
        </Typography>
      ) : typeof content === "string" ? (
        <Typography
          variant="body2"
          color="text.primary"
          // `strong` maps to the theme's bold weight token (never a literal).
          sx={{ whiteSpace: "pre-line", ...(strong && { fontWeight: "bold" }) }}
        >
          {content}
        </Typography>
      ) : (
        content
      )}
    </Box>
  );
}

LabeledValue.propTypes = {
  label: PropTypes.string.isRequired,
  /** String (or number) value; hidden when empty unless `placeholder` is set. */
  value: PropTypes.node,
  /** Muted italic text shown when the value is empty. */
  placeholder: PropTypes.string,
  /** Tighten the label→value gap for compact grids. */
  dense: PropTypes.bool,
  /** Render the value in the theme's bold weight. */
  strong: PropTypes.bool,
  /** Non-string value node (rendered as-is), takes precedence over `value`. */
  children: PropTypes.node,
};
