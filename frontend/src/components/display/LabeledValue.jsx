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

export default function LabeledValue({ label, value, placeholder, children }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  const content = children ?? value;
  const isEmpty =
    content === null || content === undefined || content === "";
  if (isEmpty && !placeholder) return null;

  return (
    <Box>
      <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
        {label}
      </Typography>
      {isEmpty ? (
        <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
          {placeholder}
        </Typography>
      ) : typeof content === "string" ? (
        <Typography variant="body2" color="text.primary" sx={{ whiteSpace: "pre-line" }}>
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
  /** Non-string value node (rendered as-is), takes precedence over `value`. */
  children: PropTypes.node,
};
