// frontend/src/__tests__/_stubs/dnd-kit-core.jsx
//
// Test-only stub for `@dnd-kit/core`, imported by the table's DraggableRow
// (re-exported from the react-table barrel but never rendered by ReusableTable).
// Not installed in the test graph; aliased in vitest.config.js so the barrel
// resolves and the real ReusableTable can mount. Not collected as a suite.

export const useDraggable = () => ({
  attributes: {},
  listeners: {},
  setNodeRef: () => {},
  transform: null,
  isDragging: false,
});

export const useDroppable = () => ({ setNodeRef: () => {}, isOver: false });

export default { useDraggable, useDroppable };
