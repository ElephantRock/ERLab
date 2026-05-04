import "@testing-library/jest-dom/vitest";

/**
 * Global mock for @sentry/react (BATCH-60/TASK-01).
 * Prevents ERR_MODULE_NOT_FOUND in Vitest by providing stub implementations
 * of all Sentry SDK functions used by the codebase.
 * This mock exists ONLY in the test environment and does NOT intercept
 * production code paths.
 */
vi.mock("@sentry/react", () => ({
  init: vi.fn(),
  captureException: vi.fn(),
  captureMessage: vi.fn(),
  withScope: vi.fn((cb) => cb({
    setUser: vi.fn(),
    setTag: vi.fn(),
    setExtra: vi.fn(),
    setLevel: vi.fn(),
  })),
  setUser: vi.fn(),
  setTag: vi.fn(),
  setExtra: vi.fn(),
  setContext: vi.fn(),
  addBreadcrumb: vi.fn(),
  startTransaction: vi.fn(() => ({
    startChild: vi.fn(() => ({
      finish: vi.fn(),
      startChild: vi.fn(),
    })),
    finish: vi.fn(),
    setStatus: vi.fn(),
  setData: vi.fn(),
  })),
  showReportDialog: vi.fn(),
  lastEventId: vi.fn(() => undefined),
  flush: vi.fn(() => Promise.resolve(true)),
  close: vi.fn(() => Promise.resolve(true)),
}));
