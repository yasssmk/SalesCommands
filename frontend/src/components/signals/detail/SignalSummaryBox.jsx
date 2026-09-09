// frontend/src/components/signals/detail/SignalSummaryBox.jsx
//
// The shared "summary box" that OPENS a signal detail on the standard chassis:
// the narrative summary as the headline, a short centered separator, then the
// "This is a {axis} {noun}" recap and the canonical_key line. Extracted verbatim
// from the Objective detail's Goal box (SIG-5e) so Objective and Pain (and any
// future canonical-axes type) render this block from ONE source.
//
// Theme tokens only (surface.level1 tint + radius.md), all optional-chained so a
// theme-less mount degrades to no-tint instead of throwing.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import Typography from "@mui/material/Typography";

export default function SignalSummaryBox({
  summary,
  axisPreview,
  axisNoun,
  canonicalKey,
  boxTestId,
  summaryTestId,
  separatorTestId,
}) {
  if (!summary && !axisPreview) return null;

  return (
    <Box
      data-testid={boxTestId}
      sx={{
        my: 1,
        px: 1.5,
        py: 1.25,
        bgcolor: (theme) => theme.aphoriQ?.surface?.level1,
        borderRadius: (theme) => theme.aphoriQ?.radius?.md && `${theme.aphoriQ.radius.md}px`,
      }}
    >
      {summary && (
        <Typography
          data-testid={summaryTestId}
          variant="body1"
          fontWeight={500}
          color="text.primary"
          sx={{ whiteSpace: "pre-line" }}
        >
          {summary}
        </Typography>
      )}
      {summary && axisPreview && (
        <Divider
          data-testid={separatorTestId}
          sx={{ width: "40%", mx: "auto", my: 1.5 }}
        />
      )}
      {axisPreview && (
        <>
          <Typography variant="caption" color="text.secondary">
            This is a{" "}
            <Box component="span" sx={{ fontWeight: 600, color: "text.primary" }}>
              {axisPreview}
            </Box>{" "}
            {axisNoun}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            display="block"
            sx={{ fontFamily: "monospace", mt: 0.25 }}
          >
            canonical_key: {canonicalKey}
          </Typography>
        </>
      )}
    </Box>
  );
}

SignalSummaryBox.propTypes = {
  /** The narrative summary — the detail's headline. */
  summary: PropTypes.string,
  /** The "{what} × {dimension}" recap text (null hides the recap + separator). */
  axisPreview: PropTypes.string,
  /** The type noun closing the recap sentence ("goal" / "pain"). */
  axisNoun: PropTypes.string,
  /** The canonical_key string shown under the recap. */
  canonicalKey: PropTypes.string,
  /** Optional test id for the enclosing box (kept per-type for existing tests). */
  boxTestId: PropTypes.string,
  /** Optional test id for the summary Typography. */
  summaryTestId: PropTypes.string,
  /** Optional test id for the separator Divider. */
  separatorTestId: PropTypes.string,
};
