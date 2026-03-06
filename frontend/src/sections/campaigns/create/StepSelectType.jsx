// frontend/src/sections/campaigns/create/StepSelectType.jsx
/**
 * Campaign Create Wizard
 *
 * Two clickable cards: Outbound vs Targeted.
 * Click selects the family and auto-advances to next step.
 */

"use client";

import PropTypes from "prop-types";

// material-ui
import { alpha, useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// api
import { SEQUENCE_TYPES } from "api/campaigns/campaigns";

// icons
import AimOutlined from "@ant-design/icons/AimOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";

// ==============================|| TYPE OPTIONS ||============================== //

const TYPE_OPTIONS = [
  {
    family: SEQUENCE_TYPES.OUTBOUND,
    label: "Outbound",
    description:
      "Launch outbound sequences on a territory segment. Auto-generate activities for every account in the segment.",
    Icon: AimOutlined,
    colorKey: "primary",
  },
  {
    family: SEQUENCE_TYPES.TARGETED,
    label: "Targeted",
    description:
      "Target specific accounts, departments or contacts with a tailored reason. Ideal for follow-ups, renewals and cross-sell.",
    Icon: ThunderboltOutlined,
    colorKey: "warning",
  },
];

// ==============================|| STEP SELECT TYPE ||============================== //

export default function StepSelectType({ selectedFamily, onSelect }) {
  const theme = useTheme();

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 1 }}>
        What type of campaign?
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Choose the campaign strategy that fits your goal.
      </Typography>

      <Grid container spacing={3}>
        {TYPE_OPTIONS.map(({ family, label, description, Icon, colorKey }) => {
          const isSelected = selectedFamily === family;
          const color = theme.palette[colorKey];

          return (
            <Grid item xs={12} sm={6} key={family}>
              <Card
                elevation={0}
                onClick={() => onSelect(family)}
                sx={{
                  p: 3,
                  cursor: "pointer",
                  border: "2px solid",
                  borderColor: isSelected ? color.main : "divider",
                  bgcolor: isSelected
                    ? alpha(color.main, 0.06)
                    : "background.paper",
                  borderRadius: 2,
                  transition: "all 0.2s ease-in-out",
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  "&:hover": {
                    borderColor: color.main,
                    bgcolor: alpha(color.main, 0.04),
                    transform: "translateY(-2px)",
                    boxShadow: `0 4px 16px ${alpha(color.main, 0.15)}`,
                  },
                  "&:active": {
                    transform: "translateY(0)",
                  },
                }}
              >
                <Stack spacing={2} alignItems="center" textAlign="center">
                  {/* Icon */}
                  <Box
                    sx={{
                      width: 64,
                      height: 64,
                      borderRadius: 2,
                      bgcolor: isSelected
                        ? alpha(color.main, 0.15)
                        : alpha(color.main, 0.08),
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      transition: "all 0.2s ease-in-out",
                    }}
                  >
                    <Icon style={{ fontSize: 32, color: color.main }} />
                  </Box>

                  {/* Label */}
                  <Typography
                    variant="h4"
                    sx={{ color: isSelected ? color.dark : "text.primary" }}
                  >
                    {label}
                  </Typography>

                  {/* Description */}
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ lineHeight: 1.6 }}
                  >
                    {description}
                  </Typography>
                </Stack>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

StepSelectType.propTypes = {
  /** Currently selected family (or empty string) */
  selectedFamily: PropTypes.string,
  /** Callback when a type is selected: (family) => void */
  onSelect: PropTypes.func.isRequired,
};
