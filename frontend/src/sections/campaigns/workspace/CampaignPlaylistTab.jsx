// frontend/src/sections/campaigns/workspace/CampaignPlaylistTab.jsx
/**
 * Campaign Playlist Tab — Main playlist view with real API data.
 *
 * Displays: PlaylistProgressBar + list of PlaylistActivityCard.
 * Accordion pattern: only one card expanded at a time.
 *
 * Pattern: CampaignAccountsTab (tab structure, loading/empty states)
 * Data: useGetPlaylist (real API), completePlaylistActivity (real mutation)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";

// material-ui
import Box from "@mui/material/Box";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import PlaylistProgressBar from "./PlaylistProgressBar";
import PlaylistActivityCard from "components/cards/PlaylistActivityCard";

// api
import {
  useGetPlaylist,
  completePlaylistActivity,
} from "api/campaigns/campaigns";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| LOADING SKELETON ||============================== //

function PlaylistSkeleton() {
  return (
    <Stack spacing={1.5}>
      {[1, 2, 3, 4].map((i) => (
        <Skeleton
          key={i}
          variant="rectangular"
          height={80}
          sx={{ borderRadius: 1.5 }}
        />
      ))}
    </Stack>
  );
}

// ==============================|| CAMPAIGN PLAYLIST TAB ||============================== //

export default function CampaignPlaylistTab({ campaignId, campaign }) {
  // ==============================|| STATE ||============================== //

  const [expandedCardId, setExpandedCardId] = useState(null);
  const [completingId, setCompletingId] = useState(null);
  const [completedToday, setCompletedToday] = useState(0);

  // ==============================|| DATA ||============================== //

  const {
    activities,
    totalCount,
    playlistLoading,
    playlistError,
    mutatePlaylist,
  } = useGetPlaylist(campaignId);

  // ==============================|| HANDLERS ||============================== //

  const handleExpand = useCallback((activityId) => {
    setExpandedCardId((prev) => (prev === activityId ? null : activityId));
  }, []);

  const handleComplete = useCallback(
    async (activityId, payload) => {
      setCompletingId(activityId);
      try {
        const result = await completePlaylistActivity(
          activityId,
          campaignId,
          payload,
        );

        if (result.success) {
          setCompletedToday((prev) => prev + 1);
          setExpandedCardId(null);
          displaySuccessSnackbar("Activity completed");
          mutatePlaylist();
        } else {
          displayErrorSnackbar(result.error || "Failed to complete activity");
        }
      } catch (err) {
        displayErrorSnackbar("An error occurred");
      } finally {
        setCompletingId(null);
      }
    },
    [campaignId, mutatePlaylist],
  );

  // ==============================|| DERIVED VALUES ||============================== //

  const completedCount =
    totalCount > 0 ? Math.max(0, totalCount - activities.length) : 0;

  // ==============================|| EMPTY STATE — Campaign not active ||============================== //

  if (!playlistLoading && campaign && campaign.status !== "ACTIVE") {
    return (
      <Box sx={{ py: 6, textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary">
          Campaign is not active
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Start the campaign to generate the activity playlist.
        </Typography>
      </Box>
    );
  }

  // ==============================|| LOADING STATE ||============================== //

  if (playlistLoading) {
    return (
      <Stack spacing={2}>
        <PlaylistProgressBar loading />
        <PlaylistSkeleton />
      </Stack>
    );
  }

  // ==============================|| ERROR STATE ||============================== //

  if (playlistError) {
    return (
      <Box sx={{ py: 6, textAlign: "center" }}>
        <Typography variant="h5" color="error">
          Failed to load playlist
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Please try refreshing the page.
        </Typography>
      </Box>
    );
  }

  // ==============================|| EMPTY STATE — No activities ||============================== //

  if (!activities.length && totalCount === 0) {
    return (
      <Stack spacing={2}>
        <PlaylistProgressBar
          total={0}
          completed={0}
          completedToday={completedToday}
        />
        <Box sx={{ py: 6, textAlign: "center" }}>
          <Typography variant="h5" color="text.secondary">
            No activities in playlist
          </Typography>
          <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
            All activities have been completed, or none have been generated yet.
          </Typography>
        </Box>
      </Stack>
    );
  }

  // ==============================|| RENDER ||============================== //

  return (
    <Stack spacing={2}>
      {/* Progress bar */}
      <PlaylistProgressBar
        total={totalCount}
        completed={completedCount + completedToday}
        completedToday={completedToday}
      />

      {/* Activity cards */}
      <Stack spacing={1.5}>
        {activities.map((activity) => (
          <PlaylistActivityCard
            key={activity.id}
            activity={activity}
            expanded={expandedCardId === activity.id}
            onExpand={handleExpand}
            onComplete={handleComplete}
            completing={completingId === activity.id}
          />
        ))}
      </Stack>
    </Stack>
  );
}

CampaignPlaylistTab.propTypes = {
  /** Campaign UUID */
  campaignId: PropTypes.string.isRequired,
  /** Campaign object (for status check) */
  campaign: PropTypes.object,
};
