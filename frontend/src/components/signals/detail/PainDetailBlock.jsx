// frontend/src/components/signals/detail/PainDetailBlock.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Chip from "@mui/material/Chip";

// Shared primitives
import DrawerSection from "components/display/DrawerSection";
import DrawerFieldRow from "components/display/DrawerFieldRow";

/**
 * PainDetailBlock — shared rendering of a PainSignal's only type-specific
 * field, the free-text related tool mention (related_techstack_mention).
 * Cross-type fields (canonical axes, scope) live in the shell/header, and
 * the manual pain→impact section is intentionally NOT here (removed in B3).
 */
export default function PainDetailBlock({ signal }) {
  const relatedTool = signal.related_techstack_mention?.trim();
  if (!relatedTool) return null;

  return (
    <DrawerSection title="RELATED TOOL">
      <DrawerFieldRow label="Mention">
        <Chip
          label={relatedTool}
          size="small"
          variant="outlined"
          sx={{ height: 20, fontSize: "0.7rem" }}
        />
      </DrawerFieldRow>
    </DrawerSection>
  );
}

PainDetailBlock.propTypes = {
  signal: PropTypes.shape({
    related_techstack_mention: PropTypes.string,
  }).isRequired,
};
