// frontend/vitest.setup.js
//
// Global test setup — runs before every test file.
//
// Registers @testing-library/jest-dom custom matchers (toBeInTheDocument,
// toHaveTextContent, etc.) so they're available in all test files without
// per-file imports.

import "@testing-library/jest-dom/vitest";

// ---------------------------------------------------------------------------
// Mock strategy for frontend tests
// ---------------------------------------------------------------------------
//
// SWR hooks are mocked directly at the import level using vi.mock(...).
// Axios is not mocked at the network layer — we trust SWR's contract and
// test from the consumer side.
//
// If a future sprint requires HTTP-level realism, introduce MSW (Mock
// Service Worker) at that point.
//
// End-to-end tests are out of scope for the per-sprint test suite —
// reserved for a dedicated test-hardening sprint at project end.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Global mocks for Next.js App Router hooks
// ---------------------------------------------------------------------------
// next/navigation is used across the codebase (useRouter, useParams,
// useSearchParams). We provide sensible defaults here; individual tests
// can override via vi.mocked(...).mockReturnValue({...}).

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  })),
  useParams: vi.fn(() => ({})),
  useSearchParams: vi.fn(() => new URLSearchParams()),
  usePathname: vi.fn(() => "/"),
  redirect: vi.fn(),
  notFound: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Global mock for useAuth
// ---------------------------------------------------------------------------
// Returns a minimal auth context so components that call useAuth() don't
// crash. Tests needing specific auth state can override per-file.

vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({
    tenantId: "test-tenant-id",
    client: { id: "test-client-id" },
    user: { id: "test-user-id", email: "test@example.com" },
    isAuthenticated: true,
  }),
}));
