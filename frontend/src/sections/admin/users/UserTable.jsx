// // frontend/src/sections/admin/users/UserTable.jsx
// import PropTypes from 'prop-types';
// import React, { Fragment, useMemo, useState, useEffect, useCallback } from 'react';
// import { useSWRConfig } from 'swr';

// // material-ui
// import { alpha, useTheme } from '@mui/material/styles';
// import useMediaQuery from '@mui/material/useMediaQuery';
// import Box from '@mui/material/Box';
// import Chip from '@mui/material/Chip';
// import Divider from '@mui/material/Divider';
// import Stack from '@mui/material/Stack';
// import Table from '@mui/material/Table';
// import TableBody from '@mui/material/TableBody';
// import TableCell from '@mui/material/TableCell';
// import TableContainer from '@mui/material/TableContainer';
// import TableHead from '@mui/material/TableHead';
// import TableRow from '@mui/material/TableRow';
// import Tooltip from '@mui/material/Tooltip';
// import Typography from '@mui/material/Typography';
// import Skeleton from '@mui/material/Skeleton';
// import Button from '@mui/material/Button';
// import Alert from '@mui/material/Alert';
// import AlertTitle from '@mui/material/AlertTitle';
// import WarningOutlined from '@ant-design/icons/WarningOutlined';
// import ReloadOutlined from '@ant-design/icons/ReloadOutlined';

// // third-party
// import {
//   flexRender,
//   getCoreRowModel,
//   getSortedRowModel,
//   getPaginationRowModel,
//   getFilteredRowModel,
//   getExpandedRowModel,
//   useReactTable
// } from '@tanstack/react-table';

// // project-import
// import MainCard from 'components/MainCard';
// import ScrollX from 'components/ScrollX';

// import { TableHeaderActions, DebouncedInput, HeaderSort, RowSelection, SelectColumnSorting, TablePagination } from 'components/third-party/react-table';
// import ExpandingUserDetail from './ExpandingUserDetail';
// import { safeGet } from 'utils/safeHelpers'

// // utils
// import { getErrorDisplayInfo } from 'utils/errorMessages';
// import { displayErrorSnackbar } from 'utils/displayError'; 
// import { useRetryCountdown } from 'hooks/useRetryCountdown';

// // assets
// import PlusOutlined from '@ant-design/icons/PlusOutlined';
// import IconButton from 'components/@extended/IconButton';

// // ==============================|| ERROR DISPLAY COMPONENT ||============================== //

// /**
//  * Affichage erreur avec support countdown 429
//  */
// function ErrorDisplay({ error, onRetry, isRetrying }) {
//   const errorInfo = getErrorDisplayInfo(error);

//    const { 
//     severity = 'error', 
//     message = 'An error occurred', 
//     status = 0, 
//     title = 'Error',
//     isRetryable = false 
//   } = safeGet(errorInfo, {
//     severity: 'error',
//     message: 'An error occurred',
//     status: 0,
//     title: 'Error',
//     isRetryable: false
//   });
  
//   // ✅ Hook countdown pour les 429
//   const secondsLeft = useRetryCountdown(error);

//   // ✅ Message avec countdown si 429
//   const errorMessage = (() => {
//     // Cas 429 avec countdown actif
//     if (status === 429 && secondsLeft !== null && secondsLeft > 0) {
//       return (
//         <Fragment>
//           {message}
//           <Box component="span" sx={{ display: 'block', mt: 1.5, fontWeight: 600, color: 'info.main' }}>
//             🕐 Automatic retry in <strong>{secondsLeft}s</strong> - Please wait
//           </Box>
//         </Fragment>
//       );
//     }
    
//     // Cas 429 countdown terminé (en attente du retry)
//     if (status === 429) {
//       return (
//         <Fragment>
//           {message}
//           <Box component="span" sx={{ display: 'block', mt: 1.5, fontStyle: 'italic', opacity: 0.7 }}>
//             Retrying automatically...
//           </Box>
//         </Fragment>
//       );
//     }
    
//     // Autres erreurs
//     return message;
//   })();

//   return (
//     <TableRow>
//       <TableCell colSpan={100} sx={{ py: 3 }}>
//         <Alert
//           severity={errorInfo.severity}
//           icon={<WarningOutlined style={{ fontSize: 24 }} />}
//           action={
//              isRetryable && status !== 429 && (
//               <Button
//                 color="inherit"
//                 size="small"
//                 onClick={onRetry}
//                 disabled={isRetrying}
//                 startIcon={<ReloadOutlined spin={isRetrying} />}
//               >
//                 {isRetrying ? 'Retrying...' : 'Retry Now'}
//               </Button>
//             )
//           }
//         >
//           <AlertTitle sx={{ fontWeight: 600 }}>{errorInfo.title}</AlertTitle>
//           <Typography variant="body2">{errorMessage}</Typography>
//         </Alert>
//       </TableCell>
//     </TableRow>
//   );
// }

// ErrorDisplay.propTypes = {
//   error: PropTypes.object,
//   onRetry: PropTypes.func.isRequired,
//   isRetrying: PropTypes.bool
// };

// // ==============================|| REACT TABLE ||============================== //

// function ReactTable({ 
//   data, 
//   columns, 
//   loading, 
//   error, 
//   swrKey, 
//   modalToggler, 
//   selectedCount, 
//   selectedRows, 
//   currentPage = 1,
//   onPaginationChange,
//   onSearchChange, 
//   totalCount,
//   onEdit,
//   onDelete,
//   initialPageSize = 10,
//   onImport,
//   sorting,              
//   onSortingChange  
// }) {

//   const theme = useTheme();
//   const matchDownSM = useMediaQuery(theme.breakpoints.down('sm'));
//   const { mutate } = useSWRConfig();

//   const [globalFilter, setGlobalFilter] = useState('');
//   const [isRetrying, setIsRetrying] = useState(false);

//   // ✅ Calculer pageIndex depuis currentPage (1-indexed → 0-indexed)
//   const pageIndex = useMemo(() => {
//     return Math.max(0, currentPage - 1);
//   }, [currentPage]);

//   const pageSize = useMemo(() => {
//     const n = Number(initialPageSize);
//     if (!n || n <= 0) return 10;
//     return Math.min(n, 100);  // ✅ Cap à 100
//   }, [initialPageSize]);

//   const pageCount = useMemo(() => {
//     return Math.ceil((totalCount || 0) / pageSize);
//   }, [totalCount, pageSize]);

//   useEffect(() => {
//     if (onSearchChange) {
//       onSearchChange(globalFilter);
//     }
//   }, [globalFilter, onSearchChange]);

//   // useEffect(() => {
//   //   if (error) {
//   //     displayErrorSnackbar(error);
//   //   }
//   // }, [error]);

//   // ✅ HANDLERS PERSONNALISÉS qui communiquent directement avec le parent
//   // Au lieu d'utiliser les méthodes TanStack (setPageIndex, setPageSize)
//   const handlePageIndexChange = useCallback((newPageIndex) => {
//     if (onPaginationChange) {
//       onPaginationChange({
//         page: newPageIndex + 1,  // Convert 0-indexed to 1-indexed
//         pageSize: Number(initialPageSize) || 10
//       });
//     }
//   }, [onPaginationChange, initialPageSize]);

//   const handlePageSizeChange = useCallback((newPageSize) => {
//     if (onPaginationChange) {
//       onPaginationChange({
//         page: 1,  // Reset to first page when changing page size
//         pageSize: newPageSize
//       });
//     }
//   }, [onPaginationChange]);

//   const table = useReactTable({
//     data,
//     columns,
//     pageCount,
//     state: {
//       sorting,
//       globalFilter,
//       pagination: {
//         pageIndex: pageIndex,
//         pageSize: pageSize
//       }
//     },
//     manualPagination: true,
//     manualFiltering: true,
//     manualSorting: true,              
//     onSortingChange: onSortingChange,
//     onGlobalFilterChange: setGlobalFilter,
//     onPaginationChange: () => {
//     },
//     getRowCanExpand: () => true,
//     getRowId: (row) => String(row.id),
//     getCoreRowModel: getCoreRowModel(),
//     getSortedRowModel: getSortedRowModel(),
//     getExpandedRowModel: getExpandedRowModel(),
//     debugTable: false
//   });

//   const backColor = alpha(theme.palette.primary.lighter, 0.1);

//   const handleRetry = async () => {
//     if (!swrKey || isRetrying) return;

//     setIsRetrying(true);
//     try {
//       await mutate(swrKey);
//     } catch (err) {
//       console.error('Retry failed:', err);
//     } finally {
//       setTimeout(() => setIsRetrying(false), 500);
//     }
//   };

//   const exportData = useMemo(() => {
//     if (!selectedRows || selectedRows.size === 0) {
//       return data;
//     }
//     return data.filter(row => selectedRows.has(row.id));
//   }, [data, selectedRows]);

//   const headers = [];
//   table.getVisibleFlatColumns().forEach((column) => {
//     if (column.columnDef.accessorKey) {
//       headers.push({
//         label: column.columnDef.header,
//         key: column.columnDef.accessorKey
//       });
//     }
//   });

//   return (
//     <MainCard content={false}>
//       <Stack
//         direction={{ xs: 'column', sm: 'row' }}
//         spacing={2}
//         alignItems="center"
//         justifyContent="space-between"
//         sx={{ padding: 2, ...(matchDownSM && { '& .MuiOutlinedInput-root, & .MuiFormControl-root': { width: '100%' } }) }}
//       >
//         <DebouncedInput
//           value={globalFilter ?? ''}
//           onFilterChange={(value) => setGlobalFilter(String(value))}
//           placeholder={loading ? 'Loading...' : `Search ${totalCount} records...`}
//           disabled={loading || !!error}
//         />

//         <Stack direction="row" alignItems="center" spacing={2} sx={{  width: { xs: '100%', sm: 'auto' } }}>
//           <SelectColumnSorting 
//             {...{ 
//               getState: table.getState, 
//               getAllColumns: table.getAllColumns, 
//               setSorting: onSortingChange  
//             }} 
//             disabled={loading || !!error} 
//           />
//           <Stack direction="row" spacing={2} alignItems="center" >
//           {matchDownSM ? (
//             <Tooltip title="Add User">
//               <IconButton color="primary" variant="contained" onClick={modalToggler} disabled={loading || !!error}>
//                 <PlusOutlined />
//               </IconButton>
//             </Tooltip>
//           ) : (
//             <Button variant="contained" startIcon={<PlusOutlined />} onClick={modalToggler} disabled={loading || !!error}>
//               Add User
//             </Button>
//           )}
//           <TableHeaderActions 
//               selectedRowCount={selectedCount || 0}    
//               onEdit={() => { if (onEdit) onEdit(); }} 
//               onDelete={() => { if (onDelete) onDelete(); }} 
//               onImport={onImport}
//               exportData={exportData}                  
//               exportHeaders={headers}                  
//               exportFilename="users-list.csv"
//             />
//           </Stack>
//         </Stack>
//       </Stack>

//       <ScrollX>
//         <Stack>
//         <RowSelection selected={selectedCount || 0} />
//           <>
//             <TableContainer>
//               <Table>
//                 <TableHead>
//                   {table.getHeaderGroups().map((headerGroup) => (
//                     <TableRow key={headerGroup.id}>
//                       {headerGroup.headers.map((header) => {
//                         if (header.column.columnDef.meta !== undefined && header.column.getCanSort()) {
//                           Object.assign(header.column.columnDef.meta, {
//                             className: header.column.columnDef.meta.className + ' cursor-pointer prevent-select'
//                           });
//                         }
//                         return (
//                           <TableCell
//                             key={header.id}
//                             {...header.column.columnDef.meta}
//                             onClick={header.column.getToggleSortingHandler()}
//                             {...(header.column.getCanSort() &&
//                               header.column.columnDef.meta === undefined && {
//                                 className: 'cursor-pointer prevent-select'
//                               })}
//                           >
//                             {header.isPlaceholder ? null : (
//                               <Stack direction="row" spacing={1} alignItems="center">
//                                 <Box>{flexRender(header.column.columnDef.header, header.getContext())}</Box>
//                                 {header.column.getCanSort() && <HeaderSort column={header.column} />}
//                               </Stack>
//                             )}
//                           </TableCell>
//                         );
//                       })}
//                     </TableRow>
//                   ))}
//                 </TableHead>
//                 <TableBody>
//                   {loading ? (
//                     Array.from({ length: Math.max(1, Math.min(initialPageSize ?? 10, 100)) 
//                       }).map((_, index) => (
//                       <TableRow key={index}>
//                         {columns.map((_, colIndex) => (
//                           <TableCell key={colIndex}>
//                             <Skeleton animation="wave" />
//                           </TableCell>
//                         ))}
//                       </TableRow>
//                     ))
//                   ) : error ? (
//                     <ErrorDisplay error={error} onRetry={handleRetry} isRetrying={isRetrying} />
//                   ) : data.length === 0 ? (
//                     <TableRow>
//                       <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
//                         <Stack spacing={1} alignItems="center">
//                           <Typography variant="h6" color="text.secondary">
//                             No users found
//                           </Typography>
//                           <Typography variant="body2" color="text.secondary">
//                             {globalFilter 
//                               ? `No results for "${globalFilter}"`
//                               : 'Start by adding your first user to the system'
//                             }
//                           </Typography>
//                         </Stack>
//                       </TableCell>
//                     </TableRow>
//                   ) : (
//                     table.getRowModel().rows.map((row) => (
//                       <Fragment key={row.id}>
//                         <TableRow>
//                           {row.getVisibleCells().map((cell) => (
//                             <TableCell key={cell.id} {...cell.column.columnDef.meta}>
//                               {flexRender(cell.column.columnDef.cell, cell.getContext())}
//                             </TableCell>
//                           ))}
//                         </TableRow>
//                         {row.getIsExpanded() && (
//                           <TableRow sx={{ bgcolor: backColor, '&:hover': { bgcolor: `${backColor} !important` } }}>
//                             <TableCell colSpan={row.getVisibleCells().length}>
//                               <ExpandingUserDetail data={row.original} />
//                             </TableCell>
//                           </TableRow>
//                         )}
//                       </Fragment>
//                     ))
//                   )}
//                 </TableBody>
//               </Table>
//             </TableContainer>
//             <>
//               <Divider />
//               <Box sx={{ p: 2 }}>
//                 <TablePagination
//                   {...{
//                     // ✅ NE PLUS passer setPageIndex/setPageSize de TanStack
//                     // À la place, passer nos handlers personnalisés
//                     setPageSize: handlePageSizeChange,
//                     setPageIndex: handlePageIndexChange,
//                     getState: table.getState,
//                     getPageCount: table.getPageCount,
//                     initialPageSize,
//                     disabled: loading || !!error
//                   }}
//                 />
//               </Box>
//             </>
//           </>
//         </Stack>
//       </ScrollX>
//     </MainCard>
//   );
// }

// ReactTable.propTypes = {
//   data: PropTypes.array,
//   columns: PropTypes.array,
//   loading: PropTypes.bool,
//   error: PropTypes.object,
//   swrKey: PropTypes.any,
//   modalToggler: PropTypes.func,
//   selectedCount: PropTypes.number,
//   selectedRows: PropTypes.instanceOf(Set),
//   currentPage: PropTypes.number,
//   onPaginationChange: PropTypes.func,
//   onSearchChange: PropTypes.func,
//   totalCount: PropTypes.number,
//   initialPageSize: PropTypes.number,
//   onImport: PropTypes.func,
//   onEdit: PropTypes.func,
//   onDelete: PropTypes.func,
//   sorting: PropTypes.array,           
//   onSortingChange: PropTypes.func 
// };

// // ==============================|| USER TABLE ||============================== //

// const UserTable = React.memo(function UserTable({ 
//   data, 
//   columns, 
//   loading, 
//   error, 
//   swrKey, 
//   modalToggler,
//   totalCount = 0,
//   currentPage = 1,
//   onPaginationChange,      
//   onSearchChange,          
//   selectedCount,           
//   selectedRows,
//   onImport,
//   onEdit,
//   onDelete, 
//   initialPageSize = 10,
//   sorting,                  
//   onSortingChange            
// }) {
//   return (
//     <ReactTable 
//       {...{ 
//         data, 
//         columns, 
//         loading, 
//         error, 
//         swrKey, 
//         modalToggler,
//         totalCount,
//         currentPage,
//         onPaginationChange,
//         onSearchChange,
//         selectedCount,
//         selectedRows,
//         initialPageSize,
//         onImport,
//         onEdit,
//         onDelete,
//         sorting,                  
//         onSortingChange 
//       }} 
//     />
//   );
// });

// UserTable.propTypes = {
//   data: PropTypes.array,
//   columns: PropTypes.array,
//   loading: PropTypes.bool,
//   error: PropTypes.object,
//   swrKey: PropTypes.any,
//   modalToggler: PropTypes.func,
//   selectedCount: PropTypes.number,
//   selectedRows: PropTypes.instanceOf(Set),   
//   totalCount: PropTypes.number,
//   currentPage: PropTypes.number,
//   initialPageSize: PropTypes.number,
//   onPaginationChange: PropTypes.func,
//   onSearchChange: PropTypes.func,
//   onImport: PropTypes.func,
//   onEdit: PropTypes.func,
//   onDelete: PropTypes.func,
//   sorting: PropTypes.array,           
//   onSortingChange: PropTypes.func   
// };

// export default UserTable;