// frontend/src/components/cards/nextSteps/LinkedActivityCard.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";

// Icons
import { EyeOutlined } from "@ant-design/icons";

// Project imports
import {
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS,
} from "api/accounts/activities";

// ==============================|| LINKED ACTIVITY CARD ||============================== //

export default function LinkedActivityCard({ activity, onOpen }) {
  if (!activity) return null;

  return (
    <Card
      variant="outlined"
      sx={{ border: "1px solid", borderColor: "divider" }}
    >
      <CardContent sx={{ py: 1.5, px: 2, "&:last-child": { pb: 1.5 } }}>
        <Stack spacing={0.75}>
          {/* Header — type + status + date */}
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
          >
            {activity.activity_type && (
              <Chip
                label={
                  ACTIVITY_TYPE_LABELS[activity.activity_type] ||
                  activity.activity_type_display ||
                  activity.activity_type
                }
                size="small"
                variant="filled"
                color="default"
                sx={{ height: 22 }}
              />
            )}
            {activity.status && (
              <Chip
                label={
                  ACTIVITY_STATUS_LABELS[activity.status] ||
                  activity.status_display ||
                  activity.status
                }
                size="small"
                color={ACTIVITY_STATUS_COLORS[activity.status] || "default"}
                sx={{ height: 22 }}
              />
            )}
            {(activity.scheduled_date || activity.due_date) && (
              <Typography variant="caption" color="text.secondary">
                {activity.scheduled_date || activity.due_date}
              </Typography>
            )}
          </Stack>

          {/* Title */}
          <Typography variant="subtitle2" fontWeight={600}>
            {activity.title}
          </Typography>

          {/* Action */}
          <Stack direction="row" justifyContent="flex-end">
            <Button
              size="small"
              variant="outlined"
              startIcon={<EyeOutlined style={{ fontSize: 14 }} />}
              onClick={() => onOpen?.(activity)}
            >
              Open Activity
            </Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
}

// ==============================|| PROP TYPES ||============================== //

LinkedActivityCard.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string.isRequired,
    title: PropTypes.string,
    activity_type: PropTypes.string,
    activity_type_display: PropTypes.string,
    status: PropTypes.string,
    status_display: PropTypes.string,
    scheduled_date: PropTypes.string,
    due_date: PropTypes.string,
  }),
  onOpen: PropTypes.func,
};
