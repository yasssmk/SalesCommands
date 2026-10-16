// frontend/src/components/display/InfoNotice.jsx
//
// Information notice (soft info tone, ⓘ icon + body2 text) — EXTRACTED from the
// RunAIWizard review step (Sprint TechStack T5b) so the AI-related notices of
// the Activity surface share ONE block instead of a copy each:
//   - RunAIWizard: "Edit below to remove anything you don't want to send…";
//   - SignalsValidationList "To validate": "Transcript analysis can make
//     mistakes…".
// Same DOM as the former inline block: Stack row, spacing 1, p 1.5, radius 1,
// info.lighter background / info.dark text, InfoCircleOutlined (md = 16) with
// a 0.25 spacing top offset aligning it on the first text line. The two former
// hard-coded values (16, 2) now come from the theme tokens of the same value.
// Information, never an error: no error / red tone (UX_UI_Guidelines.md).

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import InfoCircleOutlined from "@ant-design/icons/InfoCircleOutlined";

export default function InfoNotice({ children, ...other }) {
  const theme = useTheme();
  return (
    <Stack
      direction="row"
      spacing={1}
      sx={{
        p: 1.5,
        borderRadius: 1,
        bgcolor: "info.lighter",
        color: "info.dark",
      }}
      {...other}
    >
      <InfoCircleOutlined
        style={{ fontSize: theme.iconSizes.md, marginTop: theme.spacing(0.25), flexShrink: 0 }}
      />
      <Typography variant="body2">{children}</Typography>
    </Stack>
  );
}

InfoNotice.propTypes = {
  /** The notice text. */
  children: PropTypes.node.isRequired,
};
