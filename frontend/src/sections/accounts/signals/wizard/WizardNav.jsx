// frontend/src/sections/accounts/signals/wizard/WizardNav.jsx
/**
 * WizardNav — horizontal navigation tabs for the WizardSignalAdd drawer.
 *
 * Displays one tab per signal type: People · Pain · Objective · Tech Stack.
 * Each tab shows a badge with the count of staged (VALIDATED + REJECTED) signals
 * for that section so the user can see at a glance what has been captured.
 *
 * Fully controlled — active section and staged counts come from the parent.
 * No local state.
 */

"use client";

import PropTypes from "prop-types";

// material-ui
import Badge from "@mui/material/Badge";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";

// ==============================|| SECTION CONFIG ||============================== //

/**
 * Ordered section definitions.
 * value must match the signalType keys used in WizardSignalAdd staged state.
 */
const SECTIONS = [
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "people", label: "People" },
  { value: "tech-stack", label: "Tech Stack" },
];

// ==============================|| WIZARD NAV ||============================== //

/**
 * WizardNav
 *
 * @param {string}  activeSection  - Currently active section value
 * @param {Function} onChange      - (sectionValue: string) => void
 * @param {Object}  stagedCounts   - { people: number, pain: number, objective: number, 'tech-stack': number }
 */
export default function WizardNav({ activeSection, onChange, stagedCounts }) {
  const handleChange = (_e, newValue) => {
    onChange(newValue);
  };

  return (
    <Tabs
      value={activeSection}
      onChange={handleChange}
      variant="fullWidth"
      aria-label="Signal wizard sections"
      sx={{
        borderBottom: "1px solid",
        borderColor: "divider",
        minHeight: 44,
        "& .MuiTab-root": {
          minHeight: 44,
          textTransform: "none",
          fontSize: "0.8rem",
          fontWeight: 500,
        },
      }}
    >
      {SECTIONS.map((section) => {
        const count = stagedCounts?.[section.value] ?? 0;

        return (
          <Tab
            key={section.value}
            value={section.value}
            aria-label={`${section.label} signals`}
            label={
              <Badge
                badgeContent={count}
                color="primary"
                max={99}
                sx={{
                  "& .MuiBadge-badge": {
                    fontSize: "0.6rem",
                    height: 16,
                    minWidth: 16,
                    top: -2,
                    right: -6,
                  },
                }}
              >
                {section.label}
              </Badge>
            }
          />
        );
      })}
    </Tabs>
  );
}

// ==============================|| PROP TYPES ||============================== //

WizardNav.propTypes = {
  /** Currently active section */
  activeSection: PropTypes.oneOf(["people", "pain", "objective", "tech-stack"])
    .isRequired,

  /** Called when the user clicks a tab */
  onChange: PropTypes.func.isRequired,

  /** Count of staged signals per section (VALIDATED + REJECTED combined) */
  stagedCounts: PropTypes.shape({
    people: PropTypes.number,
    pain: PropTypes.number,
    objective: PropTypes.number,
    "tech-stack": PropTypes.number,
  }),
};
