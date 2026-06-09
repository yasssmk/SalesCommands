// frontend/src/sections/activities/nextSteps/UpcomingActivitiesSection.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";
import { useRouter } from "next/navigation";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import LinkOutlined from "@ant-design/icons/LinkOutlined";

// Project imports
import ActivityMiniCard from "components/cards/activities/ActivityMiniCard";

// ==============================|| UPCOMING ACTIVITIES SECTION ||============================== //

export default function UpcomingActivitiesSection({
  activity,
  onCreateActivity,
  isLocked,
}) {
  const router = useRouter();
  const theme = useTheme();

  const sequenceContext = activity?.sequence_context;
  const nextActivities = sequenceContext?.next_activities || [];
  const isInSequence =
    Boolean(activity?.decision_cycle) || Boolean(activity?.campaign_detail);
  const isCampaignActivity =
    Boolean(activity?.campaign_detail) && !activity?.decision_cycle;

  const sorted = useMemo(
    () =>
      [...nextActivities].sort((a, b) => {
        const dateA = a.scheduled_date || a.due_date || "";
        const dateB = b.scheduled_date || b.due_date || "";
        return dateA.localeCompare(dateB);
      }),
    [nextActivities],
  );

  const handleNavigate = (activityId) => {
    if (activityId) {
      router.push(`/activities/${activityId}`);
    }
  };

  if (!isInSequence) {
    return (
      <Box
        sx={{
          p: 3,
          borderRadius: 1,
          bgcolor: theme.palette.grey[50],
          border: "1px dashed",
          borderColor: theme.palette.grey[200],
          opacity: 0.7,
          textAlign: "center",
        }}
      >
        <LinkOutlined
          style={{
            fontSize: 32,
            color: theme.palette.grey[400],
            marginBottom: 8,
          }}
        />
        <Typography variant="body2" color="text.disabled" sx={{ mb: 0.5 }}>
          No sequence linked.
        </Typography>
        <Typography variant="caption" color="text.disabled">
          Link this activity to a Decision Cycle from the Overview tab to see
          upcoming activities.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Quick-create chips */}
      {!isLocked && !isCampaignActivity && (
        <Stack
          direction="row"
          spacing={1}
          flexWrap="wrap"
          useFlexGap
          sx={{ mb: 2 }}
        >
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => onCreateActivity("MEETING")}
          >
            Meeting
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => onCreateActivity("CALL")}
          >
            Call
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => onCreateActivity("EMAIL")}
          >
            Email
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => onCreateActivity("TASK")}
          >
            Task
          </Button>
        </Stack>
      )}

      {/* Activity list */}
      {sorted.length > 0 ? (
        <Stack spacing={1}>
          {sorted.map((act) => (
            <ActivityMiniCard
              key={act.id}
              activity={act}
              onNavigate={handleNavigate}
            />
          ))}
        </Stack>
      ) : (
        <Box
          sx={{
            p: 2,
            borderRadius: 1,
            bgcolor: theme.palette.grey[50],
            border: "1px dashed",
            borderColor: theme.palette.grey[300],
          }}
        >
          <Typography
            variant="body2"
            color="text.secondary"
            textAlign="center"
          >
            No upcoming activities in this sequence yet.
          </Typography>
        </Box>
      )}
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

UpcomingActivitiesSection.propTypes = {
  activity: PropTypes.object,
  onCreateActivity: PropTypes.func.isRequired,
  isLocked: PropTypes.bool,
};
