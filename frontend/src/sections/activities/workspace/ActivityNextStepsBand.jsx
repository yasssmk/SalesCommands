// frontend/src/sections/activities/workspace/ActivityNextStepsBand.jsx
//
// Sprint Next steps 5.12e (4) — the "Next steps" BAND of the Activity
// workspace: its CollapsibleStrip (title, icon, open state) + the band body
// (ActivityNextStepsTab). « + Add next step » sits on the right of the band's
// title, in the strip's `meta` slot — the mechanism of 5.8e / 5.8g (the pill
// in `meta`, its click / key stopped there so it never folds the strip; on a
// folded strip it unfolds it, the strip being controlled). The row of
// ActivityType pills it opens is shown at the TOP of the band body.
// 5.16 (PO) — the band's ONE creation pill: shown wherever the activity has
// next steps (hasSuggestedNextSteps — a DC, or a SUCCESSFUL campaign
// activity), hidden on a CANCELLED activity (the band's lock,
// isActivitySignalsLocked). Its creation converts while no DC is born
// (ActivityNextStepsTab's openCreate).

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";

// MUI
import Box from "@mui/material/Box";

// Icons
import RightCircleOutlined from "@ant-design/icons/RightCircleOutlined";

// Project imports
import CollapsibleStrip from "components/display/CollapsibleStrip";
import ClickablePill from "components/chips/ClickablePill";
import ActivityNextStepsTab from "sections/activities/workspace/ActivityNextStepsTab";
import { hasSuggestedNextSteps } from "utils/nextStepsBand";
import { isActivitySignalsLocked } from "utils/activitySignalsLock";

// ==============================|| ACTIVITY NEXT STEPS BAND ||============================== //

export default function ActivityNextStepsBand({ activity, defaultExpanded = false, ...bodyProps }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  // "+ Add next step" — the row of type pills is shown (in the body).
  const [typesOpen, setTypesOpen] = useState(false);
  const showsAddNextStep = hasSuggestedNextSteps(activity) && !isActivitySignalsLocked(activity);

  // On a folded band the pill unfolds it and shows the type row (which lives
  // in its body); on an open one it toggles the type row.
  const handleAddNextStep = useCallback(() => {
    if (!expanded) {
      setExpanded(true);
      setTypesOpen(true);
      return;
    }
    setTypesOpen((open) => !open);
  }, [expanded]);

  return (
    <CollapsibleStrip
      title="Next steps"
      icon={RightCircleOutlined}
      expanded={expanded}
      onExpandedChange={setExpanded}
      meta={
        showsAddNextStep ? (
          <Box
            component="span"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <ClickablePill label="+ Add next step" active onClick={handleAddNextStep} />
          </Box>
        ) : undefined
      }
    >
      {/* The band owns its lock (COMPLETED stays workable); its extraction is
          the Source band's (same runner, same lock: CANCELLED only, 5.12c). */}
      <ActivityNextStepsTab
        activity={activity}
        typesOpen={showsAddNextStep && typesOpen}
        onTypesOpenChange={setTypesOpen}
        {...bodyProps}
      />
    </CollapsibleStrip>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityNextStepsBand.propTypes = {
  activity: PropTypes.shape({
    status: PropTypes.string,
    decision_cycle: PropTypes.string,
  }),
  /** Whether the band starts open (the page: open once analysed). */
  defaultExpanded: PropTypes.bool,
};
