// frontend/src/sections/accounts/signals/SignalCard.jsx
/**
 * SignalCard — displays a single signal of any type with its metadata
 * and contextual actions.
 *
 * Actions available per status:
 *   PENDING   → Validate, Reject, Edit, Delete
 *   VALIDATED → Edit, Delete
 *   REJECTED  → Delete only
 *
 * The card body is rendered differently per signalType.
 * An expandable detail section (collapsed by default) shows secondary fields.
 *
 * The component does NOT infer signalType from the signal object —
 * it must be passed explicitly as a prop.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";

// material-ui
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Collapse from "@mui/material/Collapse";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// ant-design icons
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import UpOutlined from "@ant-design/icons/UpOutlined";

// ==============================|| STATUS CONFIG ||============================== //

/**
 * MUI Chip color + label per SignalStatus value.
 * MERGED intentionally absent — no longer exists in the new architecture.
 */
const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  VALIDATED: { color: "success", label: "Validated" },
  REJECTED: { color: "error", label: "Rejected" },
};

// ==============================|| TYPE CONFIG ||============================== //

/**
 * Distinct MUI Chip color + display label per signal type.
 */
const TYPE_CONFIG = {
  people: { color: "secondary", label: "People" },
  pain: { color: "error", label: "Pain" },
  objective: { color: "info", label: "Objective" },
  "tech-stack": { color: "primary", label: "Tech Stack" },
};

// ==============================|| HELPERS ||============================== //

/**
 * Format a contact object into a display string.
 *
 * @param {{ first_name?: string, last_name?: string, job_title?: string }|null} contact
 * @returns {string|null}
 */
function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}

/**
 * Truncate a string to a max length, appending an ellipsis if needed.
 *
 * @param {string|null|undefined} str
 * @param {number} max
 * @returns {string|null}
 */
function truncate(str, max = 120) {
  if (!str) return null;
  return str.length > max ? `${str.slice(0, max)}…` : str;
}

// ==============================|| META ITEM ||============================== //

/**
 * Small labelled metadata item used in card footers.
 */
function MetaItem({ label, value }) {
  if (!value) return null;
  return (
    <Stack direction="row" spacing={0.5} alignItems="baseline">
      <Typography
        variant="caption"
        color="text.disabled"
        sx={{ whiteSpace: "nowrap" }}
      >
        {label}:
      </Typography>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ fontWeight: 500 }}
      >
        {value}
      </Typography>
    </Stack>
  );
}

MetaItem.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.string,
};

// ==============================|| DETAIL FIELD ||============================== //

/**
 * A labelled text block used inside the expandable detail section.
 */
function DetailField({ label, value }) {
  if (!value) return null;
  return (
    <Box>
      <Typography
        variant="caption"
        color="text.disabled"
        display="block"
        gutterBottom
      >
        {label}
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
      >
        {value}
      </Typography>
    </Box>
  );
}

DetailField.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.string,
};

// ==============================|| QUOTE BLOCK ||============================== //

/**
 * Styled block quote for source_quote fields.
 */
function QuoteBlock({ value }) {
  if (!value) return null;
  return (
    <Box>
      <Typography
        variant="caption"
        color="text.disabled"
        display="block"
        gutterBottom
      >
        Source quote
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{
          fontStyle: "italic",
          pl: 1.5,
          borderLeft: "3px solid",
          borderColor: "divider",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        &ldquo;{value}&rdquo;
      </Typography>
    </Box>
  );
}

QuoteBlock.propTypes = {
  value: PropTypes.string,
};

// ==============================|| CARD BODY — PER TYPE ||============================== //

/**
 * PeopleSignalBody
 * Primary:   role_display (bold), influence_level_display (muted)
 * Secondary: target_contact full name + job_title
 */
function PeopleSignalBody({ signal }) {
  const targetName = formatContact(signal.target_contact);
  const targetTitle = signal.target_contact?.job_title ?? null;

  return (
    <Stack spacing={0.75} sx={{ mt: 1 }}>
      {/* Role + influence */}
      <Stack
        direction="row"
        spacing={1}
        alignItems="baseline"
        flexWrap="wrap"
        useFlexGap
      >
        {signal.role_display && (
          <Typography variant="body2" fontWeight={600}>
            {signal.role_display}
          </Typography>
        )}
        {signal.influence_level_display && (
          <Typography variant="caption" color="text.secondary">
            {signal.influence_level_display}
          </Typography>
        )}
      </Stack>

      {/* Target contact */}
      {targetName && (
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Typography variant="body2" color="text.secondary">
            {targetName}
          </Typography>
          {targetTitle && (
            <Typography variant="caption" color="text.disabled">
              · {targetTitle}
            </Typography>
          )}
        </Stack>
      )}

      {/* Footer */}
      <Stack
        direction="row"
        spacing={2}
        flexWrap="wrap"
        useFlexGap
        sx={{ mt: 0.5 }}
      >
        <MetaItem label="From" value={formatContact(signal.source_contact)} />
        {signal.notes && (
          <MetaItem label="Notes" value={truncate(signal.notes, 80)} />
        )}
      </Stack>
    </Stack>
  );
}

PeopleSignalBody.propTypes = { signal: PropTypes.object.isRequired };

/**
 * PainSignalBody
 * Primary:   summary (bold, max 2 lines)
 * Secondary: category_display chip + pain_level_display chip
 * Footer:    business_cost, source_contact name
 */
function PainSignalBody({ signal }) {
  return (
    <Stack spacing={0.75} sx={{ mt: 1 }}>
      {/* Summary */}
      {signal.summary && (
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {signal.summary}
        </Typography>
      )}

      {/* Category + pain level chips */}
      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
        {signal.category_display && (
          <Chip
            label={signal.category_display}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.65rem", height: 20 }}
          />
        )}
        {signal.pain_level_display && (
          <Chip
            label={signal.pain_level_display}
            size="small"
            color="error"
            variant="outlined"
            sx={{ fontSize: "0.65rem", height: 20 }}
          />
        )}
      </Stack>

      {/* Footer */}
      <Stack
        direction="row"
        spacing={2}
        flexWrap="wrap"
        useFlexGap
        sx={{ mt: 0.5 }}
      >
        <MetaItem label="From" value={formatContact(signal.source_contact)} />
        {signal.business_cost && (
          <MetaItem label="Business cost" value={signal.business_cost} />
        )}
      </Stack>
    </Stack>
  );
}

PainSignalBody.propTypes = { signal: PropTypes.object.isRequired };

/**
 * ObjectiveSignalBody
 * Primary:   summary (bold, max 2 lines)
 * Secondary: goal_level_display chip
 * Footer:    success_criteria (truncated), source_contact name
 */
function ObjectiveSignalBody({ signal }) {
  return (
    <Stack spacing={0.75} sx={{ mt: 1 }}>
      {/* Summary */}
      {signal.summary && (
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {signal.summary}
        </Typography>
      )}

      {/* Goal level chip */}
      {signal.goal_level_display && (
        <Box>
          <Chip
            label={signal.goal_level_display}
            size="small"
            color="info"
            variant="outlined"
            sx={{ fontSize: "0.65rem", height: 20 }}
          />
        </Box>
      )}

      {/* Footer */}
      <Stack
        direction="row"
        spacing={2}
        flexWrap="wrap"
        useFlexGap
        sx={{ mt: 0.5 }}
      >
        <MetaItem label="From" value={formatContact(signal.source_contact)} />
        {signal.success_criteria && (
          <MetaItem
            label="Success criteria"
            value={truncate(signal.success_criteria, 80)}
          />
        )}
      </Stack>
    </Stack>
  );
}

ObjectiveSignalBody.propTypes = { signal: PropTypes.object.isRequired };

/**
 * TechStackSignalBody
 * Primary:   tech_name (bold) + category_display chip
 * Secondary: satisfaction_display chip
 * Footer:    usage (truncated), renewal_date
 */
function TechStackSignalBody({ signal }) {
  return (
    <Stack spacing={0.75} sx={{ mt: 1 }}>
      {/* Tech name + category */}
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
      >
        {signal.tech_name && (
          <Typography variant="body2" fontWeight={600}>
            {signal.tech_name}
          </Typography>
        )}
        {signal.category_display && (
          <Chip
            label={signal.category_display}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.65rem", height: 20 }}
          />
        )}
      </Stack>

      {/* Satisfaction chip */}
      {signal.satisfaction_display && (
        <Box>
          <Chip
            label={signal.satisfaction_display}
            size="small"
            color="primary"
            variant="outlined"
            sx={{ fontSize: "0.65rem", height: 20 }}
          />
        </Box>
      )}

      {/* Footer */}
      <Stack
        direction="row"
        spacing={2}
        flexWrap="wrap"
        useFlexGap
        sx={{ mt: 0.5 }}
      >
        <MetaItem label="From" value={formatContact(signal.source_contact)} />
        {signal.usage && (
          <MetaItem label="Usage" value={truncate(signal.usage, 80)} />
        )}
        {signal.renewal_date && (
          <MetaItem label="Renewal" value={signal.renewal_date} />
        )}
      </Stack>
    </Stack>
  );
}

TechStackSignalBody.propTypes = { signal: PropTypes.object.isRequired };

// ==============================|| EXPANDED DETAIL — PER TYPE ||============================== //

function PeopleSignalDetail({ signal }) {
  return (
    <Stack spacing={1.5}>
      <DetailField label="Notes" value={signal.notes} />
      <QuoteBlock value={signal.source_quote} />
      {signal.signal_category_display && (
        <MetaItem
          label="Signal category"
          value={signal.signal_category_display}
        />
      )}
    </Stack>
  );
}
PeopleSignalDetail.propTypes = { signal: PropTypes.object.isRequired };

function PainSignalDetail({ signal }) {
  return (
    <Stack spacing={1.5}>
      <DetailField label="Impact summary" value={signal.impact_summary} />
      <DetailField label="Notes" value={signal.notes} />
      <QuoteBlock value={signal.source_quote} />
      {signal.signal_category_display && (
        <MetaItem
          label="Signal category"
          value={signal.signal_category_display}
        />
      )}
    </Stack>
  );
}
PainSignalDetail.propTypes = { signal: PropTypes.object.isRequired };

function ObjectiveSignalDetail({ signal }) {
  return (
    <Stack spacing={1.5}>
      <DetailField
        label="Measurement method"
        value={signal.measurement_method}
      />
      <DetailField label="Notes" value={signal.notes} />
      <QuoteBlock value={signal.source_quote} />
      {signal.signal_category_display && (
        <MetaItem
          label="Signal category"
          value={signal.signal_category_display}
        />
      )}
    </Stack>
  );
}
ObjectiveSignalDetail.propTypes = { signal: PropTypes.object.isRequired };

function TechStackSignalDetail({ signal }) {
  return (
    <Stack spacing={1.5}>
      <DetailField label="Limitations" value={signal.limitations} />
      <DetailField label="Workarounds" value={signal.workarounds} />
      <DetailField label="Integrations" value={signal.integrations} />
      <QuoteBlock value={signal.source_quote} />
      {signal.signal_category_display && (
        <MetaItem
          label="Signal category"
          value={signal.signal_category_display}
        />
      )}
    </Stack>
  );
}
TechStackSignalDetail.propTypes = { signal: PropTypes.object.isRequired };

// ==============================|| SIGNAL CARD ||============================== //

/**
 * SignalCard
 *
 * @param {Object}   signal      - Signal data object (shape varies per type)
 * @param {string}   signalType  - 'people' | 'pain' | 'objective' | 'tech-stack'
 * @param {Function} onValidate  - (signal, signalType) => void
 * @param {Function} onReject    - (signal, signalType) => void
 * @param {Function} onEdit      - (signal, signalType) => void
 * @param {Function} onDelete    - (signal, signalType) => void
 */
export default function SignalCard({
  signal,
  signalType,
  onValidate,
  onReject,
  onEdit,
  onDelete,
}) {
  // ==============================|| LOCAL STATE ||============================== //

  const [menuAnchor, setMenuAnchor] = useState(null);
  const [expanded, setExpanded] = useState(false);

  // ==============================|| DERIVED ||============================== //

  const status = signal.status ?? "PENDING";
  const statusCfg = STATUS_CONFIG[status] ?? {
    color: "default",
    label: status,
  };
  const typeCfg = TYPE_CONFIG[signalType] ?? {
    color: "default",
    label: signalType,
  };

  const isPending = status === "PENDING";
  const isValidated = status === "VALIDATED";

  /** Formatted creation date */
  const createdDate = signal.created_at
    ? new Date(signal.created_at).toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : null;

  /**
   * Source context line — always visible at the bottom of the card.
   * "From [contact name] · [activity id truncated]" or "Source: [source_display]"
   */
  const sourceContext = (() => {
    const contactName = formatContact(signal.source_contact);
    const activitySuffix = signal.source_activity?.id
      ? `· ${String(signal.source_activity.id).slice(0, 8)}…`
      : "";

    if (contactName) {
      return `From ${contactName} ${activitySuffix}`.trim();
    }
    if (signal.source_display) {
      return `Source: ${signal.source_display}`;
    }
    return null;
  })();

  // ==============================|| MENU HANDLERS ||============================== //

  const handleMenuOpen = useCallback((e) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  }, []);

  const handleMenuClose = useCallback(() => setMenuAnchor(null), []);

  const handleEdit = useCallback(() => {
    handleMenuClose();
    onEdit(signal, signalType);
  }, [handleMenuClose, onEdit, signal, signalType]);

  const handleDelete = useCallback(() => {
    handleMenuClose();
    onDelete(signal, signalType);
  }, [handleMenuClose, onDelete, signal, signalType]);

  const handleValidate = useCallback(() => {
    onValidate(signal, signalType);
  }, [onValidate, signal, signalType]);

  const handleReject = useCallback(() => {
    onReject(signal, signalType);
  }, [onReject, signal, signalType]);

  const handleToggleExpand = useCallback(() => setExpanded((v) => !v), []);

  // ==============================|| RENDER ||============================== //

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: isPending ? "warning.light" : "divider",
        borderRadius: 1.5,
        p: 2,
        bgcolor: "background.paper",
        transition: "border-color 0.15s",
        "&:hover": { borderColor: "primary.light" },
      }}
    >
      {/* ==================== HEADER ROW ==================== */}
      <Stack direction="row" spacing={1} alignItems="flex-start">
        {/* Left: type chip + status chip + date */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1 }}
        >
          <Chip
            label={typeCfg.label}
            color={typeCfg.color}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />
          <Chip
            label={statusCfg.label}
            color={statusCfg.color}
            size="small"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />
          {createdDate && (
            <Typography variant="caption" color="text.disabled">
              {createdDate}
            </Typography>
          )}
        </Stack>

        {/* Right: quick actions + overflow menu + expand toggle */}
        <Stack direction="row" spacing={0.5} alignItems="center" flexShrink={0}>
          {/* Validate — PENDING only */}
          {isPending && (
            <Tooltip title="Validate signal">
              <IconButton
                size="small"
                color="success"
                onClick={handleValidate}
                aria-label="Validate signal"
              >
                <CheckCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          {/* Reject — PENDING only */}
          {isPending && (
            <Tooltip title="Reject signal">
              <IconButton
                size="small"
                color="error"
                onClick={handleReject}
                aria-label="Reject signal"
              >
                <CloseCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          {/* Overflow menu — Edit (PENDING + VALIDATED) + Delete (always) */}
          <IconButton
            size="small"
            onClick={handleMenuOpen}
            aria-label="Signal actions"
            aria-controls={menuAnchor ? "signal-action-menu" : undefined}
            aria-haspopup="true"
            aria-expanded={Boolean(menuAnchor)}
          >
            <MoreOutlined style={{ fontSize: 16 }} />
          </IconButton>

          <Menu
            id="signal-action-menu"
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={handleMenuClose}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            {/* Edit — PENDING and VALIDATED only */}
            {(isPending || isValidated) && (
              <MenuItem onClick={handleEdit} dense>
                <Stack direction="row" spacing={1} alignItems="center">
                  <EditOutlined style={{ fontSize: 14 }} />
                  <span>Edit</span>
                </Stack>
              </MenuItem>
            )}

            {/* Delete — always available */}
            <MenuItem onClick={handleDelete} dense sx={{ color: "error.main" }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <DeleteOutlined style={{ fontSize: 14 }} />
                <span>Delete</span>
              </Stack>
            </MenuItem>
          </Menu>

          {/* Expand toggle */}
          <IconButton
            size="small"
            onClick={handleToggleExpand}
            aria-label={expanded ? "Collapse details" : "Expand details"}
          >
            {expanded ? (
              <UpOutlined style={{ fontSize: 12 }} />
            ) : (
              <DownOutlined style={{ fontSize: 12 }} />
            )}
          </IconButton>
        </Stack>
      </Stack>

      {/* ==================== CARD BODY — PER TYPE ==================== */}
      {signalType === "people" && <PeopleSignalBody signal={signal} />}
      {signalType === "pain" && <PainSignalBody signal={signal} />}
      {signalType === "objective" && <ObjectiveSignalBody signal={signal} />}
      {signalType === "tech-stack" && <TechStackSignalBody signal={signal} />}

      {/* ==================== SOURCE CONTEXT LINE ==================== */}
      {sourceContext && (
        <Typography
          variant="caption"
          color="text.disabled"
          display="block"
          sx={{ mt: 1.25 }}
        >
          {sourceContext}
        </Typography>
      )}

      {/* ==================== EXPANDED DETAILS ==================== */}
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Divider sx={{ mt: 1.5, mb: 1.5 }} />
        {signalType === "people" && <PeopleSignalDetail signal={signal} />}
        {signalType === "pain" && <PainSignalDetail signal={signal} />}
        {signalType === "objective" && (
          <ObjectiveSignalDetail signal={signal} />
        )}
        {signalType === "tech-stack" && (
          <TechStackSignalDetail signal={signal} />
        )}
      </Collapse>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

SignalCard.propTypes = {
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    source: PropTypes.string,
    source_display: PropTypes.string,
    signal_category: PropTypes.string,
    signal_category_display: PropTypes.string,
    source_quote: PropTypes.string,
    source_contact: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      job_title: PropTypes.string,
    }),
    source_activity: PropTypes.shape({ id: PropTypes.string }),
    created_at: PropTypes.string,
    // PeopleSignal
    role: PropTypes.string,
    role_display: PropTypes.string,
    influence_level: PropTypes.string,
    influence_level_display: PropTypes.string,
    target_contact: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      job_title: PropTypes.string,
    }),
    notes: PropTypes.string,
    // PainSignal
    summary: PropTypes.string,
    category: PropTypes.string,
    category_display: PropTypes.string,
    pain_level: PropTypes.string,
    pain_level_display: PropTypes.string,
    business_cost: PropTypes.string,
    impact_summary: PropTypes.string,
    // ObjectiveSignal
    goal_level: PropTypes.string,
    goal_level_display: PropTypes.string,
    success_criteria: PropTypes.string,
    measurement_method: PropTypes.string,
    // TechStackSignal
    tech_name: PropTypes.string,
    satisfaction: PropTypes.string,
    satisfaction_display: PropTypes.string,
    usage: PropTypes.string,
    limitations: PropTypes.string,
    workarounds: PropTypes.string,
    integrations: PropTypes.string,
    renewal_date: PropTypes.string,
  }).isRequired,

  /** Signal type — never inferred from the signal object itself */
  signalType: PropTypes.oneOf(["people", "pain", "objective", "tech-stack"])
    .isRequired,

  onValidate: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};
