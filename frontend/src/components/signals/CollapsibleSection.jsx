// frontend/src/components/signals/CollapsibleSection.jsx
//
// A collapsible section built on the design-system MUI Accordion (the same
// primitive used by SignalClusterDetailDrawer's ByLevelAccordion). Open by
// default; the user collapses to reduce noise. Open/close is component state
// (MUI Accordion) — no browser storage. Collapsed content is unmounted so the
// section truly hides (and stays cheap).
//
// Two visual levels:
//   "section" — a narrative/type section header (overline, letter-spaced).
//   "domain"  — a nested domain grouping (bolder subtitle), lighter chrome.

"use client";

import PropTypes from "prop-types";

import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import DownOutlined from "@ant-design/icons/DownOutlined";

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
      disableGutters
      elevation={0}
      square
      // Unmount collapsed content so the section genuinely hides.
      TransitionProps={{ unmountOnExit: true }}
      data-testid={testId}
      sx={{
        bgcolor: "transparent",
        "&:before": { display: "none" },
        mb: isSection ? 2 : 1,
      }}
    >
      <AccordionSummary
        expandIcon={<DownOutlined style={{ fontSize: isSection ? 13 : 11 }} />}
        sx={{
          px: isSection ? 0 : 1,
          minHeight: 0,
          "& .MuiAccordionSummary-content": { my: isSection ? 0.5 : 0.25 },
        }}
      >
        <Stack direction="row" spacing={1} alignItems="baseline">
          {isSection ? (
            <Typography
              variant="overline"
              color="text.secondary"
              sx={{ letterSpacing: 1.5, lineHeight: 1.6 }}
            >
              {title}
            </Typography>
          ) : (
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              {title}
            </Typography>
          )}
          {typeof count === "number" && (
            <Typography variant="caption" color="text.disabled">
              ({count})
            </Typography>
          )}
        </Stack>
      </AccordionSummary>
      <AccordionDetails sx={{ px: isSection ? 0 : 1, pt: 0, pb: 1 }}>
        <Box sx={{ width: "100%" }}>{children}</Box>
      </AccordionDetails>
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
