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
import ObjectiveCard from "components/cards/signals/ObjectiveCard";
import TechStackCard from "components/cards/signals/TechStackCard";

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
  // Props consumed by dedicated card components:
  //   - `choices` is needed by PainCard (impact labels / human_impacts)
  //     AND by ObjectiveCard (canonical axes + scope labels — Wave B).
  //     Ignored silently when signalType is People / TechStack.
  //   - `onAddImpact` / `onEditImpact` / `onDeleteImpact` are Pain-only.
  //     A Pain SignalList without these handlers will crash at PainCard
  //     level — the failure is obvious.
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

  // Each signal type can route to a dedicated card component. The generic
  // SignalCard remains authoritative for People only — Pain, Objective,
  // and Tech Stack each have their own dedicated card with type-specific
  // affordances.
  //
  // Dedicated cards:
  //   - pain       → PainCard        (nested impacts + impact CRUD controls)
  //   - objective  → ObjectiveCard   (canonical axes + scope + target_date
  //                                    urgency — Wave B)
  //   - tech-stack → TechStackCard   (catalog anchor + lifecycle +
  //                                    competitor / integration flags —
  //                                    Sprint TechStack)
  //
  // Resolution is done once per type (outside the map) so the branch
  // predicate stays O(1) per row.
  const isPain = signalType === "pain";
  const isObjective = signalType === "objective";
  const isTechStack = signalType === "tech-stack";

  const renderSignalCard = (signal) => {
    if (isPain) {
      return (
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
      );
    }
    if (isObjective) {
      return (
        <ObjectiveCard
          key={signal.id}
          objective={signal}
          choices={choices}
          onValidate={onValidate}
          onReject={onReject}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      );
    }
    if (isTechStack) {
      return (
        <TechStackCard
          key={signal.id}
          techStack={signal}
          choices={choices}
          onValidate={onValidate}
          onReject={onReject}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      );
    }
    // Fallback: People (and any other future type) renders via the
    // generic SignalCard. SignalCard's PainSignalBody / TechStackSignalBody
    // fallbacks remain visible warnings if someone bypasses this routing.
    return (
      <SignalCard
        key={signal.id}
        signal={signal}
        signalType={signalType}
        onValidate={onValidate}
        onReject={onReject}
        onEdit={onEdit}
        onDelete={onDelete}
      />
    );
  };

  return (
    <Stack spacing={1.5}>
      {signals.map(renderSignalCard)}

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

  // `choices` is consumed by PainCard + ObjectiveCard (Wave B) to render
  // canonical axis and scope labels. Not enforced strictly required so
  // that People / TechStack callers can omit it without warnings, but
  // Pain / Objective lists without it will render raw enum values.
  //
  // `onAddImpact` / `onEditImpact` / `onDeleteImpact` are Pain-only —
  // omitted for any other signalType. A Pain SignalList without these
  // handlers will crash at the PainCard level (obvious failure).
  choices: PropTypes.object,
  onAddImpact: PropTypes.func,
  onEditImpact: PropTypes.func,
  onDeleteImpact: PropTypes.func,
};
