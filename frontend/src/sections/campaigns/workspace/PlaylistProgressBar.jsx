// frontend/src/sections/campaigns/workspace/PlaylistProgressBar.jsx
/**
 * Playlist Progress Bar — Campaign activity completion progress.
 *
 * Displays: remaining count, completed today count, total progress bar with percentage.
 * Pure presentational component — no data fetching.
 *
 * Pattern: LinearProgress usage from CampaignAccountsTab progress cells.
 */

"use client";

import PropTypes from "prop-types";

// material-ui
import { useTheme, alpha } from "@mui/material/styles";
import Box from "@mui/material/Box";
import LinearProgress from "@mui/material/LinearProgress";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ==============================|| PLAYLIST PROGRESS BAR ||============================== //

export default function PlaylistProgressBar({
  total,
  completed,
  completedToday,
  loading,
}) {
  const theme = useTheme();

  // ==============================|| LOADING STATE ||============================== //

  if (loading) {
    return (
      <Box
        sx={{
          p: 2,
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1.5,
        }}
      >
        <Skeleton variant="text" width={200} height={20} />
        <Skeleton
          variant="rectangular"
          height={8}
          sx={{ mt: 1, borderRadius: 1 }}
        />
        <Skeleton variant="text" width={100} height={16} sx={{ mt: 0.5 }} />
      </Box>
    );
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const safeTotal = total || 0;
  const safeCompleted = completed || 0;
  const remaining = Math.max(0, safeTotal - safeCompleted);
  const percentage =
    safeTotal > 0 ? Math.round((safeCompleted / safeTotal) * 100) : 0;
  const isComplete = safeTotal > 0 && safeCompleted >= safeTotal;

  // Progress bar color
  const progressColor = isComplete ? "success" : "primary";

  // ==============================|| RENDER ||============================== //

  return (
    <Box
      sx={{
        p: 2,
        border: "1px solid",
        borderColor: isComplete ? theme.palette.success.light : "divider",
        borderRadius: 1.5,
        bgcolor: isComplete
          ? alpha(theme.palette.success.main, 0.04)
          : "background.paper",
      }}
    >
      {/* Row 1: Stats */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 1 }}
      >
        <Typography variant="body2" color="text.secondary">
          {remaining} remaining
          {completedToday > 0 && (
            <Typography
              component="span"
              variant="body2"
              color="success.main"
              fontWeight={600}
            >
              {" · "}
              {completedToday} completed today
            </Typography>
          )}
        </Typography>
        <Typography
          variant="body2"
          fontWeight={600}
          color={isComplete ? "success.main" : "text.primary"}
        >
          {safeCompleted}/{safeTotal} ({percentage}%)
        </Typography>
      </Stack>

      {/* Row 2: Progress bar */}
      <LinearProgress
        variant="determinate"
        value={percentage}
        color={progressColor}
        sx={{
          height: 8,
          borderRadius: 1,
          bgcolor: theme.palette.grey[200],
          "& .MuiLinearProgress-bar": {
            borderRadius: 1,
          },
        }}
      />
    </Box>
  );
}

PlaylistProgressBar.propTypes = {
  /** Total number of activities in the campaign */
  total: PropTypes.number,
  /** Number of completed activities */
  completed: PropTypes.number,
  /** Number of activities completed in today's session */
  completedToday: PropTypes.number,
  /** Loading state */
  loading: PropTypes.bool,
};
