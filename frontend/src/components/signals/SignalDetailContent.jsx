// frontend/src/components/signals/SignalDetailContent.jsx
//
// The single-signal detail CONTENT — header row (leading/trailing action slots
// + type/status chips), body (summary, validated-by, per-type detail block via
// the shared B1.2 blocks, source quote, origin provenance) and the lifecycle
// actions (validate / reject / edit / reopen).
//
// This is the drawer body extracted from SignalQuickDrawer so it can be reused
// as the "replacement" content inside another themed MUI Drawer shell (the
// cluster drawer's signal view) WITHOUT stacking a second drawer. Both
// SignalQuickDrawer and SignalClusterDetailDrawer render this same content.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { CloseOutlined, LinkOutlined } from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import SignalStatusChip from "components/chips/SignalStatusChip";
import StatusPill from "components/chips/StatusPill";
import ContactInline from "components/signals/ContactInline";
import { SIGNAL_STATUS_PILL } from "components/signals/signalStatusPill";
import { getSignalTypeLabel } from "utils/signalTypes";
import DrawerFieldRow from "components/display/DrawerFieldRow";
import DrawerSection from "components/display/DrawerSection";
import SectionHeader from "components/display/SectionHeader";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import { getMissingFields } from "sections/activities/signals/signalValidationRules";
import SignalIncompleteAlert from "components/signals/SignalIncompleteAlert";
import {
  getTechSummary,
  getContact,
  formatContact,
  getNextStepSummary,
  formatSuggestedContacts,
  formatTargetDepartments,
} from "sections/activities/signals/utils/signalDisplay";

// Shared per-type detail blocks — the single rendering of each type's
// type-specific fields (B1.2).
import ImpactDetailBlock from "components/signals/detail/ImpactDetailBlock";
import ObjectiveDetailBlock from "components/signals/detail/ObjectiveDetailBlock";
import TechDetailBlock from "components/signals/detail/TechDetailBlock";
import PainDetailBlock from "components/signals/detail/PainDetailBlock";

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function getSummary(signal, signalType) {
  if (signalType === "tech-stack") return getTechSummary(signal).name;
  if (signalType === "next-steps") return getNextStepSummary(signal);
  return signal.summary || "—";
}

// ==============================|| SOURCE QUOTE BLOCK ||============================== //

function SourceQuoteBlock({ quote }) {
  if (!quote) return null;
  return (
    <Box
      sx={{
        p: 1.5,
        bgcolor: "grey.50",
        borderRadius: 1,
        borderLeft: 3,
        borderColor: "primary.main",
      }}
    >
      <Typography variant="body2" sx={{ fontStyle: "italic" }} color="text.secondary">
        &ldquo;{quote}&rdquo;
      </Typography>
    </Box>
  );
}

SourceQuoteBlock.propTypes = { quote: PropTypes.string };

// ==============================|| TYPE-SPECIFIC DETAIL SECTIONS ||============================== //

function PainDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
        {/* Multi-department scope (M2M): all target_departments, joined. */}
        <DrawerFieldRow label="Department" value={formatTargetDepartments(signal)} />
        <DrawerFieldRow label="Category" value={signal.signal_category_display} />
      </DrawerSection>
      <PainDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
PainDetails.propTypes = { signal: PropTypes.object.isRequired };

function ObjectiveDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
      </DrawerSection>
      <ObjectiveDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
ObjectiveDetails.propTypes = { signal: PropTypes.object.isRequired };

function ImpactDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
        {/* Multi-department scope (M2M): all target_departments, joined. */}
        <DrawerFieldRow label="Department" value={formatTargetDepartments(signal)} />
      </DrawerSection>
      <ImpactDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
      </DrawerSection>
    </>
  );
}
ImpactDetails.propTypes = { signal: PropTypes.object.isRequired };

function TechStackDetails({ signal }) {
  const techInfo = getTechSummary(signal);
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="IDENTITY">
        <DrawerFieldRow label="Tool">
          <Typography variant="body2">{techInfo.name}</Typography>
        </DrawerFieldRow>
        <DrawerFieldRow label="Mentioned by" value={contactName} />
      </DrawerSection>
      <TechDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
TechStackDetails.propTypes = { signal: PropTypes.object.isRequired };

function BlockerDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <DrawerSection title="CONTEXT">
      <DrawerFieldRow label="Raised by" value={contactName} />
    </DrawerSection>
  );
}
BlockerDetails.propTypes = { signal: PropTypes.object.isRequired };

function NextStepDetails({ signal }) {
  const suggestedContacts = formatSuggestedContacts(signal.suggested_contacts);
  const linked = signal.linked_activity;
  return (
    <>
      <DrawerSection title="SUGGESTION">
        <DrawerFieldRow label="Type" value={signal.suggested_activity_type_display} />
        <DrawerFieldRow label="Due date" value={formatDate(signal.suggested_due_date)} />
        {signal.suggested_objective && (
          <DrawerFieldRow label="Objective" value={signal.suggested_objective} />
        )}
        {suggestedContacts && (
          <DrawerFieldRow label="Contacts" value={suggestedContacts} />
        )}
      </DrawerSection>
      {linked && (
        <DrawerSection title="LINKED ACTIVITY">
          <DrawerFieldRow label="Title" value={linked.title} />
          <DrawerFieldRow label="Type" value={linked.activity_type_display} />
          <DrawerFieldRow label="Status" value={linked.status_display} />
          <DrawerFieldRow label="Date" value={formatDate(linked.scheduled_date)} />
        </DrawerSection>
      )}
    </>
  );
}
NextStepDetails.propTypes = { signal: PropTypes.object.isRequired };

function PeopleDetails({ signal }) {
  const targetContact = signal.target_contact ? formatContact(signal.target_contact) : null;
  const targetDept = signal.target_department?.name;
  return (
    <>
      <DrawerSection title="ROLE">
        <DrawerFieldRow label="Role" value={signal.role_display} />
        <DrawerFieldRow label="Influence" value={signal.influence_display} />
        <DrawerFieldRow label="Contact" value={targetContact} />
        <DrawerFieldRow label="Department" value={targetDept} />
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
PeopleDetails.propTypes = { signal: PropTypes.object.isRequired };

function ConstraintDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Rigidity" value={signal.rigidity_display} />
        {/* Multi-department scope (M2M): all target_departments, joined —
            the singular target_department FK was dropped for Constraint. */}
        <DrawerFieldRow label="Department" value={formatTargetDepartments(signal)} />
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Raised by" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
ConstraintDetails.propTypes = { signal: PropTypes.object.isRequired };

// Competitor drawer: only the competitor identity is type-specific — summary,
// source quote and provenance are rendered by the type-agnostic sections.
function CompetitorDetails({ signal }) {
  return (
    <DrawerSection title="COMPETITOR">
      <DrawerFieldRow label="Name" value={signal.competitor_name} />
    </DrawerSection>
  );
}
CompetitorDetails.propTypes = { signal: PropTypes.object.isRequired };

function renderDetails(signal, signalType) {
  switch (signalType) {
    case "pain": return <PainDetails signal={signal} />;
    case "objective": return <ObjectiveDetails signal={signal} />;
    case "impact": return <ImpactDetails signal={signal} />;
    case "tech-stack": return <TechStackDetails signal={signal} />;
    case "blockers": return <BlockerDetails signal={signal} />;
    case "next-steps": return <NextStepDetails signal={signal} />;
    case "people": return <PeopleDetails signal={signal} />;
    case "constraints": return <ConstraintDetails signal={signal} />;
    case "competitors": return <CompetitorDetails signal={signal} />;
    default: return null;
  }
}

// ==============================|| PROVENANCE ||============================== //

function ProvenanceSection({ signal, onOpenActivity }) {
  const contacts = signal.source_context?.contacts ?? [];
  const activityId = signal.source_context?.activity?.id ?? null;
  if (contacts.length === 0 && !activityId) return null;

  return (
    <DrawerSection title="ORIGIN">
      {contacts.length > 0 && (
        <DrawerFieldRow label={contacts.length > 1 ? "Contacts" : "Contact"}>
          <Stack spacing={0.25}>
            {contacts.map((c) => (
              <ContactInline key={c.id} contact={c} variant="body2" />
            ))}
          </Stack>
        </DrawerFieldRow>
      )}
      {activityId && onOpenActivity && (
        <Button
          size="small"
          variant="text"
          startIcon={<LinkOutlined style={{ fontSize: 13 }} />}
          onClick={() => onOpenActivity(activityId)}
          sx={{ mt: 0.5, px: 0 }}
        >
          View origin activity
        </Button>
      )}
    </DrawerSection>
  );
}
ProvenanceSection.propTypes = {
  signal: PropTypes.object.isRequired,
  onOpenActivity: PropTypes.func,
};

// ==============================|| OBJECTIVE DETAIL VIEW (SIG-5e) ||============================== //
//
// The Objective detail is rebuilt as a READ mirror of EditObjectiveContent: the
// same 5 SectionHeaders + subtitles + the Domain × Dimension recap, values shown
// (not editable). No type/status chips — the type is the coque title, the status
// is muted text. Origin (section 5) is detail-only, with a "View origin activity"
// link shown ONLY when the origin activity differs from the current one.

// Numbered section badge — info palette role (mirror of EditObjectiveContent).
// A read-flow field: a discreet muted label ABOVE the value (not a rigid
// label/value column) — reads like a page, not a form.
function ReadField({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <Box sx={{ mb: 1.25 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
        {label}
      </Typography>
      <Typography variant="body2" color="text.primary" sx={{ whiteSpace: "pre-line" }}>
        {value}
      </Typography>
    </Box>
  );
}
ReadField.propTypes = { label: PropTypes.string, value: PropTypes.node };

// A label/value ROW: muted label on the LEFT, value on the RIGHT (2-column,
// value right-aligned). Used for scope + metrics, where each field is a short
// scalar read as "Label ………… Value".
function ReadRow({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        gap: 2,
        mb: 1,
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        color="text.primary"
        sx={{ textAlign: "right", whiteSpace: "pre-line" }}
      >
        {value}
      </Typography>
    </Box>
  );
}
ReadRow.propTypes = { label: PropTypes.string, value: PropTypes.node };

// Read scope as a label/value pair (mirrors the pill's Company / Department).
function objectiveScopeRow(signal) {
  if (signal.scope_level === "DEPARTMENT") {
    return { label: "Department", value: signal.target_department?.name || "—" };
  }
  if (signal.scope_level === "PERSONAL") {
    const c = signal.target_contact;
    const name = c ? `${c.first_name ?? ""} ${c.last_name ?? ""}`.trim() : "";
    return { label: "Contact", value: name || "—" };
  }
  return { label: "Scope", value: "Company" };
}

function ObjectiveDetailView({
  signal,
  onValidate,
  onReject,
  onEdit,
  onReopen,
  onOpenActivity,
  onClose,
  headerInCoque,
  isLocked,
  currentActivityId,
}) {
  const isPending = signal.status === "PENDING";
  const missingFields = isPending ? getMissingFields(signal, "objective") : [];
  const validateDisabled = missingFields.length > 0;

  const axisPreview =
    signal.what_display && signal.dimension_display
      ? `${signal.what_display} × ${signal.dimension_display}`
      : null;
  const canonicalPreview =
    signal.what && signal.dimension ? `objective:${signal.what}:${signal.dimension}` : null;

  const contacts = signal.source_context?.contacts ?? [];
  const originActivityId = signal.source_context?.activity?.id ?? null;
  // View-origin link only when the origin activity is NOT the one we're viewing.
  const showOriginLink = Boolean(
    originActivityId && onOpenActivity && originActivityId !== currentActivityId,
  );
  const hasMetrics = Boolean(signal.success_criteria || signal.target_date || signal.notes);

  return (
    <>
      <Box sx={{ px: 2.5, py: 2, flex: 1, overflow: "auto" }}>
        {/* In-content header (title · [status pill + close ×]) — used only when
            the coque does NOT own the header (headerInCoque=false; DC/Account).
            On the Activity surface the coque renders title + status pill + × in
            its own header (UI-1), so this block is suppressed. */}
        {!headerInCoque && (
          <Box
            data-testid="objective-detail-header"
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1,
              mb: 2,
            }}
          >
            <Typography variant="h3" fontWeight="bold" data-testid="objective-detail-title">
              {getSignalTypeLabel("objective")}
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <StatusPill status={signal.status} statusMap={SIGNAL_STATUS_PILL} />
              {onClose && (
                <IconButton size="small" onClick={onClose} aria-label="Close drawer">
                  <CloseOutlined style={{ fontSize: 14 }} />
                </IconButton>
              )}
            </Stack>
          </Box>
        )}

        {/* UI-6 — one container box grounds the detail body, mirroring the other
            drawers' framed content box (DrawerContentLayout's drawer-content-box:
            background.default + radius.lg + hairline). The Goal box keeps its
            surface.level1 tint (UI-5) so the highlighted block still reads above
            this container. Optional chaining keeps it safe in the theme-less
            cluster-drawer render contexts. */}
        <Box
          data-testid="objective-detail-container"
          sx={{
            backgroundColor: "background.default",
            borderRadius: (theme) => theme.aphoriQ?.radius?.lg && `${theme.aphoriQ.radius.lg}px`,
            border: (theme) =>
              theme.aphoriQ?.border &&
              `${theme.aphoriQ.border.width.hairline}px solid ${theme.aphoriQ.border.color}`,
            p: 2,
          }}
        >
        <SignalIncompleteAlert missingFields={missingFields} />

        {signal.validated_by && (
          <ReadField
            label="Validated by"
            value={`${signal.validated_by.first_name || ""} ${signal.validated_by.last_name || ""}`.trim()}
          />
        )}
        {signal.validated_at && (
          <ReadField label="Validated at" value={formatDateTime(signal.validated_at)} />
        )}

        {/* Section 1 — Goal. The summary is the headline (prominent, no label);
            the Domain × Dimension are conveyed by the recap only. Detail exposes
            values — no instruction subtitles (those live in the edit). */}
        {/* One enclosing Goal box: summary (top) · short centered separator ·
            axis recap (bottom). A single surface tint, no inner accent border. */}
        <SectionHeader index={1} title="Goal" sx={{ mb: 1 }} />
        {(signal.summary || axisPreview) && (
          <Box
            data-testid="objective-goal-box"
            sx={{
              my: 1,
              px: 1.5,
              py: 1.25,
              bgcolor: (theme) => theme.aphoriQ?.surface?.level1,
              borderRadius: (theme) => theme.aphoriQ?.radius?.md && `${theme.aphoriQ.radius.md}px`,
            }}
          >
            {signal.summary && (
              <Typography
                data-testid="objective-summary-box"
                variant="body1"
                fontWeight={500}
                color="text.primary"
                sx={{ whiteSpace: "pre-line" }}
              >
                {signal.summary}
              </Typography>
            )}
            {signal.summary && axisPreview && (
              <Divider
                data-testid="objective-goal-separator"
                sx={{ width: "40%", mx: "auto", my: 1.5 }}
              />
            )}
            {axisPreview && (
              <>
                <Typography variant="caption" color="text.secondary">
                  This is a{" "}
                  <Box component="span" sx={{ fontWeight: 600, color: "text.primary" }}>
                    {axisPreview}
                  </Box>{" "}
                  goal
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  display="block"
                  sx={{ fontFamily: "monospace", mt: 0.25 }}
                >
                  canonical_key: {canonicalPreview}
                </Typography>
              </>
            )}
          </Box>
        )}

        <Divider sx={{ my: 2 }} />

        {/* Section 2 — Scope, as a label/value row (value right). */}
        <SectionHeader index={2} title="Scope" sx={{ mb: 1 }} />
        <ReadRow {...objectiveScopeRow(signal)} />

        <Divider sx={{ my: 2 }} />

        {/* Section 3 — Metrics (one discreet line when empty). */}
        <SectionHeader index={3} title="Metrics" sx={{ mb: 1 }} />
        {hasMetrics ? (
          <>
            <ReadRow label="Success criteria" value={signal.success_criteria} />
            <ReadRow label="Target date" value={formatDate(signal.target_date)} />
            <ReadRow label="Notes" value={signal.notes} />
          </>
        ) : (
          <Typography variant="body2" color="text.disabled" sx={{ fontStyle: "italic", my: 1 }}>
            No metrics defined
          </Typography>
        )}

        <Divider sx={{ my: 2 }} />

        {/* Section 4 — Source: the quote, who said it, and (conditionally) a link
            to the origin activity. Merges the former Source quote + Origin. */}
        <SectionHeader index={4} title="Source" sx={{ mb: 1 }} />
        {signal.source_quote ? (
          <SourceQuoteBlock quote={signal.source_quote} />
        ) : (
          <Typography variant="body2" color="text.disabled" sx={{ fontStyle: "italic" }}>
            No source quote
          </Typography>
        )}
        {contacts.length > 0 && (
          <Box sx={{ mt: 1.25 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              {contacts.length > 1 ? "Contacts" : "Contact"}
            </Typography>
            <Stack spacing={0.25}>
              {contacts.map((c) => (
                <ContactInline key={c.id} contact={c} variant="body2" />
              ))}
            </Stack>
          </Box>
        )}
        {showOriginLink && (
          <Button
            size="small"
            variant="text"
            startIcon={<LinkOutlined style={{ fontSize: 13 }} />}
            onClick={() => onOpenActivity(originActivityId)}
            sx={{ mt: 0.5, px: 0 }}
          >
            View origin activity
          </Button>
        )}
        </Box>
      </Box>

      <Divider />

      {/* Actions — the shared read-signal bar (rule 6) via DrawerContentLayout:
          Edit (neutre) · Reject (error) · Validate (success) · Reopen. */}
      <Box sx={{ px: 2.5, py: 2 }}>
        <DrawerContentLayout
          readActions={{
            onEdit: () => onEdit?.(signal, "objective"),
            onReject: () => onReject?.(signal, "objective"),
            onValidate: () => onValidate?.(signal, "objective"),
            onReopen: () => onReopen?.(signal, "objective"),
            status: signal.status,
            isLocked,
            validateDisabled,
          }}
        />
      </Box>
    </>
  );
}
ObjectiveDetailView.propTypes = {
  signal: PropTypes.object.isRequired,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
  onOpenActivity: PropTypes.func,
  /** When provided, renders the close (×) inside the detail header (the coque
      suppresses its own cross). Absent → no in-header close (DC/Account). */
  onClose: PropTypes.func,
  /** When true, the coque owns the header (title + status pill + ×) — the
      in-content header is suppressed. Absent/false → in-content header. */
  headerInCoque: PropTypes.bool,
  isLocked: PropTypes.bool,
  currentActivityId: PropTypes.string,
};

// ==============================|| SIGNAL DETAIL CONTENT ||============================== //

/**
 * @param {node} leadingAction   Rendered before the chips (e.g. a Back button).
 * @param {node} trailingAction  Rendered at the far right (e.g. a Close button).
 */
export default function SignalDetailContent({
  signal,
  signalType,
  onValidate,
  onReject,
  onEdit,
  onReopen,
  onOpenActivity,
  onClose,
  headerInCoque,
  isLocked,
  currentActivityId,
  leadingAction,
  trailingAction,
}) {
  if (!signal) return null;

  // SIG-5e — Objective gets the new read-mirror layout (other types unchanged).
  if (signalType === "objective") {
    return (
      <ObjectiveDetailView
        signal={signal}
        onValidate={onValidate}
        onReject={onReject}
        onEdit={onEdit}
        onReopen={onReopen}
        onOpenActivity={onOpenActivity}
        onClose={onClose}
        headerInCoque={headerInCoque}
        isLocked={isLocked}
        currentActivityId={currentActivityId}
      />
    );
  }

  const isPending = signal.status === "PENDING";
  const missingFields = isPending ? getMissingFields(signal, signalType) : [];
  const validateDisabled = missingFields.length > 0;

  return (
    <>
      {/* Header — leading action (back) · chips · trailing action (close) */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2.5,
          py: 2,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
          {leadingAction}
          <SignalTypeChip signalType={signalType} size="small" />
          <SignalStatusChip status={signal.status} size="small" />
        </Stack>
        {trailingAction}
      </Box>

      <Divider />

      {/* Body */}
      <Box sx={{ px: 2.5, py: 2, flex: 1, overflow: "auto" }}>
        <SignalIncompleteAlert missingFields={missingFields} />

        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {getSummary(signal, signalType)}
        </Typography>

        {signal.validated_by && (
          <DrawerFieldRow
            label="Validated by"
            value={`${signal.validated_by.first_name || ""} ${signal.validated_by.last_name || ""}`.trim()}
          />
        )}
        {signal.validated_at && (
          <DrawerFieldRow label="Validated at" value={formatDateTime(signal.validated_at)} />
        )}
        {(signal.validated_by || signal.validated_at) && <Box sx={{ mb: 1.5 }} />}

        {renderDetails(signal, signalType)}

        {signal.source_quote && (
          <DrawerSection title="SOURCE QUOTE">
            <SourceQuoteBlock quote={signal.source_quote} />
          </DrawerSection>
        )}

        <ProvenanceSection signal={signal} onOpenActivity={onOpenActivity} />
      </Box>

      <Divider />

      {/* Actions — shared read-signal bar (rule 6) via DrawerContentLayout. */}
      <Box sx={{ px: 2.5, py: 2 }}>
        <DrawerContentLayout
          readActions={{
            onEdit: () => onEdit?.(signal, signalType),
            onReject: () => onReject?.(signal, signalType),
            onValidate: () => onValidate?.(signal, signalType),
            onReopen: () => onReopen?.(signal, signalType),
            status: signal.status,
            isLocked,
            validateDisabled,
          }}
        />
      </Box>
    </>
  );
}

SignalDetailContent.propTypes = {
  signal: PropTypes.object,
  signalType: PropTypes.string,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
  onOpenActivity: PropTypes.func,
  /** Objective detail only: when set, renders the close (×) in the detail
      header (the Activity coque suppresses its own cross). */
  onClose: PropTypes.func,
  /** Objective detail only: when true, the coque owns the header — the
      in-content title + pill + × are suppressed. */
  headerInCoque: PropTypes.bool,
  isLocked: PropTypes.bool,
  /** The activity currently being viewed — used to hide the "View origin
      activity" link when the signal's origin IS that activity. Optional;
      absent on DC/Account surfaces (link always shown there). */
  currentActivityId: PropTypes.string,
  leadingAction: PropTypes.node,
  trailingAction: PropTypes.node,
};
