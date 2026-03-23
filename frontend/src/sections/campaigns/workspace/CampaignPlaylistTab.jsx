// frontend/src/sections/campaigns/workspace/CampaignPlaylistTab.jsx
/**
 * Campaign Playlist Tab — Main playlist view with real API data.
 *
 * Displays: PlaylistProgressBar + list of PlaylistActivityCard.
 * Accordion pattern: only one card expanded at a time.
 * Executor filter: optional dropdown to filter by a single team member.
 * Optimistic removal: completed activities are hidden immediately from the UI.
 *
 * Pattern: CampaignAccountsTab (tab structure, loading/empty states)
 * Data: useGetPlaylist (real API), completePlaylistActivity (real mutation)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import DownOutlined from "@ant-design/icons/DownOutlined";

// project imports
import PlaylistProgressBar from "./PlaylistProgressBar";
import PlaylistActivityCard from "components/cards/PlaylistActivityCard";
import CampaignOutcomeModal from "../CampaignOutcomeModal";

import {
  useGetPlaylist,
  useGetCampaignMembers,
  useGetCompletedActivities,
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

  const [completingId, setCompletingId] = useState(null);
  const [completedToday, setCompletedToday] = useState(0);
  // { open: bool, activity: object|null }
  const [outcomeModal, setOutcomeModal] = useState({
    open: false,
    activity: null,
  });
  const [executorId, setExecutorId] = useState("");

  // Track optimistically removed activity IDs
  const [removedIds, setRemovedIds] = useState(new Set());
  const [showCompleted, setShowCompleted] = useState(false);

  // ==============================|| DATA ||============================== //

  const BLOCKED_STATUSES = {
    DRAFT: {
      title: "Campaign not started",
      body: "Start the campaign to activate the activity playlist.",
    },
    PAUSED: {
      title: "Campaign paused",
      body: "Activities are on hold. Resume the campaign to continue.",
    },
    COMPLETED: {
      title: "Campaign completed",
      body: "This campaign has ended. The playlist is now read-only.",
    },
    CANCELLED: {
      title: "Campaign cancelled",
      body: "This campaign was cancelled. No activities are available.",
    },
  };

  const isBlocked = campaign && BLOCKED_STATUSES[campaign?.status];

  const {
    activities: rawActivities,
    totalCount,
    playlistLoading,
    playlistError,
    mutatePlaylist,
  } = useGetPlaylist(isBlocked ? null : campaignId, {
    executorId: executorId || undefined,
  });

  // Executors — derived from campaign object (owner + executor if set)
  const executors = useMemo(() => {
    const result = [];
    if (campaign?.owner) result.push({ ...campaign.owner, role: "OWNER" });
    if (campaign?.executor)
      result.push({ ...campaign.executor, role: "EXECUTOR" });
    return result;
  }, [campaign]);

  // Filter out optimistically removed activities
  const activities = useMemo(
    () => rawActivities.filter((a) => !removedIds.has(a.id)),
    [rawActivities, removedIds],
  );

  // ==============================|| HANDLERS ||============================== //

  const handleExecutorChange = useCallback((event) => {
    setExecutorId(event.target.value);
    setRemovedIds(new Set());
  }, []);

  // 1-click complete for EMAIL / LINKEDIN
  const handleOneClickComplete = useCallback(
    async (activityId, payload) => {
      setCompletingId(activityId);
      try {
        const result = await completePlaylistActivity(
          activityId,
          campaignId,
          payload,
        );
        if (result.success) {
          setRemovedIds((prev) => new Set([...prev, activityId]));
          setCompletedToday((prev) => prev + 1);
          mutatePlaylist();
          displaySuccessSnackbar("Activity completed");
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setCompletingId(null);
      }
    },
    [campaignId, mutatePlaylist],
  );

  // Opens outcome modal for CALL / MEETING / TASK
  const handleLogOutcome = useCallback((activity) => {
    setOutcomeModal({ open: true, activity });
  }, []);

  // Called by CampaignOutcomeModal on successful completion
  const handleOutcomeComplete = useCallback(
    (activityId) => {
      setRemovedIds((prev) => new Set([...prev, activityId]));
      setCompletedToday((prev) => prev + 1);
      mutatePlaylist();
    },
    [mutatePlaylist],
  );

  // ==============================|| DERIVED VALUES ||============================== //

  // ── Completed activities (lazy-loaded on expand) ──
  const { activities: completedActivities, completedActivitiesLoading } =
    useGetCompletedActivities(showCompleted ? campaignId : null);

  // ── Split PLANNED into Today vs Upcoming ──
  const todayStr = new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, timezone-safe

  const { todayActivities, upcomingActivities, onHoldActivities } =
    useMemo(() => {
      const today = [];
      const upcoming = [];
      const onHold = [];
      activities.forEach((a) => {
        // ON_HOLD activities go to end of Upcoming with warning style
        if (a.status === "ON_HOLD") {
          onHold.push(a);
          return;
        }
        const d = a.scheduled_date || a.due_date;
        if (!d || d <= todayStr) {
          today.push(a);
        } else {
          upcoming.push(a);
        }
      });
      return {
        todayActivities: today,
        upcomingActivities: upcoming,
        onHoldActivities: onHold,
      };
    }, [activities, todayStr]);

  const completedCount =
    totalCount > 0 ? Math.max(0, totalCount - rawActivities.length) : 0;

  // ==============================|| EMPTY STATE — Campaign not active ||============================== //

  if (!playlistLoading && campaign && BLOCKED_STATUSES[campaign.status]) {
    const { title, body } = BLOCKED_STATUSES[campaign.status];
    return (
      <Box sx={{ py: 6, textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary">
          {title}
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          {body}
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
      <CampaignOutcomeModal
        open={outcomeModal.open}
        onClose={() => setOutcomeModal({ open: false, activity: null })}
        activity={outcomeModal.activity}
        campaignId={campaignId}
        onComplete={handleOutcomeComplete}
        onUpdate={mutatePlaylist}
      />

      {/* Progress bar */}
      <PlaylistProgressBar
        total={totalCount}
        completed={completedCount + completedToday}
        completedToday={completedToday}
      />

      {/* ── Inactivity warning ── */}
      {campaign?.is_inactive && (
        <Alert severity="warning" variant="outlined">
          No activity completed in the last {30} days — this campaign may need
          attention.
        </Alert>
      )}

      {/* ── Section: To Do Today ── */}
      <Box>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
          <Typography variant="subtitle2" fontWeight={600}>
            To do today
          </Typography>
          <Chip
            label={todayActivities.length}
            size="small"
            color="primary"
            variant="filled"
          />
        </Stack>

        {todayActivities.length === 0 ? (
          <Box sx={{ py: 3, textAlign: "center" }}>
            <Typography variant="body2" color="text.secondary">
              Nothing to do today 🎉
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1.5}>
            {todayActivities.map((activity) => (
              <PlaylistActivityCard
                key={activity.id}
                activity={activity}
                onComplete={handleOneClickComplete}
                onLogOutcome={handleLogOutcome}
                completing={completingId === activity.id}
              />
            ))}
          </Stack>
        )}
      </Box>

      {/* ── Section: Upcoming (collapsible) ── */}
      {(upcomingActivities.length > 0 || onHoldActivities.length > 0) && (
        <Accordion
          disableGutters
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1.5,
            "&:before": { display: "none" },
            "&.Mui-expanded": { borderColor: "divider" },
          }}
        >
          <AccordionSummary
            expandIcon={<DownOutlined style={{ fontSize: 12 }} />}
            sx={{
              minHeight: 48,
              "& .MuiAccordionSummary-content": {
                alignItems: "center",
                gap: 1,
              },
            }}
          >
            <Typography variant="subtitle2" fontWeight={600}>
              Upcoming
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0, pb: 1.5 }}>
            <Stack spacing={1.5}>
              {upcomingActivities.map((activity) => (
                <PlaylistActivityCard
                  key={activity.id}
                  activity={activity}
                  onComplete={handleOneClickComplete}
                  onLogOutcome={handleLogOutcome}
                  completing={completingId === activity.id}
                  isGreyedOut
                />
              ))}

              {/* ON_HOLD activities — end of list, warning background */}
              {onHoldActivities.map((activity) => (
                <Box
                  key={activity.id}
                  sx={{
                    borderRadius: 1.5,
                    bgcolor: "warning.lighter",
                    border: "1px solid",
                    borderColor: "warning.light",
                  }}
                >
                  <PlaylistActivityCard activity={activity} isGreyedOut />
                </Box>
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      {/* ── Section: Completed (collapsible, lazy-load) ── */}
      <Accordion
        disableGutters
        elevation={0}
        onChange={(_e, expanded) => {
          if (expanded) setShowCompleted(true);
        }}
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1.5,
          "&:before": { display: "none" },
        }}
      >
        <AccordionSummary
          expandIcon={<DownOutlined style={{ fontSize: 12 }} />}
          sx={{
            minHeight: 48,
            "& .MuiAccordionSummary-content": { alignItems: "center", gap: 1 },
          }}
        >
          <Typography variant="subtitle2" fontWeight={600}>
            Completed
          </Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ pt: 0, pb: 1.5 }}>
          {completedActivitiesLoading ? (
            <Stack spacing={1}>
              {[1, 2].map((i) => (
                <Skeleton key={i} height={60} sx={{ borderRadius: 1 }} />
              ))}
            </Stack>
          ) : completedActivities.length === 0 ? (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ py: 2, textAlign: "center" }}
            >
              No completed activities yet
            </Typography>
          ) : (
            <Stack spacing={1.5}>
              {completedActivities
                .filter((a) => a.status === "COMPLETED")
                .map((activity) => (
                  <PlaylistActivityCard
                    key={activity.id}
                    activity={activity}
                    isGreyedOut
                  />
                ))}
            </Stack>
          )}
        </AccordionDetails>
      </Accordion>
    </Stack>
  );
}

CampaignPlaylistTab.propTypes = {
  /** Campaign UUID */
  campaignId: PropTypes.string.isRequired,
  /** Campaign object (for status check) */
  campaign: PropTypes.object,
};
