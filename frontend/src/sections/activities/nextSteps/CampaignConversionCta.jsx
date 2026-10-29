// frontend/src/sections/activities/nextSteps/CampaignConversionCta.jsx
//
// Sprint Next steps 5.12 B — the campaign → Decision Cycle conversion block of
// the Next steps band (« Successful outcome — ready to convert » + Start
// Decision Cycle), moved unchanged from the former "Next planned step"
// sub-block (UpcomingActivitiesSection) to the top of the band. When it
// applies: showsCampaignConversion (utils/nextStepsBand) — the caller renders
// it only then. 5.13: its action is a ClickablePill (no MUI button in the
// band, 5.12c) — it opens the creation drawer in conversion mode.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import TrophyOutlined from "@ant-design/icons/TrophyOutlined";

// Project imports
import ClickablePill from "components/chips/ClickablePill";

// ==============================|| CAMPAIGN CONVERSION CTA ||============================== //

export default function CampaignConversionCta({ onStartCycle }) {
  const theme = useTheme();

  return (
    <Box
      data-testid="campaign-conversion"
      sx={{
        p: 2,
        borderRadius: 1,
        bgcolor: theme.palette.success.lighter,
        border: "1px solid",
        borderColor: theme.palette.success.light,
      }}
    >
      <Stack spacing={1}>
        <Stack direction="row" spacing={1} alignItems="center">
          <TrophyOutlined
            style={{ fontSize: 20, color: theme.palette.success.main }}
          />
          <Typography variant="subtitle2" color="success.dark">
            Successful outcome — ready to convert
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary">
          This prospect responded positively. Start a Decision Cycle to move
          them into your pipeline.
        </Typography>
        <Box>
          <ClickablePill label="Start Decision Cycle" active onClick={onStartCycle} />
        </Box>
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

CampaignConversionCta.propTypes = {
  onStartCycle: PropTypes.func.isRequired,
};
