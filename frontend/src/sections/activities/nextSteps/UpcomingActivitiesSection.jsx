// frontend/src/sections/activities/nextSteps/UpcomingActivitiesSection.jsx

"use client";

import PropTypes from "prop-types";
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
import TrophyOutlined from "@ant-design/icons/TrophyOutlined";
import RocketOutlined from "@ant-design/icons/RocketOutlined";

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

  // Part 1 of the "Next steps" band: the ONE next planned step, chosen and
  // ordered by the server (activity.next_planned_step) — no client re-sort.
  const sequenceContext = activity?.sequence_context;
  const nextPlannedStep = activity?.next_planned_step || null;
  const plannedActivity = nextPlannedStep?.activity || null;
  const bornCycle =
    nextPlannedStep?.source === "BORN_DECISION_CYCLE"
      ? nextPlannedStep.decision_cycle
      : null;
  const isInSequence =
    Boolean(activity?.decision_cycle) || Boolean(activity?.campaign_detail);
  const isCampaignActivity =
    Boolean(activity?.campaign_detail) && !activity?.decision_cycle;
  // Hidden once a Decision Cycle was born from this activity.
  const showConversionCta =
    isCampaignActivity &&
    !bornCycle &&
    (activity?.outcome === "SUCCESSFUL" ||
      activity?.outcome === "MEETING_SCHEDULED");
  const isLastInSequence =
    sequenceContext?.position != null &&
    sequenceContext?.position === sequenceContext?.total;

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
          its next planned step.
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

      {/* The decision cycle born from this activity */}
      {bornCycle && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: "block", mb: 1 }}
        >
          {`In decision cycle ${bornCycle.name}`}
        </Typography>
      )}

      {/* The next planned step */}
      {plannedActivity ? (
        <ActivityMiniCard
          activity={plannedActivity}
          onNavigate={handleNavigate}
        />
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
            {bornCycle
              ? "No activity planned in this decision cycle yet."
              : "No next step planned yet."}
          </Typography>
          {!isLocked && !bornCycle && (
            <Typography
              variant="caption"
              color="text.secondary"
              component="p"
              textAlign="center"
            >
              {isLastInSequence
                ? "This is the last activity in the sequence. Create a follow-up to continue the cycle."
                : "Create a follow-up to continue."}
            </Typography>
          )}
        </Box>
      )}

      {/* Campaign → Decision Cycle conversion CTA */}
      {showConversionCta && !isLocked && (
        <Box
          sx={{
            mt: 2,
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
              onClick={() =>
                onCreateActivity("MEETING", { convertFromCampaign: true })
              }
              sx={{ alignSelf: "flex-start" }}
            >
              Start Decision Cycle
            </Button>
          </Stack>
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
