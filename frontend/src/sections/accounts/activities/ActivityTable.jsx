// frontend/src/sections/accounts/activities/ActivityTable.jsx
/**
 * Activity Table Component
 * 
 * Reusable table for displaying activities.
 * Used in Account Workspace, Territory Workspace, and Decision Step.
 */

'use client';

import PropTypes from 'prop-types';
import { useMemo, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// project imports
import IconButton from 'components/@extended/IconButton';
import ReusableTable from 'components/table/Table';
import {
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS,
  ACTIVITY_OUTCOME_LABELS,
  ACTIVITY_OUTCOME_COLORS
} from 'api/accounts/activities';

// utils
import { formatDateTime, formatDateOnly } from 'config/formatters';

// assets
import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import LinkedinOutlined from '@ant-design/icons/LinkedinOutlined';
import QuestionCircleOutlined from '@ant-design/icons/QuestionCircleOutlined';

// ==============================|| SORT FIELD MAPPING ||============================== //

const COLUMN_TO_BACKEND_FIELD = {
  title: 'title',
  activity_type: 'activity_type',
  status: 'status',
  scheduled_date: 'scheduled_date',
  due_date: 'due_date',
  owner: 'owner__last_name',
  account: 'account__company_name',
  updated_at: 'updated_at'
};

// ==============================|| TYPE ICONS ||============================== //

const TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined
};

// ==============================|| ACTIVITY TABLE ||============================== //

/**
 * ActivityTable Component
 * 
 * @param {Object} props
 * @param {Array} props.activities - Activities data array
 * @param {boolean} props.loading - Loading state
 * @param {Error} props.error - Error object
 * @param {number} props.totalCount - Total activities count
 * @param {number} props.page - Current page (1-indexed)
 * @param {number} props.pageSize - Page size
 * @param {Array} props.sorting - Sorting state
 * @param {Function} props.onPaginationChange - Pagination handler
 * @param {Function} props.onSearchChange - Search handler
 * @param {Function} props.onSortingChange - Sorting handler
 * @param {Function} props.onAdd - Add activity handler
 * @param {Function} props.onEdit - Edit activity handler
 * @param {Function} props.onDelete - Delete activity handler
 * @param {Function} props.onComplete - Complete activity handler
 * @param {Function} props.onCancel - Cancel activity handler
 * @param {boolean} props.showAccount - Show account column (default: false)
 * @param {boolean} props.showActions - Show action buttons (default: true)
 * @param {string} props.emptyMessage - Empty state message
 * @param {string} props.emptyDescription - Empty state description
 */
export default function ActivityTable({
  activities = [],
  loading = false,
  error = null,
  totalCount = 0,
  page = 1,
  pageSize = 25,
  sorting = [],
  onPaginationChange,
  onSearchChange,
  onSortingChange,
  onAdd,
  onEdit,
  onDelete,
  onComplete,
  onCancel,
  showAccount = false,
  showActions = true,
  emptyMessage = 'No activities found',
  emptyDescription = 'Create your first activity to start tracking your sales actions'
}) {
  
  // ==============================|| HANDLERS ||============================== //
  
  const handleEdit = useCallback((activity) => {
    if (onEdit) onEdit(activity);
  }, [onEdit]);
  
  const handleDelete = useCallback((activity) => {
    if (onDelete) onDelete(activity);
  }, [onDelete]);
  
  const handleComplete = useCallback((activity) => {
    if (onComplete) onComplete(activity);
  }, [onComplete]);
  
  const handleCancel = useCallback((activity) => {
    if (onCancel) onCancel(activity);
  }, [onCancel]);

  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(() => {
    const baseColumns = [
      // Type Icon + Title
      {
        id: 'title',
        header: 'Activity',
        accessorKey: 'title',
        cell: ({ row }) => {
          const type = row.original.activity_type;
          const TypeIcon = TYPE_ICONS[type] || QuestionCircleOutlined;
          
          return (
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <Tooltip title={ACTIVITY_TYPE_LABELS[type] || type}>
                <Box
                  sx={{
                    width: 32,
                    height: 32,
                    borderRadius: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: 'action.hover'
                  }}
                >
                  <TypeIcon style={{ fontSize: 16 }} />
                </Box>
              </Tooltip>
              <Box>
                <Typography variant="subtitle2" noWrap sx={{ maxWidth: 200 }}>
                  {row.original.title}
                </Typography>
                {row.original.call_to_action && (
                  <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 200 }}>
                    {row.original.call_to_action}
                  </Typography>
                )}
              </Box>
            </Stack>
          );
        }
      },
      // Status
      {
        id: 'status',
        header: 'Status',
        accessorKey: 'status',
        cell: ({ row }) => {
          const status = row.original.status;
          return (
            <Chip
              label={ACTIVITY_STATUS_LABELS[status] || status}
              color={ACTIVITY_STATUS_COLORS[status] || 'default'}
              size="small"
              variant="light"
            />
          );
        }
      },
      // Scheduled Date
      {
        id: 'scheduled_date',
        header: 'Scheduled',
        accessorKey: 'scheduled_date',
        cell: ({ row }) => {
          const date = row.original.scheduled_date;
          const time = row.original.scheduled_time;
          
          if (!date) {
            return <Typography variant="body2" color="text.secondary">—</Typography>;
          }
          
          return (
            <Typography variant="body2">
              {formatDateOnly(date)}
              {time && (
                <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                  {time.slice(0, 5)}
                </Typography>
              )}
            </Typography>
          );
        }
      },
      // Due Date
      {
        id: 'due_date',
        header: 'Due',
        accessorKey: 'due_date',
        cell: ({ row }) => {
          const date = row.original.due_date;
          const isOverdue = row.original.is_overdue;
          
          if (!date) {
            return <Typography variant="body2" color="text.secondary">—</Typography>;
          }
          
          return (
            <Typography 
              variant="body2" 
              color={isOverdue ? 'error.main' : 'text.primary'}
              fontWeight={isOverdue ? 500 : 400}
            >
              {formatDateOnly(date)}
            </Typography>
          );
        }
      },
      // Owner
      {
        id: 'owner',
        header: 'Owner',
        accessorKey: 'owner',
        cell: ({ row }) => {
          const owner = row.original.owner;
          if (!owner) return <Typography variant="body2" color="text.secondary">—</Typography>;
          
          const name = owner.full_name || `${owner.first_name || ''} ${owner.last_name || ''}`.trim();
          return (
            <Typography variant="body2" noWrap sx={{ maxWidth: 120 }}>
              {name || owner.email}
            </Typography>
          );
        }
      },
      // Outcome (only for completed)
      {
        id: 'outcome',
        header: 'Outcome',
        accessorKey: 'outcome',
        cell: ({ row }) => {
          const outcome = row.original.outcome;
          const status = row.original.status;
          
          if (status !== 'COMPLETED' || !outcome) {
            return <Typography variant="body2" color="text.secondary">—</Typography>;
          }
          
          return (
            <Chip
              label={ACTIVITY_OUTCOME_LABELS[outcome] || outcome}
              color={ACTIVITY_OUTCOME_COLORS[outcome] || 'default'}
              size="small"
              variant="outlined"
            />
          );
        }
      }
    ];

    // Add Account column if needed
    if (showAccount) {
      baseColumns.splice(1, 0, {
        id: 'account',
        header: 'Account',
        accessorKey: 'account',
        cell: ({ row }) => {
          const account = row.original.account;
          if (!account) return <Typography variant="body2" color="text.secondary">—</Typography>;
          
          return (
            <Typography variant="body2" noWrap sx={{ maxWidth: 150 }}>
              {account.company_name}
            </Typography>
          );
        }
      });
    }

    // Add Actions column if needed
    if (showActions) {
      baseColumns.push({
        id: 'actions',
        header: '',
        cell: ({ row }) => {
          const activity = row.original;
          const isCompleted = activity.status === 'COMPLETED';
          const isCancelled = activity.status === 'CANCELLED';
          const canComplete = !isCompleted && !isCancelled;
          const canCancel = !isCompleted && !isCancelled;
          
          return (
            <Stack direction="row" spacing={0.5} justifyContent="flex-end">
              {/* Complete */}
              {canComplete && onComplete && (
                <Tooltip title="Mark Complete">
                  <IconButton
                    size="small"
                    color="success"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleComplete(activity);
                    }}
                  >
                    <CheckCircleOutlined />
                  </IconButton>
                </Tooltip>
              )}
              
              {/* Cancel */}
              {canCancel && onCancel && (
                <Tooltip title="Cancel">
                  <IconButton
                    size="small"
                    color="warning"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCancel(activity);
                    }}
                  >
                    <CloseCircleOutlined />
                  </IconButton>
                </Tooltip>
              )}
              
              {/* Edit */}
              {onEdit && (
                <Tooltip title="Edit">
                  <IconButton
                    size="small"
                    color="secondary"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEdit(activity);
                    }}
                  >
                    <EditOutlined />
                  </IconButton>
                </Tooltip>
              )}
              
              {/* Delete */}
              {onDelete && (
                <Tooltip title="Delete">
                  <IconButton
                    size="small"
                    color="secondary"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(activity);
                    }}
                  >
                    <DeleteOutlined />
                  </IconButton>
                </Tooltip>
              )}
            </Stack>
          );
        }
      });
    }

    return baseColumns;
  }, [showAccount, showActions, onEdit, onDelete, onComplete, onCancel, handleEdit, handleDelete, handleComplete, handleCancel]);

  // ==============================|| RENDER ||============================== //

  return (
    <ReusableTable
      data={activities}
      columns={columns}
      loading={loading}
      error={error}
      modalToggler={onAdd}
      totalCount={totalCount}
      currentPage={page}
      initialPageSize={pageSize}
      onPaginationChange={onPaginationChange}
      onSearchChange={onSearchChange}
      sorting={sorting}
      onSortingChange={onSortingChange}
      addButtonLabel="Add Activity"
      addButtonTooltip="Create new activity"
      searchPlaceholder={`Search ${totalCount} activities...`}
      exportFilename="activities-list.csv"
      emptyMessage={emptyMessage}
      emptyDescription={emptyDescription}
      enableImport={false}
    />
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityTable.propTypes = {
  activities: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.object,
  totalCount: PropTypes.number,
  page: PropTypes.number,
  pageSize: PropTypes.number,
  sorting: PropTypes.array,
  onPaginationChange: PropTypes.func,
  onSearchChange: PropTypes.func,
  onSortingChange: PropTypes.func,
  onAdd: PropTypes.func,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
  onComplete: PropTypes.func,
  onCancel: PropTypes.func,
  showAccount: PropTypes.bool,
  showActions: PropTypes.bool,
  emptyMessage: PropTypes.string,
  emptyDescription: PropTypes.string
};

// ==============================|| EXPORT COLUMN MAPPING ||============================== //

export { COLUMN_TO_BACKEND_FIELD };