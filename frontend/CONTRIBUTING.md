# Frontend Contributing Guide

## Testing

### Framework

**Vitest** + **React Testing Library** (RTL) + **jsdom**.

### Commands

| Command | Usage |
|---|---|
| `npm test` | One-shot run (CI). Exits with code 0/1. |
| `npm run test:watch` | Interactive watch mode (dev). Re-runs on file change. |
| `npm run test:coverage` | One-shot with coverage report. |
| `npm run test:ui` | Browser-based test explorer (`@vitest/ui`). |

### File conventions

- Test files live next to source or under `src/__tests__/`.
- Naming: `ComponentName.test.jsx` or `hookName.test.js`.
- One test file per component/hook.

### Mock strategy

SWR hooks are mocked directly at the import level using `vi.mock(...)`. Axios is not mocked at the network layer — we trust SWR's contract and test from the consumer side.

Global mocks (next/navigation, useAuth) are configured in `vitest.setup.js`. Override per-test as needed via `vi.mocked(...)`.

If a future sprint requires HTTP-level realism, introduce MSW (Mock Service Worker) at that point.

End-to-end tests are out of scope for the per-sprint test suite — reserved for a dedicated test-hardening sprint at project end.

### Coverage expectations per sprint

Every sprint PR must include tests that cover:

1. **Render OK** — component mounts without crash with expected props.
2. **Interactions** — clicks, navigations, form submissions.
3. **Loading / error / empty states** — all parallel states.
