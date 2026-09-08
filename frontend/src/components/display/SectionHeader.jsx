// frontend/src/components/display/SectionHeader.jsx
//
// UI-3 — the shared numbered section header (contract rule 2): an optional
// index BADGE (info palette role) + a TITLE, with an optional SUBTITLE below.
// The subtitle renders only when passed — callers add it only where the
// contract allows (edit / complex signals). Without an `index`, no badge is
// shown (just the title).
//
// Consolidates the byte-identical inline copies that lived in
// EditObjectiveContent and SignalDetailContent (and mirrored in the wizard
// forms). Theme tokens only; the badge's fixed 18px square + 0.65rem label are
// the established values, kept verbatim.

import PropTypes from "prop-types";

// MUI
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function SectionHeader({ index, title, subtitle, sx }) {
  return (
    <Stack spacing={0.25} sx={sx}>
      <Stack direction="row" spacing={1} alignItems="center">
        {/* Numbered badge — info palette role (PO decision). No hardcoded colour. */}
        {index != null && (
          <Chip
            label={index}
            size="small"
            color="info"
            sx={{
              height: 18,
              width: 18,
              fontSize: "0.65rem",
              fontWeight: 700,
              "& .MuiChip-label": { px: 0 },
            }}
          />
        )}
        <Typography variant="body2" fontWeight={600}>
          {title}
        </Typography>
      </Stack>
      {subtitle && (
        <Typography variant="caption" color="text.secondary" sx={{ pl: 3.25 }}>
          {subtitle}
        </Typography>
      )}
    </Stack>
  );
}

SectionHeader.propTypes = {
  /** Badge number (optional — absent → no badge, just the title). */
  index: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  /** Section title. */
  title: PropTypes.node.isRequired,
  /** Optional subtitle (rendered only when provided). */
  subtitle: PropTypes.node,
  /** Extra sx merged onto the outer Stack (e.g. the detail view's mb). */
  sx: PropTypes.object,
};
