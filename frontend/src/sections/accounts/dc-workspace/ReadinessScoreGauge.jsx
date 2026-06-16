// frontend/src/sections/accounts/dc-workspace/ReadinessScoreGauge.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";

// ==============================|| SCORE HELPERS ||============================== //

function getScoreCategory(score) {
  if (score >= 80) return { key: "excellent", label: "Excellent", color: "success" };
  if (score >= 60) return { key: "good", label: "Good", color: "info" };
  if (score >= 40) return { key: "fair", label: "Fair", color: "warning" };
  return { key: "poor", label: "Needs work", color: "error" };
}

function getProgressColor(score) {
  if (score >= 80) return "success";
  if (score >= 60) return "info";
  if (score >= 40) return "warning";
  return "error";
}

// ==============================|| READINESS SCORE GAUGE ||============================== //

export default function ReadinessScoreGauge({ score, dimensions }) {
  const safeScore = typeof score === "number" ? score : 0;
  const category = getScoreCategory(safeScore);
  const progressColor = getProgressColor(safeScore);

  return (
    <Stack spacing={2.5} alignItems="center">
      {/* Circular gauge */}
      <Box sx={{ position: "relative", display: "inline-flex" }}>
        <CircularProgress
          variant="determinate"
          value={100}
          size={88}
          thickness={4}
          sx={{ color: "divider", position: "absolute" }}
        />
        <CircularProgress
          variant="determinate"
          value={safeScore}
          size={88}
          thickness={4}
          color={progressColor}
        />
        <Box
          sx={{
            top: 0,
            left: 0,
            bottom: 0,
            right: 0,
            position: "absolute",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
          }}
        >
          <Typography variant="h4" fontWeight={700} lineHeight={1}>
            {safeScore}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            / 100
          </Typography>
        </Box>
      </Box>

      <Chip label={category.label} size="small" color={category.color} />

      {/* Dimensions breakdown */}
      {dimensions && dimensions.length > 0 && (
        <Stack spacing={0.75} sx={{ width: "100%", maxWidth: 320 }}>
          <Typography variant="caption" color="text.secondary" fontWeight={600}>
            Readiness dimensions
          </Typography>
          {dimensions.map((d) => (
            <Stack
              key={d.name}
              direction="row"
              spacing={1}
              alignItems="center"
              justifyContent="space-between"
            >
              <Stack direction="row" spacing={0.75} alignItems="center">
                {d.filled ? (
                  <CheckCircleOutlined style={{ fontSize: 14, color: "#52c41a" }} />
                ) : (
                  <CloseCircleOutlined style={{ fontSize: 14, color: "#d9d9d9" }} />
                )}
                <Typography variant="caption">{d.detail}</Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary">
                {d.weight}pts
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}
    </Stack>
  );
}

ReadinessScoreGauge.propTypes = {
  score: PropTypes.number,
  dimensions: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      filled: PropTypes.bool.isRequired,
      weight: PropTypes.number.isRequired,
      detail: PropTypes.string.isRequired,
    }),
  ),
};
