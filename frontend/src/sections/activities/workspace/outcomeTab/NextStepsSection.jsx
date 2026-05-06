// frontend/src/sections/activities/workspace/outcomeTab/NextStepsSection.jsx
/**
 * NextStepsSection — Next-step planning for the Activity workspace.
 *
 * Extracted from the legacy ActivityOutcomeTab so it can be reused by
 * the new ActivityWrapUpTab without duplication. Logic identical to
 * the legacy implementation — no behavioural change.
 *
 * Renders:
 *   - Sequence next activities (decision-cycle / campaign scope)
 *   - Quick-create follow-up CTAs (decision-cycle activities only)
 *   - Campaign → Decision Cycle conversion CTA (when applicable)
 *   - Inactive disabled state when activity is not part of any sequence
 *
 * Helpers SectionCard and ActivityMiniCard are inlined here — they
 * were inline helpers in the legacy ActivityOutcomeTab and have no
 * other consumer after the Wrap-up refactor.
 */

"use client";

import PropTypes from "prop-types";
import { useRouter } from "next/navigation";

// material-ui
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import LinkOutlined from "@ant-design/icons/LinkOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import RocketOutlined from "@ant-design/icons/RocketOutlined";
import TrophyOutlined from "@ant-design/icons/TrophyOutlined";

// project imports
import {
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS,
} from "api/accounts/activities";

// ==============================|| SECTION CARD WRAPPER ||============================== //

/**
 * Internal helper — outlined card with a title row and an optional
 * trailing action slot. Inlined here because the legacy KeyTakeaways /
 * Result sections (its other former consumers) are removed by the
 * Wrap-up refactor.
 */
function SectionCard({ title, icon: Icon, children, action }) {
  const theme = useTheme();

  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{ mb: 2 }}
        >
          <Stack direction="row" spacing={1} alignItems="center">
            {Icon && (
              <Icon
                style={{ fontSize: theme.iconSizes.md, color: "#8c8c8c" }}
              />
            )}
            <Typography variant="subtitle1" fontWeight={600}>
              {title}
            </Typography>
          </Stack>
          {action}
        </Stack>
        {children}
      </CardContent>
    </Card>
  );
}

SectionCard.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.elementType,
  children: PropTypes.node,
  action: PropTypes.node,
};

// ==============================|| ACTIVITY MINI CARD ||============================== //

/**
 * Internal helper — compact card for an activity reference shown in
 * the "Upcoming in sequence" list. Click navigates to the activity
 * workspace; optional unlink action when caller passes showUnlink.
 */
function ActivityMiniCard({
  activity: activityItem,
  onNavigate,
  onUnlink,
  showUnlink = false,
}) {
  const theme = useTheme();

  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleDateString();
  };

  const displayDate = activityItem.scheduled_date || activityItem.due_date;
  const stepName = activityItem.decision_step_name;

  return (
    <Card
      variant="outlined"
      sx={{
        p: 1.5,
        cursor: "pointer",
        transition: "all 0.15s ease-in-out",
        "&:hover": {
          bgcolor: "action.hover",
          borderColor: theme.palette.primary.light,
        },
      }}
      onClick={() => onNavigate(activityItem.id)}
    >
      <Stack spacing={1}>
        {/* Row 1: Type + Title */}
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Chip
            label={
              ACTIVITY_TYPE_LABELS[activityItem.activity_type] ||
              activityItem.activity_type
            }
            size="small"
            variant="outlined"
            sx={{ minWidth: 80 }}
          />
          <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1 }}>
            {activityItem.title}
          </Typography>
          {showUnlink && (
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onUnlink?.();
              }}
              sx={{ ml: "auto" }}
            >
              <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
          )}
        </Stack>

        {/* Row 2: Meta info (step, date, status) */}
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
        >
          {stepName && (
            <Chip
              label={stepName}
              size="small"
              variant="filled"
              sx={{
                height: 20,
                fontSize: "0.7rem",
                bgcolor: theme.palette.grey[100],
                color: theme.palette.text.secondary,
              }}
            />
          )}
          {displayDate && (
            <Typography variant="caption" color="text.secondary">
              {formatDate(displayDate)}
            </Typography>
          )}
          <Chip
            label={
              activityItem.is_overdue
                ? "Overdue"
                : ACTIVITY_STATUS_LABELS[activityItem.status] ||
                  activityItem.status
            }
            size="small"
            color={
              activityItem.is_overdue
                ? "error"
                : ACTIVITY_STATUS_COLORS[activityItem.status] || "default"
            }
            sx={{ height: 20, fontSize: "0.7rem" }}
          />
        </Stack>
      </Stack>
    </Card>
  );
}

ActivityMiniCard.propTypes = {
  activity: PropTypes.object.isRequired,
  onNavigate: PropTypes.func.isRequired,
  onUnlink: PropTypes.func,
  showUnlink: PropTypes.bool,
};

// ==============================|| NEXT STEPS SECTION ||============================== //

/**
 * NextStepsSection — public component.
 *
 * @param {Object}   activity         - Full activity object
 * @param {Function} onCreateActivity - (activityType, options?) => void.
 *                                      Opens the create-activity modal.
 * @param {Function} onUpdate         - Callback after parent-driven mutations
 *                                      (currently forwarded but unused inside).
 * @param {boolean}  isLocked         - Activity is COMPLETED or CANCELLED →
 *                                      hide creation CTAs.
 */
export default function NextStepsSection({
  activity,
  onCreateActivity,
  onUpdate,
  isLocked = false,
}) {
  const router = useRouter();
  const theme = useTheme();

  // Check if activity belongs to a sequence (Decision Cycle or Campaign)
  const isInSequence =
    Boolean(activity?.decision_cycle) || Boolean(activity?.campaign_detail);
  const isCampaignActivity =
    Boolean(activity?.campaign_detail) && !activity?.decision_cycle;
  const showConversionCta =
    isCampaignActivity &&
    (activity?.outcome === "SUCCESSFUL" ||
      activity?.outcome === "MEETING_SCHEDULED");

  // Sequence context (calculated by backend serializer)
  const sequenceContext = activity?.sequence_context;
  const nextActivities = sequenceContext?.next_activities || [];
  const hasNextActivity = nextActivities.length > 0;

  // Sequence position info
  const isLastInSequence = sequenceContext?.position === sequenceContext?.total;

  // Navigate to activity workspace
  const handleActivityClick = (activityId) => {
    if (activityId) {
      router.push(`/activities/${activityId}`);
    }
  };

  // ========== DISABLED STATE: Not in a sequence ==========
  if (!isInSequence) {
    return (
      <SectionCard title="Next Steps" icon={RocketOutlined}>
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
              fontSize: theme.iconSizes.lg,
              color: theme.palette.grey[400],
              marginBottom: 8,
            }}
          />
          <Typography variant="body2" color="text.disabled" sx={{ mb: 0.5 }}>
            Next step planning requires a sequence.
          </Typography>
          <Typography variant="caption" color="text.disabled">
            Link this activity to a Decision Cycle from the Overview tab to
            enable next steps.
          </Typography>
        </Box>
      </SectionCard>
    );
  }

  // ========== ACTIVE STATE: In a sequence ==========
  return (
    <SectionCard title="Next Steps" icon={RocketOutlined}>
      <Stack spacing={2}>
        {/* Next Activities List (ordered by sequence) */}
        {hasNextActivity && (
          <Box>
            <Typography
              variant="subtitle2"
              color="text.secondary"
              sx={{ mb: 1 }}
            >
              Upcoming in sequence ({nextActivities.length})
            </Typography>
            <Stack spacing={1}>
              {nextActivities.map((nextAct) => (
                <ActivityMiniCard
                  key={nextAct.id}
                  activity={nextAct}
                  onNavigate={handleActivityClick}
                />
              ))}
            </Stack>
          </Box>
        )}

        {/* Create follow-up — only for decision cycle activities */}
        {!isLocked && !isCampaignActivity && (
          <Box>
            {hasNextActivity && (
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ mb: 1 }}
              >
                Create additional follow-up
              </Typography>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
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
          </Box>
        )}

        {/* Campaign conversion CTA */}
        {showConversionCta && !isLocked && (
          <Box
            sx={{
              p: 2,
              borderRadius: 1,
              bgcolor: "success.lighter",
              border: "1px solid",
              borderColor: "success.light",
            }}
          >
            <Stack spacing={1}>
              <Stack direction="row" spacing={1} alignItems="center">
                <TrophyOutlined style={{ color: theme.palette.success.main }} />
                <Typography
                  variant="body2"
                  fontWeight={600}
                  color="success.dark"
                >
                  Successful outcome — ready to convert
                </Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary">
                This prospect responded positively. Start a Decision Cycle to
                move them into your pipeline.
              </Typography>
              <Button
                variant="contained"
                color="success"
                size="small"
                startIcon={<RocketOutlined />}
                onClick={() =>
                  onCreateActivity("MEETING", { convertFromCampaign: true })
                }
              >
                Start Decision Cycle
              </Button>
            </Stack>
          </Box>
        )}

        {/* Empty state hint - only if no next activities */}
        {!hasNextActivity && !isLocked && (
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
              {isLastInSequence
                ? "This is the last activity in the sequence. Create a follow-up to continue the cycle."
                : "No activities scheduled after this one. Create a follow-up to continue."}
            </Typography>
          </Box>
        )}
      </Stack>
    </SectionCard>
  );
}

// ==============================|| PROP TYPES ||============================== //

NextStepsSection.propTypes = {
  activity: PropTypes.object,
  onCreateActivity: PropTypes.func.isRequired,
  onUpdate: PropTypes.func,
  isLocked: PropTypes.bool,
};
