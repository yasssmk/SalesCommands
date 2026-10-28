// frontend/src/sections/activities/nextSteps/CampaignConversionCta.jsx
//
// Sprint Next steps 5.12 B — the campaign → Decision Cycle conversion block of
// the Next steps band (« Successful outcome — ready to convert » + Start
// Decision Cycle), moved unchanged from the former "Next planned step"
// sub-block (UpcomingActivitiesSection) to the top of the band. When it
// applies: showsCampaignConversion (utils/nextStepsBand) — the caller renders
// it only then.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import TrophyOutlined from "@ant-design/icons/TrophyOutlined";
import RocketOutlined from "@ant-design/icons/RocketOutlined";

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
        <Button
          variant="contained"
          color="success"
          size="small"
          startIcon={<RocketOutlined />}
          onClick={onStartCycle}
          sx={{ alignSelf: "flex-start" }}
        >
          Start Decision Cycle
        </Button>
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

CampaignConversionCta.propTypes = {
  onStartCycle: PropTypes.func.isRequired,
};
