// frontend/src/sections/accounts/decision-cycles/hooks/useDecisionStepEdit.js
/**
 * useDecisionStepEdit — Shared hook for step field editing
 *
 * Centralizes all step edit operations to avoid duplication between
 * DecisionStepDetail (modal) and DecisionStepOverviewTab (workspace).
 *
 * Both consumers pass the same { step, accountId, onUpdate } and get
 * back identical handler signatures + options data for dropdowns.
 *
 * @param {Object} options
 * @param {Object} options.step        - Step data object (must have .id and .cycle)
 * @param {string} options.accountId   - Account UUID (for fetching contacts)
 * @param {Function} options.onUpdate  - Callback after successful update (e.g. mutateStep)
 * @returns {Object}
 */

'use client';

import { useState, useCallback, useMemo } from 'react';

// API
import {
  updateDecisionStep
} from 'api/accounts/decisionCycles';
import { useGetContactChoices, useGetContacts } from 'api/businessData/contacts';

// Utils
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| USE DECISION STEP EDIT ||============================== //

export function useDecisionStepEdit({ step, accountId, onUpdate }) {
  const [saving, setSaving] = useState(false);

  // Derived IDs (stable across renders)
  const stepId = step?.id;
  const cycleId = step?.cycle_id || step?.cycle;

  // ==============================|| DATA FETCHING — OPTIONS ||============================== //

  // Departments for EditableMultiSelect
  const { standardDepartments = [], choicesLoading: deptLoading } = useGetContactChoices();

  // Contacts for this account
  const { contacts = [], contactsLoading } = useGetContacts({
    pageSize: 100,
    filters: { account: accountId }
  });

  // Transform departments for EditableMultiSelect
  const departmentOptions = useMemo(
    () =>
      standardDepartments.map((d) => ({
        id: d.value || d.id,
        name: d.label || d.name || d.display_name
      })),
    [standardDepartments]
  );

  // Transform contacts for EditableMultiSelect
  const contactOptions = useMemo(
    () =>
      contacts.map((c) => ({
        id: c.id,
        name: `${c.first_name || ''} ${c.last_name || ''}`.trim() || c.email || 'Unknown'
      })),
    [contacts]
  );

  // ==============================|| HANDLERS ||============================== //

  /**
   * Save a single scalar field.
   * @param {string} fieldKey - Backend field name
   * @param {*} newValue      - New value
   * @returns {Promise<boolean>} success
   */
  const handleSaveField = useCallback(
    async (fieldKey, newValue) => {
      if (!stepId) return false;
      setSaving(true);

      try {
        const payload = { [fieldKey]: newValue };
        const result = await updateDecisionStep(stepId, payload, cycleId);

        if (result.success) {
          displaySuccessSnackbar('Step updated');
          onUpdate?.(result.data);
          return true;
        } else {
          displayErrorSnackbar({
            message: result.error || 'Failed to update step',
            status: result.status
          });
          return false;
        }
      } catch (err) {
        displayErrorSnackbar({
          message: err?.message || 'An unexpected error occurred',
          status: 500
        });
        return false;
      } finally {
        setSaving(false);
      }
    },
    [stepId, cycleId, onUpdate]
  );

  /**
   * Save multi-select fields (departments, contacts).
   * @param {string} fieldKey - Backend field name (e.g. 'department_ids', 'contact_ids')
   * @param {string[]} newIds - Array of UUIDs
   * @returns {Promise<boolean>} success
   */
  const handleSaveMultiSelect = useCallback(
    async (fieldKey, newIds) => {
      if (!stepId) return false;
      setSaving(true);

      try {
        const payload = { [fieldKey]: newIds };
        const result = await updateDecisionStep(stepId, payload, cycleId);

        if (result.success) {
          displaySuccessSnackbar('Step updated');
          onUpdate?.(result.data);
          return true;
        } else {
          displayErrorSnackbar({
            message: result.error || 'Failed to update step',
            status: result.status
          });
          return false;
        }
      } catch (err) {
        displayErrorSnackbar({
          message: err?.message || 'An unexpected error occurred',
          status: 500
        });
        return false;
      } finally {
        setSaving(false);
      }
    },
    [stepId, cycleId, onUpdate]
  );

  /**
   * Update expected_end date (from DatePicker — dayjs object).
   * @param {Object|string} newDate - dayjs object or ISO string
   * @returns {Promise<boolean>} success
   */
  const handleExpectedEndChange = useCallback(
    async (newDate) => {
      if (!newDate) return false;
      const formatted = typeof newDate === 'string' ? newDate : newDate.format('YYYY-MM-DD');
      return handleSaveField('expected_end', formatted);
    },
    [handleSaveField]
  );

  /**
   * Save date and time together (scheduled_date + scheduled_time).
   * Used by DecisionStepDetail modal's EditableDateTime.
   * @param {string} newDate - YYYY-MM-DD
   * @param {string} newTime - HH:mm:ss
   * @returns {Promise<boolean>} success
   */
  const handleSaveDateTime = useCallback(
    async (newDate, newTime) => {
      if (!stepId) return false;
      setSaving(true);

      try {
        const payload = {
          scheduled_date: newDate,
          scheduled_time: newTime
        };
        const result = await updateDecisionStep(stepId, payload, cycleId);

        if (result.success) {
          displaySuccessSnackbar('Schedule updated');
          onUpdate?.(result.data);
          return true;
        } else {
          displayErrorSnackbar({
            message: result.error || 'Failed to update schedule',
            status: result.status
          });
          return false;
        }
      } catch (err) {
        displayErrorSnackbar({
          message: err?.message || 'An unexpected error occurred',
          status: 500
        });
        return false;
      } finally {
        setSaving(false);
      }
    },
    [stepId, cycleId, onUpdate]
  );

  /**
   * Save manager notes.
   * @param {string} notes - New notes content
   * @returns {Promise<boolean>} success
   */
  const handleSaveManagerNotes = useCallback(
    async (notes) => {
      return handleSaveField('manager_notes', notes);
    },
    [handleSaveField]
  );

  /**
   * Delete (clear) manager notes.
   * @returns {Promise<boolean>} success
   */
  const handleDeleteManagerNotes = useCallback(
    async () => {
      return handleSaveField('manager_notes', '');
    },
    [handleSaveField]
  );

  // ==============================|| RETURN ||============================== //

  return {
    // State
    saving,

    // Field handlers (all async, return boolean success)
    handleSaveField,
    handleSaveMultiSelect,
    handleExpectedEndChange,
    handleSaveDateTime,
    handleSaveManagerNotes,
    handleDeleteManagerNotes,

    // Options data (for dropdowns)
    departmentOptions,
    contactOptions,
    deptLoading,
    contactsLoading
  };
}