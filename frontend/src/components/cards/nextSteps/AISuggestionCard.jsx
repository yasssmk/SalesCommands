// frontend/src/components/cards/nextSteps/AISuggestionCard.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  RobotOutlined,
  EditOutlined,
  CloseCircleOutlined,
  CheckCircleOutlined,
  EyeOutlined,
} from "@ant-design/icons";

// Project imports
import { ACTIVITY_TYPE_LABELS } from "api/accounts/activities";

// ==============================|| STATUS STYLES ||============================== //

const STATUS_STYLES = {
  PENDING: {
    border: "2px dashed",
    borderColor: "warning.main",
    bgcolor: "warning.lighter",
  },
  VALIDATED: {
    border: "1px solid",
    borderColor: "divider",
    bgcolor: "action.hover",
    opacity: 0.75,
  },
  REJECTED: {
    border: "1px solid",
    borderColor: "divider",
    bgcolor: "action.disabledBackground",
    opacity: 0.5,
  },
};

// ==============================|| AI SUGGESTION CARD ||============================== //

export default function AISuggestionCard({
  signal,
  onConvert,
  onEdit,
  onReject,
  onViewActivity,
  isLocked,
}) {
  const status = signal?.status || "PENDING";
  const styles = STATUS_STYLES[status] || STATUS_STYLES.PENDING;
  const linkedActivity = signal?.linked_activity;

  const suggestedContacts = signal?.suggested_contacts || [];
  const contactNames = suggestedContacts
    .map((c) => `${c.first_name || ""} ${c.last_name || ""}`.trim())
    .filter(Boolean);

  return (
    <Card
      variant="outlined"
      sx={{
        ...styles,
        transition: "opacity 0.3s ease",
      }}
    >
      <CardContent sx={{ py: 1.5, px: 2, "&:last-child": { pb: 1.5 } }}>
        <Stack spacing={1}>
          {/* Header — badge + type chip + due date */}
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
          >
            <Chip
              icon={<RobotOutlined style={{ fontSize: 12 }} />}
              label="AI Suggestion"
              size="small"
              color="warning"
              variant="outlined"
              sx={{ height: 22, "& .MuiChip-label": { px: 0.75 } }}
            />
            {signal?.suggested_activity_type && (
              <Chip
                label={
                  ACTIVITY_TYPE_LABELS[signal.suggested_activity_type] ||
                  signal.suggested_activity_type
                }
                size="small"
                variant="filled"
                color="default"
                sx={{ height: 22 }}
              />
            )}
            {signal?.suggested_due_date && (
              <Typography variant="caption" color="text.secondary">
                suggested {signal.suggested_due_date}
              </Typography>
            )}
            {status !== "PENDING" && (
              <Chip
                label={status === "VALIDATED" ? "Converted" : "Rejected"}
                size="small"
                color={status === "VALIDATED" ? "success" : "default"}
                sx={{ height: 22 }}
              />
            )}
          </Stack>

          {/* Title */}
          <Typography variant="subtitle2" fontWeight={600}>
            {signal?.suggested_title || "Untitled suggestion"}
          </Typography>

          {/* Source quote */}
          {signal?.source_quote && (
            <Box
              sx={{
                borderLeft: 3,
                borderColor: "divider",
                pl: 1.5,
                py: 0.5,
              }}
            >
              <Typography
                variant="body2"
                color="text.secondary"
                fontStyle="italic"
                sx={{
                  display: "-webkit-box",
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                &ldquo;{signal.source_quote}&rdquo;
              </Typography>
            </Box>
          )}

          {/* Contacts */}
          {contactNames.length > 0 && (
            <Typography variant="caption" color="text.secondary">
              {contactNames.join(" · ")}
            </Typography>
          )}

          {/* Actions */}
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            {status === "PENDING" && !isLocked && (
              <>
                <Button
                  size="small"
                  variant="contained"
                  color="primary"
                  startIcon={<CheckCircleOutlined style={{ fontSize: 14 }} />}
                  onClick={() => onConvert?.(signal)}
                >
                  Convert to Activity
                </Button>
                <Tooltip title="Edit suggestion before converting">
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<EditOutlined style={{ fontSize: 14 }} />}
                    onClick={() => onEdit?.(signal)}
                  >
                    Edit
                  </Button>
                </Tooltip>
                <Button
                  size="small"
                  color="error"
                  startIcon={
                    <CloseCircleOutlined style={{ fontSize: 14 }} />
                  }
                  onClick={() => onReject?.(signal)}
                >
                  Reject
                </Button>
              </>
            )}
            {status === "VALIDATED" && linkedActivity && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<EyeOutlined style={{ fontSize: 14 }} />}
                onClick={() => onViewActivity?.(linkedActivity)}
              >
                View Activity
              </Button>
            )}
            {status === "VALIDATED" && !linkedActivity && (
              <Typography variant="caption" color="text.disabled">
                Activity deleted
              </Typography>
            )}
            {(status === "VALIDATED" || status === "REJECTED") &&
              !isLocked && (
                <Button
                  size="small"
                  variant="text"
                  startIcon={<EditOutlined style={{ fontSize: 14 }} />}
                  onClick={() => onEdit?.(signal)}
                >
                  Edit / Reopen
                </Button>
              )}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
}

// ==============================|| PROP TYPES ||============================== //

AISuggestionCard.propTypes = {
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string,
    suggested_title: PropTypes.string,
    suggested_activity_type: PropTypes.string,
    suggested_due_date: PropTypes.string,
    suggested_contacts: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string,
        first_name: PropTypes.string,
        last_name: PropTypes.string,
      }),
    ),
    source_quote: PropTypes.string,
    linked_activity: PropTypes.shape({
      id: PropTypes.string,
      title: PropTypes.string,
    }),
  }).isRequired,
  onConvert: PropTypes.func,
  onEdit: PropTypes.func,
  onReject: PropTypes.func,
  onViewActivity: PropTypes.func,
  isLocked: PropTypes.bool,
};
