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
  maxHeight = '800px',
  parentField // optional: name of the field that holds the parent (e.g. "parent_team")
}) {
  const theme = useTheme();
  const [expandedIds, setExpandedIds] = useState(defaultExpandedIds);

  // -------- FILTERING --------

  // If parentField is provided, we build a tree from a flat list.
  const structuredData = useMemo(() => {
    if (!data) return [];
    if (!parentField) return data;
    return buildTreeFromFlat(data, parentField);
  }, [data, parentField]);

  const filteredData = useMemo(() => {
    if (!searchTerm || searchTerm.trim() === '') return structuredData;
    const filter = filterFunction || defaultFilterFunction;
    return filterTree(structuredData, (node) => filter(node, searchTerm));
  }, [structuredData, searchTerm, filterFunction]);

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
      const node = findNodeById(structuredData, itemId);
      if (node && onSelect) {
        onSelect(itemId, node);
      }
    },
    [structuredData, onSelect]
  );

  const handleExpandedItemsChange = useCallback(
    (event, itemIds) => {
      setExpandedIds(itemIds);
      if (onExpand) onExpand(itemIds);
    },
    [onExpand]
  );

  // ---------- UTILITIES ---------

  function buildTreeFromFlat(nodes, parentField) {
  if (!nodes || nodes.length === 0) return [];

  // Clone nodes and initialize children
  const map = new Map();
  nodes.forEach((node) => {
    map.set(node.id, { ...node, children: [] });
  });

  const roots = [];

  map.forEach((node) => {
    // parentField can point to an object (e.g. { id, name }) or a raw id
    const parentValue = parentField ? node[parentField] : null;
    const parentId =
      parentValue && typeof parentValue === 'object'
        ? parentValue.id
        : parentValue;

    if (parentId && map.has(parentId)) {
      map.get(parentId).children.push(node);
    } else {
      roots.push(node);
    }
  });

  return roots;
}


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
  maxHeight: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  // Optional field name used to derive hierarchy from a flat list (e.g. "parent_team")
  parentField: PropTypes.string
};


export default GenericTreeView;
