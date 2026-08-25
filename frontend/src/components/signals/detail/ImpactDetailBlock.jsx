// frontend/src/components/signals/detail/ImpactDetailBlock.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Chip from "@mui/material/Chip";

// Shared primitives
import DrawerSection from "components/display/DrawerSection";
import DrawerFieldRow from "components/display/DrawerFieldRow";

/**
 * ImpactDetailBlock — the single, shared rendering of an ImpactSignal's
 * type-specific fields (impact_type, metric_text, human_impact).
 *
 * Reads the pre-rendered *_display fields off the signal payload so it is
 * identical in the drawer and the rich card (both receive them from the
 * list serializer). Cross-type fields (scope, canonical axes, status) are
 * NOT rendered here — they belong to the shell/header.
 */
export default function ImpactDetailBlock({ signal }) {
  const impactType = signal.impact_type_display;
  const metric = signal.metric_text?.trim();
  const humanImpact = signal.human_impact_display;

  if (!impactType && !metric && !humanImpact) return null;

  return (
    <DrawerSection title="IMPACT EVIDENCE">
      {impactType && (
        <DrawerFieldRow label="Impact type">
          <Chip
            label={impactType}
            size="small"
            color="secondary"
            variant="outlined"
            sx={{ height: 20, fontSize: "0.7rem" }}
          />
        </DrawerFieldRow>
      )}
      <DrawerFieldRow label="Metric" value={metric} />
      {humanImpact && (
        <DrawerFieldRow label="Human impact">
          <Chip
            label={humanImpact}
            size="small"
            color="error"
            variant="outlined"
            sx={{ height: 20, fontSize: "0.7rem" }}
          />
        </DrawerFieldRow>
      )}
    </DrawerSection>
  );
}

ImpactDetailBlock.propTypes = {
  signal: PropTypes.shape({
    impact_type_display: PropTypes.string,
    metric_text: PropTypes.string,
    human_impact_display: PropTypes.string,
  }).isRequired,
};
