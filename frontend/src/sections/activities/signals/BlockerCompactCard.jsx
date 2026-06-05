// frontend/src/sections/activities/signals/BlockerCompactCard.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  UserOutlined,
} from "@ant-design/icons";

// Project imports
import SignalStatusChip from "components/chips/SignalStatusChip";

function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}

// ==============================|| BLOCKER COMPACT CARD ||============================== //

export default function BlockerCompactCard({
  signal,
  onSelect,
  onValidate,
  onReject,
  isLocked,
}) {
  const isPending = signal.status === "PENDING";
  const isRejected = signal.status === "REJECTED";
  const contactName = formatContact(signal.contact);

  return (
    <Box
      onClick={() => onSelect?.(signal, "blockers")}
      sx={{
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        p: 2,
        cursor: "pointer",
        opacity: isRejected ? 0.5 : 1,
        "&:hover": { bgcolor: "action.hover" },
        transition: "background-color 0.15s",
        mb: 1.5,
      }}
    >
      {/* Top row: summary + status + actions */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        spacing={1}
      >
        <Typography variant="body2" fontWeight={500} sx={{ flex: 1 }}>
          {signal.summary || "—"}
        </Typography>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <SignalStatusChip status={signal.status} size="small" />
          {isPending && !isLocked && (
            <>
              <Tooltip title="Validate">
                <IconButton
                  size="small"
                  color="success"
                  onClick={(e) => {
                    e.stopPropagation();
                    onValidate?.(signal, "blockers");
                  }}
                  aria-label="Validate blocker"
                >
                  <CheckCircleOutlined style={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
              <Tooltip title="Reject">
                <IconButton
                  size="small"
                  color="error"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReject?.(signal, "blockers");
                  }}
                  aria-label="Reject blocker"
                >
                  <CloseCircleOutlined style={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            </>
          )}
        </Stack>
      </Stack>

      {/* Source quote */}
      {signal.source_quote && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ fontStyle: "italic", display: "block", mt: 0.75 }}
        >
          &ldquo;{signal.source_quote}&rdquo;
        </Typography>
      )}

      {/* Contact */}
      <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.75 }}>
        <UserOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
        <Typography variant="caption" color="text.secondary">
          {contactName || "No contact attributed"}
        </Typography>
      </Stack>
    </Box>
  );
}

BlockerCompactCard.propTypes = {
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    summary: PropTypes.string,
    source_quote: PropTypes.string,
    contact: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
    }),
  }).isRequired,
  onSelect: PropTypes.func,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  isLocked: PropTypes.bool,
};
