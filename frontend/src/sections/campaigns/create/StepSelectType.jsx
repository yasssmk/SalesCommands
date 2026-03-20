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
import { CAMPAIGN_TYPES } from "api/campaigns/campaigns";

// icons
import AimOutlined from "@ant-design/icons/AimOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";
import SyncOutlined from "@ant-design/icons/SyncOutlined";

// ==============================|| TYPE OPTIONS ||============================== //

const TYPE_OPTIONS = [
  {
    family: CAMPAIGN_TYPES.OUTBOUND,
    label: "Outbound",
    description:
      "Launch outbound sequences on a territory segment. Auto-generate activities for every account in the segment.",
    Icon: AimOutlined,
    colorKey: "primary",
    disabled: false,
  },
  {
    family: "RENEWAL",
    label: "Renewal",
    description:
      "Re-engage existing clients nearing contract end. Automated renewal sequences on expiring accounts.",
    Icon: SyncOutlined,
    colorKey: "success",
    disabled: true,
    comingSoon: true,
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
        {TYPE_OPTIONS.map(
          ({
            family,
            label,
            description,
            Icon,
            colorKey,
            disabled,
            comingSoon,
          }) => {
            const isSelected = selectedFamily === family;
            const color = theme.palette[colorKey];

            return (
              <Grid item xs={12} sm={6} key={family}>
                <Card
                  elevation={0}
                  onClick={() => !disabled && onSelect(family)}
                  sx={{
                    p: 3,
                    cursor: disabled ? "not-allowed" : "pointer",
                    border: "2px solid",
                    borderColor: isSelected ? color.main : "divider",
                    bgcolor: isSelected
                      ? alpha(color.main, 0.06)
                      : disabled
                        ? "action.disabledBackground"
                        : "background.paper",
                    borderRadius: 2,
                    opacity: disabled ? 0.6 : 1,
                    transition: "all 0.2s ease-in-out",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    position: "relative",
                    ...(!disabled && {
                      "&:hover": {
                        borderColor: color.main,
                        bgcolor: alpha(color.main, 0.04),
                        transform: "translateY(-2px)",
                        boxShadow: `0 4px 16px ${alpha(color.main, 0.15)}`,
                      },
                      "&:active": {
                        transform: "translateY(0)",
                      },
                    }),
                  }}
                >
                  {/* Coming soon badge */}
                  {comingSoon && (
                    <Box
                      sx={{
                        position: "absolute",
                        top: 12,
                        right: 12,
                        px: 1,
                        py: 0.25,
                        borderRadius: 1,
                        bgcolor: "action.selected",
                        border: "1px solid",
                        borderColor: "divider",
                      }}
                    >
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        fontWeight={600}
                      >
                        Coming soon
                      </Typography>
                    </Box>
                  )}

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
          },
        )}
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
