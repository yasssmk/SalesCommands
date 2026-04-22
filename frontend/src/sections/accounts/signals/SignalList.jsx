// frontend/src/sections/accounts/signals/SignalList.jsx
/**
 * SignalList
 *
 * @param {Array}    signals            - Array of signal objects for this type
 * @param {string}   signalType         - 'people' | 'pain' | 'objective' | 'tech-stack'
 * @param {boolean}  loading            - Show skeleton when true
 * @param {*}        error              - Truthy value shows error state
 * @param {Function} onValidate         - (signal, signalType) => void
 * @param {Function} onReject           - (signal, signalType) => void
 * @param {Function} onEdit             - (signal, signalType) => void
 * @param {Function} onDelete           - (signal, signalType) => void
 * @param {string}   emptyMessage       - Primary empty state text
 * @param {string}   [emptyDescription] - Secondary empty state text
 */

"use client";

import PropTypes from "prop-types";

// material-ui
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import AlertOutlined from "@ant-design/icons/AlertOutlined";
import InboxOutlined from "@ant-design/icons/InboxOutlined";

// project imports
import SignalCard from "components/cards/signals/SignalCard";
import PainCard from "components/cards/signals/PainCard";

// ==============================|| SKELETON CARD ||============================== //

/**
 * Skeleton placeholder shown while signals are loading.
 * Matches the approximate height of a real SignalCard.
 */
function SignalCardSkeleton() {
  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1.5,
        p: 2,
      }}
    >
      <Stack spacing={1.5}>
        {/* Header row: badge + title */}
        <Stack direction="row" spacing={1} alignItems="center">
          <Skeleton
            variant="rectangular"
            width={80}
            height={22}
            sx={{ borderRadius: 4 }}
          />
          <Skeleton
            variant="rectangular"
            width={110}
            height={22}
            sx={{ borderRadius: 4 }}
          />
          <Box flex={1} />
          <Skeleton variant="circular" width={28} height={28} />
        </Stack>

        {/* Value */}
        <Skeleton variant="text" width="75%" height={20} />
        <Skeleton variant="text" width="50%" height={20} />

        {/* Footer row: meta info */}
        <Stack direction="row" spacing={2}>
          <Skeleton variant="text" width={100} height={16} />
          <Skeleton variant="text" width={80} height={16} />
        </Stack>
      </Stack>
    </Box>
  );
}

// ==============================|| EMPTY STATE ||============================== //

function EmptyState({ message, description }) {
  return (
    <Stack spacing={1.5} alignItems="center" py={6}>
      <InboxOutlined style={{ fontSize: 36, color: "#bfbfbf" }} />
      <Typography variant="body1" color="text.secondary" fontWeight={500}>
        {message}
      </Typography>
      {description && (
        <Typography
          variant="body2"
          color="text.disabled"
          textAlign="center"
          maxWidth={380}
        >
          {description}
        </Typography>
      )}
    </Stack>
  );
}

EmptyState.propTypes = {
  message: PropTypes.string.isRequired,
  description: PropTypes.string,
};

// ==============================|| ERROR STATE ||============================== //

function ErrorState() {
  return (
    <Stack spacing={1} alignItems="center" py={6}>
      <AlertOutlined style={{ fontSize: 32, color: "#ff4d4f" }} />
      <Typography variant="body2" color="error">
        Failed to load signals. Please refresh and try again.
      </Typography>
    </Stack>
  );
}

// ==============================|| SIGNAL LIST ||============================== //

/**
 * SignalList
 *
 * @param {Array}    signals          - Tagged signal objects (each has .signalType)
 * @param {boolean}  loading          - Show skeleton when true
 * @param {*}        error            - Truthy value shows error state
 * @param {Function} onValidate       - (signal, signalType) => void
 * @param {Function} onReject         - (signal, signalType) => void
 * @param {Function} onEdit           - (signal, signalType) => void
 * @param {Function} onSupersede      - (signal, signalType) => void
 * @param {Function} onDelete         - (signal, signalType) => void
 * @param {string}   emptyMessage     - Primary empty state text
 * @param {string}   [emptyDescription] - Secondary empty state text
 */
export default function SignalList({
  signals,
  signalType,
  loading,
  error,
  onValidate,
  onReject,
  onEdit,
  onDelete,
  emptyMessage,
  emptyDescription,
  // Pain-specific action props — only used when signalType === 'pain'.
  // Ignored silently for the other 3 types; required when signalType === 'pain'
  // (see PropTypes validator below).
  choices,
  onAddImpact,
  onEditImpact,
  onDeleteImpact,
}) {
  // ==============================|| LOADING ||============================== //

  if (loading) {
    return (
      <Stack spacing={1.5}>
        <SignalCardSkeleton />
        <SignalCardSkeleton />
        <SignalCardSkeleton />
      </Stack>
    );
  }

  // ==============================|| ERROR ||============================== //

  if (error) {
    return <ErrorState />;
  }

  // ==============================|| EMPTY ||============================== //

  if (!signals || signals.length === 0) {
    return (
      <EmptyState
        message={emptyMessage || "No signals found"}
        description={emptyDescription}
      />
    );
  }

  // ==============================|| LIST ||============================== //

  // Pain gets a dedicated card with nested impacts + impact CRUD controls.
  // The generic SignalCard stays authoritative for the other 3 types.
  const isPain = signalType === "pain";

  return (
    <Stack spacing={1.5}>
      {signals.map((signal) =>
        isPain ? (
          <PainCard
            key={signal.id}
            pain={signal}
            choices={choices}
            onValidate={onValidate}
            onReject={onReject}
            onEdit={onEdit}
            onDelete={onDelete}
            onAddImpact={onAddImpact}
            onEditImpact={onEditImpact}
            onDeleteImpact={onDeleteImpact}
          />
        ) : (
          <SignalCard
            key={signal.id}
            signal={signal}
            signalType={signalType}
            onValidate={onValidate}
            onReject={onReject}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ),
      )}

      {/* Total count footer */}
      {signals.length > 0 && (
        <Stack direction="row" justifyContent="flex-end" sx={{ pt: 0.5 }}>
          <Chip
            label={`${signals.length} signal${signals.length === 1 ? "" : "s"}`}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.7rem" }}
          />
        </Stack>
      )}
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

SignalList.propTypes = {
  signals: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
    }),
  ),
  signalType: PropTypes.oneOf(["people", "pain", "objective", "tech-stack"])
    .isRequired,
  loading: PropTypes.bool,
  error: PropTypes.any,
  onValidate: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  emptyMessage: PropTypes.string,
  emptyDescription: PropTypes.string,

  // Pain-only props — resolved from useGetSignalChoices() and the parent's
  // impact CRUD handlers. Not enforced as strictly required so that
  // non-Pain callers (People / Objective / TechStack lists) can omit them
  // without PropTypes warnings. A Pain-typed SignalList without these
  // props will crash at the PainCard level — the failure is obvious.
  choices: PropTypes.object,
  onAddImpact: PropTypes.func,
  onEditImpact: PropTypes.func,
  onDeleteImpact: PropTypes.func,
};
