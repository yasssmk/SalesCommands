// frontend/src/__tests__/_stubs/react-csv.jsx
//
// Test-only stub for `react-csv`, which is imported by the table's CSV export
// button (components/third-party/react-table/CSVExport.jsx) but is not installed
// in the test graph. Aliased in vitest.config.js so the REAL ReusableTable and
// its toolbar/pagination children can render under test — the CSV export itself
// is irrelevant to what we test. Not collected as a suite (no .test suffix).

export function CSVLink({ children }) {
  return <a href="#csv">{children}</a>;
}

export default { CSVLink };
