// frontend/src/sections/accounts/signals/SignalCard.jsx
/**
 * SignalCard — displays a single signal with its metadata and contextual actions.
 *
 * Actions available per status:
 *   PENDING   → Validate, Reject, Edit, Delete
 *   VALIDATED → Edit, Supersede, Delete
 *   REJECTED  → Delete
 *   MERGED    → (read-only, no actions)
 *
 * The `value` field is a JSONField on the backend — rendered as a string
 * if primitive, or compact JSON if object/array.
 *
 * Each card is self-contained: it receives handlers from SignalList
 * and calls them with (signal, signalType).
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
import EditOutlined from "@ant-design/icons/EditOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import RetweetOutlined from "@ant-design/icons/RetweetOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import UpOutlined from "@ant-design/icons/UpOutlined";

// ==============================|| STATUS CONFIG ||============================== //

/**
 * MUI Chip color + label per SignalStatus value.
 * Covers all backend SignalStatus choices.
 */
const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  VALIDATED: { color: "success", label: "Validated" },
  REJECTED: { color: "error", label: "Rejected" },
  MERGED: { color: "default", label: "Merged" },
};

/**
 * MUI Chip color per signal type.
 */
const TYPE_CONFIG = {
  qualification: { color: "info", label: "Qualification" },
  "tech-stack": { color: "primary", label: "Tech Stack" },
};

// ==============================|| VALUE RENDERER ||============================== //

/**
 * Safely render a JSONField value.
 *
 * - null / undefined → em dash
 * - primitive (string, number, boolean) → string cast
 * - object / array → compact JSON (max 200 chars, truncated)
 *
 * @param {*} value
 * @returns {string}
 */
function renderValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value || "—";
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";

  try {
    const str = JSON.stringify(value, null, 0);
    return str.length > 200 ? `${str.slice(0, 200)}…` : str;
  } catch {
    return String(value);
  }
}

// ==============================|| META ITEM ||============================== //

/**
 * Small labelled metadata item used in the card footer.
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

// ==============================|| SIGNAL CARD ||============================== //

/**
 * SignalCard
 *
 * @param {Object}   signal      - Signal data from BaseSignalListSerializer
 *                                 (+ .signalType tag added by AccountSignalsTab)
 * @param {string}   signalType  - 'qualification' | 'tech-stack'
 * @param {Function} onValidate  - (signal, signalType) => void
 * @param {Function} onReject    - (signal, signalType) => void
 * @param {Function} onEdit      - (signal, signalType) => void
 * @param {Function} onSupersede - (signal, signalType) => void
 * @param {Function} onDelete    - (signal, signalType) => void
 */
export default function SignalCard({
  signal,
  signalType,
  onValidate,
  onReject,
  onEdit,
  onSupersede,
  onDelete,
}) {
  // ==============================|| LOCAL STATE ||============================== //

  /** Controls the overflow action menu (Edit / Supersede / Delete) */
  const [menuAnchor, setMenuAnchor] = useState(null);
  /** Controls the collapsible extra-info section */
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
  const isRejected = status === "REJECTED";
  const isMerged = status === "MERGED";
  const isSuperseded = Boolean(signal.is_superseded);

  /** Contact display name */
  const contactName = signal.source_contact
    ? `${signal.source_contact.first_name} ${signal.source_contact.last_name}`.trim()
    : null;

  /** Department display name */
  const deptName = signal.source_department?.name ?? null;

  /** Formatted creation date */
  const createdDate = signal.created_at
    ? new Date(signal.created_at).toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : null;

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

  const handleSupersede = useCallback(() => {
    handleMenuClose();
    onSupersede(signal, signalType);
  }, [handleMenuClose, onSupersede, signal, signalType]);

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
        borderColor: isSuperseded
          ? "divider"
          : isPending
            ? "warning.light"
            : "divider",
        borderRadius: 1.5,
        p: 2,
        opacity: isMerged || isSuperseded ? 0.6 : 1,
        bgcolor: "background.paper",
        transition: "border-color 0.15s, opacity 0.15s",
        "&:hover": {
          borderColor: "primary.light",
        },
      }}
    >
      {/* ==================== HEADER ROW ==================== */}
      <Stack direction="row" spacing={1} alignItems="flex-start">
        {/* Left: badges */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1 }}
        >
          {/* Signal type badge */}
          <Chip
            label={typeCfg.label}
            color={typeCfg.color}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />

          {/* Status badge */}
          <Chip
            label={statusCfg.label}
            color={statusCfg.color}
            size="small"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />

          {/* Superseded indicator */}
          {isSuperseded && (
            <Chip
              label="Superseded"
              size="small"
              variant="outlined"
              sx={{
                fontSize: "0.68rem",
                height: 20,
                borderColor: "text.disabled",
                color: "text.disabled",
              }}
            />
          )}

          {/* Field name */}
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            {signal.field_name_display || signal.field_name}
          </Typography>

          {/* Tech stack tool name */}
          {signalType === "tech-stack" && signal.tech_name && (
            <Typography variant="caption" color="text.secondary">
              · {signal.tech_name}
            </Typography>
          )}

          {/* Signal category */}
          {signal.signal_category_display && (
            <Chip
              label={signal.signal_category_display}
              size="small"
              variant="outlined"
              color="default"
              sx={{ fontSize: "0.65rem", height: 18 }}
            />
          )}
        </Stack>

        {/* Right: quick actions + overflow menu */}
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

          {/* Overflow menu — available unless MERGED */}
          {!isMerged && (
            <>
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
                {/* Edit — PENDING and VALIDATED */}
                {(isPending || isValidated) && (
                  <MenuItem onClick={handleEdit} dense>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <EditOutlined style={{ fontSize: 14 }} />
                      <span>Edit</span>
                    </Stack>
                  </MenuItem>
                )}

                {/* Supersede — VALIDATED only */}
                {isValidated && (
                  <MenuItem onClick={handleSupersede} dense>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <RetweetOutlined style={{ fontSize: 14 }} />
                      <span>Supersede</span>
                    </Stack>
                  </MenuItem>
                )}

                {/* Delete — always (except MERGED handled by !isMerged above) */}
                <MenuItem
                  onClick={handleDelete}
                  dense
                  sx={{ color: "error.main" }}
                >
                  <Stack direction="row" spacing={1} alignItems="center">
                    <DeleteOutlined style={{ fontSize: 14 }} />
                    <span>Delete</span>
                  </Stack>
                </MenuItem>
              </Menu>
            </>
          )}

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

      {/* ==================== VALUE ROW ==================== */}
      <Box sx={{ mt: 1.25, mb: 0.5 }}>
        <Typography
          variant="body2"
          sx={{
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            lineHeight: 1.6,
          }}
        >
          {renderValue(signal.value)}
        </Typography>
      </Box>

      {/* ==================== META FOOTER ==================== */}
      <Stack
        direction="row"
        spacing={2}
        flexWrap="wrap"
        useFlexGap
        sx={{ mt: 1 }}
      >
        {contactName && <MetaItem label="Contact" value={contactName} />}
        {deptName && <MetaItem label="Department" value={deptName} />}
        {signal.source_display && (
          <MetaItem label="Source" value={signal.source_display} />
        )}
        {signal.confidence !== null && signal.confidence !== undefined && (
          <MetaItem
            label="Confidence"
            value={`${Math.round(signal.confidence * 100)}%`}
          />
        )}
        {signal.confirmation_count > 0 && (
          <MetaItem label="Confirmed" value={`${signal.confirmation_count}×`} />
        )}
        {createdDate && <MetaItem label="Added" value={createdDate} />}
      </Stack>

      {/* ==================== EXPANDED DETAILS ==================== */}
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Divider sx={{ mt: 1.5, mb: 1.5 }} />

        <Stack spacing={1}>
          {/* Source quote */}
          {signal.source_quote && (
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
                &ldquo;{signal.source_quote}&rdquo;
              </Typography>
            </Box>
          )}

          {/* Original value — shown only when signal has been LLM-modified */}
          {signal.original_value !== undefined &&
            signal.original_value !== null && (
              <Box>
                <Typography
                  variant="caption"
                  color="text.disabled"
                  display="block"
                  gutterBottom
                >
                  Original value (before edit)
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {renderValue(signal.original_value)}
                </Typography>
              </Box>
            )}

          {/* Inferred flag */}
          {signal.is_inferred && (
            <Typography variant="caption" color="text.disabled">
              This value was inferred from context, not stated explicitly.
            </Typography>
          )}
        </Stack>
      </Collapse>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

SignalCard.propTypes = {
  /** Signal data from BaseSignalListSerializer + .signalType tag */
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    field_name: PropTypes.string.isRequired,
    field_name_display: PropTypes.string,
    value: PropTypes.any,
    original_value: PropTypes.any,
    signal_category: PropTypes.string,
    signal_category_display: PropTypes.string,
    status: PropTypes.string.isRequired,
    source_display: PropTypes.string,
    confidence: PropTypes.number,
    is_inferred: PropTypes.bool,
    is_superseded: PropTypes.bool,
    confirmation_count: PropTypes.number,
    source_quote: PropTypes.string,
    tech_name: PropTypes.string,
    source_contact: PropTypes.shape({
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      job_title: PropTypes.string,
    }),
    source_department: PropTypes.shape({
      name: PropTypes.string,
    }),
    created_at: PropTypes.string,
  }).isRequired,

  /** 'qualification' | 'tech-stack' */
  signalType: PropTypes.oneOf(["qualification", "tech-stack"]).isRequired,

  onValidate: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onSupersede: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};
