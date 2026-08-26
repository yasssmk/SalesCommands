// frontend/src/components/signals/CollapsibleSection.jsx
//
// A collapsible section using the PROJECT-THEMED MUI Accordion — the same
// Accordion / AccordionSummary / AccordionDetails the rest of the app uses
// (see themes/overrides/Accordion*.{js,jsx}: tinted summary background,
// secondary.light border, the RightOutlined rotating chevron, themed
// spacing). No ad-hoc chrome — the theme owns the look, so these sections
// match the app's other accordions.
//
// Open by default; the user collapses to reduce noise. Open/close is component
// state (MUI Accordion) — no browser storage. Collapsed content is unmounted.

"use client";

import PropTypes from "prop-types";

import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function CollapsibleSection({
  title,
  count,
  level = "section",
  defaultExpanded = true,
  testId,
  children,
}) {
  const isSection = level === "section";

  return (
    <Accordion
      defaultExpanded={defaultExpanded}
      // Unmount collapsed content so the section genuinely hides.
      TransitionProps={{ unmountOnExit: true }}
      data-testid={testId}
      // Small gap between stacked sections; all other chrome comes from the theme.
      sx={{ mb: isSection ? 2 : 1 }}
    >
      <AccordionSummary>
        <Stack direction="row" spacing={1} alignItems="baseline">
          <Typography
            variant={isSection ? "subtitle1" : "subtitle2"}
            sx={{ fontWeight: 600 }}
          >
            {title}
          </Typography>
          {typeof count === "number" && (
            <Typography variant="caption" color="text.secondary">
              ({count})
            </Typography>
          )}
        </Stack>
      </AccordionSummary>
      <AccordionDetails>{children}</AccordionDetails>
    </Accordion>
  );
}

CollapsibleSection.propTypes = {
  title: PropTypes.string.isRequired,
  count: PropTypes.number,
  level: PropTypes.oneOf(["section", "domain"]),
  defaultExpanded: PropTypes.bool,
  testId: PropTypes.string,
  children: PropTypes.node,
};
