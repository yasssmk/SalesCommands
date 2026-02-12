// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepContactsTab.jsx
/**
 * Decision Step Contacts Tab
 *
 * Read-only table of contacts involved in this step.
 * All contacts come from linked activities (all_contacts).
 * Uses ReusableTable with same column pattern as AccountContactsTab.
 *
 * No add/edit/delete — contacts are managed from the Activity module.
 */

'use client';

import { useMemo, useState, useCallback } from 'react';
import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// Project imports
import ReusableTable from 'components/table/Table';

// ==============================|| INFLUENCE LEVEL COLORS ||============================== //

const INFLUENCE_COLORS = {
  DECISION_MAKER: 'success',
  INFLUENCER: 'info',
  CHAMPION: 'primary',
  USER: 'default',
  GATEKEEPER: 'warning',
  BLOCKER: 'error',
  UNKNOWN: 'default'
};

// ==============================|| DECISION STEP CONTACTS TAB ||============================== //

/**
 * @param {Object} step - Decision Step data (contains all_contacts)
 * @param {string} accountId - Account UUID (for navigation)
 */
export default function DecisionStepContactsTab({ step, accountId }) {

  // ==============================|| DATA ||============================== //

  const contacts = useMemo(() => step?.all_contacts || [], [step?.all_contacts]);

  // ==============================|| CLIENT-SIDE SEARCH ||============================== //

  const [search, setSearch] = useState('');

  const filteredContacts = useMemo(() => {
    if (!search) return contacts;
    const lower = search.toLowerCase();
    return contacts.filter((c) => {
      const name = [c.first_name, c.last_name].filter(Boolean).join(' ').toLowerCase();
      const email = (c.email || '').toLowerCase();
      const dept = (c.department_name || '').toLowerCase();
      const job = (c.job_title || '').toLowerCase();
      return name.includes(lower) || email.includes(lower) || dept.includes(lower) || job.includes(lower);
    });
  }, [contacts, search]);

  const handleSearchChange = useCallback((value) => {
    setSearch(value);
  }, []);

  // ==============================|| SORTING (client-side) ||============================== //

  const [sorting, setSorting] = useState([]);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prev) =>
      typeof updaterOrValue === 'function' ? updaterOrValue(prev) : updaterOrValue
    );
  }, []);

  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(
    () => [
      // Name + Job Title
      {
        header: 'Name',
        id: 'full_name',
        accessorFn: (row) => [row.first_name, row.last_name].filter(Boolean).join(' ') || row.email || 'Unknown',
        cell: ({ row }) => {
          const contact = row.original;
          const fullName = [contact.first_name, contact.last_name].filter(Boolean).join(' ');

          return (
            <Stack spacing={0}>
              <Typography variant="subtitle2">
                {fullName || 'Unknown'}
              </Typography>
              {contact.job_title && (
                <Typography variant="caption" color="text.secondary">
                  {contact.job_title}
                </Typography>
              )}
            </Stack>
          );
        }
      },
      // Department
      {
        header: 'Department',
        id: 'department_name',
        accessorKey: 'department_name',
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2">{value}</Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">—</Typography>
          );
        }
      },
      // Email
      {
        header: 'Email',
        id: 'email',
        accessorKey: 'email',
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
              {value}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">—</Typography>
          );
        }
      },
      // Phone
      {
        header: 'Phone',
        id: 'phone_number',
        accessorKey: 'phone_number',
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2">{value}</Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">—</Typography>
          );
        }
      },
      // Influence Level
      {
        header: 'Influence',
        id: 'influence_level',
        accessorKey: 'influence_level',
        cell: ({ row }) => {
          const contact = row.original;
          if (!contact.influence_level || contact.influence_level === 'UNKNOWN') {
            return <Typography variant="body2" color="text.disabled">—</Typography>;
          }
          return (
            <Chip
              label={contact.influence_level_display || contact.influence_level.replace('_', ' ')}
              size="small"
              color={INFLUENCE_COLORS[contact.influence_level] || 'default'}
              variant="light"
            />
          );
        }
      }
    ],
    []
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <ReusableTable
        data={filteredContacts}
        columns={columns}
        loading={false}
        totalCount={filteredContacts.length}
        currentPage={1}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        onSearchChange={handleSearchChange}
        searchPlaceholder={`Search ${contacts.length} contacts...`}
        emptyMessage="No contacts involved"
        emptyDescription="Contacts will appear here automatically when they are added to activities linked to this step."
        showAddButton={false}
        enableImport={false}
      />
    </Box>
  );
}

DecisionStepContactsTab.propTypes = {
  step: PropTypes.object,
  accountId: PropTypes.string
};