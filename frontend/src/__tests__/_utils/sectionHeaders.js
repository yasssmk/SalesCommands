// frontend/src/__tests__/_utils/sectionHeaders.js
//
// The numbered SectionHeaders of a rendered tree — the helper of the C2b
// parity test (EditCompetitorContent.test.jsx), shared (lot 3 / 13, TD-239)
// by the drawer structure tests.
//   sectionHeaders(root) → [{ index, title, el }]
//   sectionTitles(root)  → ["Identity", "Contact", …]
//   sectionOf(root, el)  → the 1-based section `el` sits in (0 = before §1)

export function sectionHeaders(root) {
  return [...root.querySelectorAll(".MuiChip-label")]
    .filter((label) => /^\d+$/.test(label.textContent))
    .map((label) => {
      const row = label.closest(".MuiChip-root").parentElement;
      return { index: label.textContent, title: row.textContent.slice(label.textContent.length), el: row };
    });
}

export const sectionTitles = (root) => sectionHeaders(root).map(({ title }) => title);

export function sectionOf(root, el) {
  const headers = sectionHeaders(root).map((h) => h.el);
  let n = 0;
  headers.forEach((h, i) => {
    if (h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) n = i + 1;
  });
  return n;
}
