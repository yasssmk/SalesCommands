// frontend/src/components/tree/GenericTreeView.jsx

import PropTypes from 'prop-types';
import { useState, useMemo, useCallback } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

// mui x tree view
import { RichTreeView } from '@mui/x-tree-view/RichTreeView';

// icons
import { DownOutlined, RightOutlined } from '@ant-design/icons';

// ==================== MAIN COMPONENT ====================

function GenericTreeView({
  data,
  selectedId,
  onSelect,
  defaultExpandedIds = [],
  onExpand,
  searchTerm = '',
  filterFunction,
  height = '600px',
  maxHeight = '800px'
}) {
  const theme = useTheme();
  const [expandedIds, setExpandedIds] = useState(defaultExpandedIds);

  // -------- FILTERING --------

  const filteredData = useMemo(() => {
    if (!searchTerm || searchTerm.trim() === '') return data;
    const filter = filterFunction || defaultFilterFunction;
    return filterTree(data, (node) => filter(node, searchTerm));
  }, [data, searchTerm, filterFunction]);

  const autoExpandedIds = useMemo(() => {
    if (!searchTerm || searchTerm.trim() === '') return expandedIds;

    const ids = new Set(expandedIds);

    const addParentIds = (nodes) => {
      (nodes || []).forEach((node) => {
        if (node.children && node.children.length > 0) {
          ids.add(node.id);
          addParentIds(node.children);
        }
      });
    };

    addParentIds(filteredData);
    return Array.from(ids);
  }, [filteredData, searchTerm, expandedIds]);

  // -------- TRANSFORM TO MUI ITEMS --------
  // On ne donne à RichTreeView que { id, label, children }
  // et on garantit que label est une string.

  const treeItems = useMemo(() => {
    const toTreeViewItems = (nodes) =>
      (nodes || []).map((node) => ({
        id: node.id,
        label:
          typeof node.label === 'string'
            ? node.label
            : typeof node.name === 'string'
            ? node.name
            : String(node.label ?? node.name ?? ''),
        children: node.children ? toTreeViewItems(node.children) : undefined
      }));

    return toTreeViewItems(filteredData);
  }, [filteredData]);

  // -------- HANDLERS --------

  const handleSelectChange = useCallback(
    (event, itemId) => {
      if (!itemId) return;
      const node = findNodeById(data, itemId);
      if (node && onSelect) {
        onSelect(itemId, node);
      }
    },
    [data, onSelect]
  );

  const handleExpandedItemsChange = useCallback(
    (event, itemIds) => {
      setExpandedIds(itemIds);
      if (onExpand) onExpand(itemIds);
    },
    [onExpand]
  );

  // -------- EMPTY STATE --------

  if (!treeItems || treeItems.length === 0) {
    return (
      <Box
        sx={{
          height,
          maxHeight,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 3,
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 1
        }}
      >
        <Typography variant="body2" color="text.secondary">
          {searchTerm ? `No results for "${searchTerm}"` : 'No data available'}
        </Typography>
      </Box>
    );
  }

  // -------- RENDER --------

  return (
    <Box
      sx={{
        height,
        maxHeight,
        overflow: 'auto',
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 1,
        p: 1,
        // Style simple et cohérent, sans toucher à l’indentation
        '& .MuiTreeItem-label': {
          ...theme.typography.subtitle1, // Typpgraphie - font
          color: theme.palette.text.secondary // Typpgraphie - Color
        }
      }}
    >
      <RichTreeView
        items={treeItems}
        selectedItems={selectedId}
        onSelectedItemsChange={handleSelectChange}
        expandedItems={autoExpandedIds}
        onExpandedItemsChange={handleExpandedItemsChange}
        itemChildrenIndentation={24} // décalage visuel clair pour les sous-niveaux
        slots={{
          collapseIcon: DownOutlined,
          expandIcon: RightOutlined
        }}
        // getItemLabel doit renvoyer une STRING → on renvoie item.label
        getItemLabel={(item) => item.label}
      />
    </Box>
  );
}

// ==================== UTILITIES ====================

function findNodeById(nodes, id) {
  if (!nodes) return null;
  for (const node of nodes) {
    if (String(node.id) === String(id)) return node;
    if (node.children) {
      const found = findNodeById(node.children, id);
      if (found) return found;
    }
  }
  return null;
}

function defaultFilterFunction(node, searchTerm) {
  return node.name.toLowerCase().includes(searchTerm.toLowerCase());
}

function filterTree(nodes, filterFn) {
  return (nodes || []).reduce((acc, node) => {
    const matches = filterFn(node);
    const filteredChildren = node.children
      ? filterTree(node.children, filterFn)
      : [];

    if (matches || filteredChildren.length > 0) {
      acc.push({ ...node, children: filteredChildren });
    }
    return acc;
  }, []);
}

// ==================== PROP TYPES ====================

GenericTreeView.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      name: PropTypes.string.isRequired,
      children: PropTypes.array
    })
  ).isRequired,
  selectedId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onSelect: PropTypes.func,
  defaultExpandedIds: PropTypes.arrayOf(
    PropTypes.oneOfType([PropTypes.string, PropTypes.number])
  ),
  onExpand: PropTypes.func,
  searchTerm: PropTypes.string,
  filterFunction: PropTypes.func,
  height: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  maxHeight: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
};

export default GenericTreeView;
