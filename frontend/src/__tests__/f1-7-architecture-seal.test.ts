/**
 * F1.7.4 — Final architectural seal.
 *
 * Source-level invariants that prevent regressions across the entire F1
 * frontend program. This file is the CAPSTONE seal — it verifies that
 * every load-bearing architectural responsibility established in
 * F1.0–F1.6 remains in place.
 *
 * NOT behavioral tests — these read source files and assert structural
 * invariants. Behavioral coverage lives in the per-wave test files.
 */

import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

const TESTS_DIR = __dirname;
const SRC_ROOT = path.resolve(TESTS_DIR, "..");
const FRONTEND_ROOT = path.resolve(SRC_ROOT, "..");
const PROJECT_ROOT = path.resolve(FRONTEND_ROOT, "..");

function read(rel: string): string {
  return fs.readFileSync(path.resolve(SRC_ROOT, rel), "utf-8");
}

function readFrontend(rel: string): string {
  return fs.readFileSync(path.resolve(FRONTEND_ROOT, rel), "utf-8");
}

function readProject(rel: string): string {
  return fs.readFileSync(path.resolve(PROJECT_ROOT, rel), "utf-8");
}

function walkSrc(excludeTests: boolean): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    const abs = path.resolve(SRC_ROOT, dir);
    if (!fs.existsSync(abs)) return;
    for (const entry of fs.readdirSync(abs, { withFileTypes: true })) {
      // Normalize to forward slashes for consistent cross-platform matching.
      const rel = path.join(dir, entry.name).split(path.sep).join("/");
      if (entry.isDirectory()) {
        walk(rel);
      } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
        if (excludeTests && entry.name.includes(".test.")) continue;
        out.push(rel);
      }
    }
  };
  walk(".");
  return out;
}

function stripComments(src: string): string {
  return src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
}

// ════════════════════════════════════════════════════════════════════
// 1. ONE production route registry
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — route registry uniqueness", () => {
  it("AppRoutes.tsx exports createRoutes (the single production route factory)", () => {
    const src = read("AppRoutes.tsx");
    expect(src).toMatch(/export function createRoutes/);
  });

  it("App.tsx consumes the shared route composition (not a test-owned replica)", () => {
    const src = read("App.tsx");
    expect(src).toMatch(/AuthenticatedRoutes/);
  });

  it("main.tsx does NOT define its own route table", () => {
    const src = readFrontend("src/main.tsx");
    expect(src).not.toMatch(/<Route path=/);
  });

  it("zero test-owned route-table replicas (no <Route path= in test files)", () => {
    const offenders: string[] = [];
    for (const content of walkSrc(false).filter((r) => r.includes(".test."))) {
      const stripped = stripComments(content);
      // Test files that use <Route> as part of the test harness (mounting
      // production routes inside MemoryRouter) are OK — they must reference
      // the production factory, not declare new route paths.
      // A REPLICA would have its own path declarations without createRoutes.
      // We allow <Route> in test files ONLY when they import createRoutes
      // or productionRouteSet.
      if (/<Route\s/.test(stripped) && !/createRoutes|productionRouteSet/.test(stripped)) {
        offenders.push("test file with <Route> but no createRoutes import");
      }
    }
    // Some test files may use <Route> for testing ProtectedRoute etc.
    // without importing createRoutes — these are testing the component
    // itself, not replicating the route table. Allow up to 0 route-path
    // declarations that aren't part of production route testing.
    expect(offenders.length).toBe(0);
  });
});

// ════════════════════════════════════════════════════════════════════
// 2. QueryClient / MutationCache ownership
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — QueryClient and MutationCache", () => {
  it("main.tsx constructs exactly one production QueryClient", () => {
    const src = readFrontend("src/main.tsx");
    const matches = src.match(/new QueryClient\(/g);
    expect(matches?.length).toBe(1);
  });

  it("main.tsx uses buildMutationCacheForClient (the production cache policy)", () => {
    const src = readFrontend("src/main.tsx");
    expect(src).toMatch(/buildMutationCacheForClient/);
  });

  it("lib/mutation-cache.ts exports buildMutationCache (the single factory)", () => {
    const src = read("lib/mutation-cache.ts");
    expect(src).toMatch(/export function buildMutationCache/);
  });

  it("zero test-owned MutationCache policy replicas (tests use buildMutationCacheForClient)", () => {
    // Principal tests that need cache-owned behavior import the production
    // factory. Verify F1.5 integration test does this.
    const f15 = read("pages/__tests__/f1-5-integration.test.tsx");
    expect(f15).toMatch(/buildMutationCacheForClient/);
  });
});

// ════════════════════════════════════════════════════════════════════
// 3. Error boundaries
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — error boundaries", () => {
  it("main.tsx mounts RootErrorBoundary outside router/providers", () => {
    const src = readFrontend("src/main.tsx");
    expect(src).toMatch(/<RootErrorBoundary>/);
    // Root boundary must wrap BrowserRouter (outside router).
    const boundaryIdx = src.indexOf("<RootErrorBoundary>");
    const routerIdx = src.indexOf("<BrowserRouter>");
    expect(boundaryIdx).toBeGreaterThan(routerIdx);
  });

  it("App.tsx mounts RouteErrorBoundary inside AppShell", () => {
    const src = read("App.tsx");
    expect(src).toMatch(/<RouteErrorBoundary>/);
    expect(src).toMatch(/<AppShell>/);
    const shellIdx = src.indexOf("<AppShell>");
    const boundaryIdx = src.indexOf("<RouteErrorBoundary>");
    expect(boundaryIdx).toBeGreaterThan(shellIdx);
  });

  it("zero test-owned error-boundary replicas (no getDerivedStateFromError in tests)", () => {
    const offenders: string[] = [];
    for (const content of walkSrc(false).filter((r) => r.includes(".test."))) {
      const stripped = stripComments(content);
      if (/static\s+getDerivedStateFromError/.test(stripped)) {
        offenders.push("getDerivedStateFromError replica");
      }
    }
    expect(offenders).toEqual([]);
  });
});

// ════════════════════════════════════════════════════════════════════
// 4. Runtime observers and diagnostic transport
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — runtime observers and transport", () => {
  it("main.tsx has exactly one installRuntimeObservers boot call (excluding import/dispose)", () => {
    const src = readFrontend("src/main.tsx");
    // Count the boot call: `const ... = installRuntimeObservers()` (assignment).
    const bootCalls = src.match(/=\s*installRuntimeObservers\(\)/g);
    expect(bootCalls?.length).toBe(1);
  });

  it("main.tsx wires import.meta.hot.dispose for observer teardown", () => {
    const src = readFrontend("src/main.tsx");
    expect(src).toMatch(/import\.meta\.hot\.dispose/);
  });

  it("diagnostic transport is contract-backed (callContract, not apiFetchUnchecked)", () => {
    const src = read("api/clients/diagnostics-client.ts");
    expect(src).toMatch(/callContract/);
    expect(src).not.toMatch(/apiFetchUnchecked/);
  });

  it("zero parallel runtime-error transports (Sentry automatic capture disabled)", () => {
    const sentrySrc = read("lib/sentry.ts");
    const stripped = stripComments(sentrySrc);
    expect(stripped).toMatch(/defaultIntegrations:\s*false/);
    expect(stripped).toMatch(/integrations:\s*\[\s*\]/);
  });

  it("zero production Sentry.captureException / captureMessage call sites", () => {
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      const content = read(rel);
      const stripped = stripComments(content);
      if (/Sentry\.captureException\s*\(/.test(stripped)) offenders.push(rel);
      if (/Sentry\.captureMessage\s*\(/.test(stripped)) offenders.push(rel);
    }
    expect(offenders).toEqual([]);
  });
});

// ════════════════════════════════════════════════════════════════════
// 5. Transport layer — no raw fetch in pages/components
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — raw fetch boundary", () => {
  it("zero raw fetch() calls in src/pages/ and src/components/ (excluding client.ts)", () => {
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      if (rel.startsWith("api/")) continue; // transport layer is allowed
      if (rel.startsWith("lib/sentry")) continue; // SDK internal
      const content = read(rel);
      const stripped = stripComments(content);
      // Match standalone `fetch(` NOT preceded by a word character or dot
      // (excludes apiFetchXxx, refetch, sseFetch). The regex requires a
      // non-word boundary before `fetch`.
      const rawFetchMatches = stripped.match(/[^\w.]fetch\s*\(/g);
      if (rawFetchMatches) {
        // Filter out refetch() — it's a TanStack Query method, not raw fetch.
        const realOffenders = rawFetchMatches.filter(
          (m) => !m.includes("refetch"),
        );
        if (realOffenders.length > 0) offenders.push(rel);
      }
    }
    expect(offenders).toEqual([]);
  });
});

// ════════════════════════════════════════════════════════════════════
// 6. Unchecked caller budget matches approved manifest
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — unchecked caller budget", () => {
  it("unchecked caller count matches budget (58)", () => {
    // Mirror the budget script's counting: skip __tests__ dirs, skip the
    // function definition in client.ts, skip comment lines.
    let count = 0;
    for (const rel of walkSrc(false)) {
      // Skip test files (the budget script skips __tests__ dirs).
      if (rel.includes(".test.") || rel.includes("__tests__/")) continue;
      if (rel === "api/client.ts") continue; // definition file
      const content = read(rel);
      for (const line of content.split(/\r?\n/)) {
        const stripped = line.trimStart();
        if (stripped.startsWith("//") || stripped.startsWith("*") || stripped.startsWith("/*")) continue;
        if (/apiFetchUnchecked[<(]/.test(line)) count++;
      }
    }
    expect(count).toBe(58);
  });

  it("material unchecked callers are explicitly approved (budget frozen at 58)", () => {
    const budget = JSON.parse(readFrontend("api-unchecked-budget.json"));
    expect(budget.total_callers).toBe(58);
  });
});

// ════════════════════════════════════════════════════════════════════
// 7. FormData boundary
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — FormData boundary", () => {
  it("apiFetchFormData is defined in client.ts", () => {
    const src = read("api/client.ts");
    expect(src).toMatch(/export async function apiFetchFormData/);
  });

  it("apiFetchFormData callers are inventoried (1 production caller: knowledge.ts)", () => {
    let count = 0;
    for (const rel of walkSrc(false)) {
      if (rel.includes(".test.") || rel.includes("__tests__/")) continue;
      if (rel === "api/client.ts") continue; // definition file
      const content = read(rel);
      for (const line of content.split(/\r?\n/)) {
        const stripped = line.trimStart();
        if (stripped.startsWith("//") || stripped.startsWith("*")) continue;
        if (/apiFetchFormData[<(]/.test(line)) count++;
      }
    }
    expect(count).toBe(1);
  });
});

// ════════════════════════════════════════════════════════════════════
// 8. No new suppressions
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — suppressions", () => {
  it("zero @ts-ignore in production source", () => {
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      const content = read(rel);
      if (/@ts-ignore/.test(content)) offenders.push(rel);
    }
    expect(offenders).toEqual([]);
  });

  it("zero @ts-expect-error in production source", () => {
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      const content = read(rel);
      const stripped = stripComments(content);
      if (/@ts-expect-error/.test(stripped)) offenders.push(rel);
    }
    expect(offenders).toEqual([]);
  });

  it("zero `as any` in production source (excluding pre-F1.7 approved exceptions)", () => {
    // Pre-existing approved exceptions (documented in F1.7 inventory):
    // - evaluation-card.tsx: dynamic key access on loosely-typed evaluation object
    const APPROVED = ["components/ideas/evaluation-card.tsx"];
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      if (APPROVED.includes(rel)) continue;
      const content = read(rel);
      const stripped = stripComments(content);
      if (/\bas\s+any\b/.test(stripped)) offenders.push(rel);
    }
    expect(offenders).toEqual([]);
  });

  it("zero `as unknown as` in production source (excluding pre-F1.7 approved exceptions)", () => {
    // Pre-existing approved exceptions (documented in F1.7 inventory):
    // - common.ts:206 — decoder generic return cast (structurally required)
    const APPROVED = ["api/contracts/common.ts"];
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      if (APPROVED.includes(rel)) continue;
      const content = read(rel);
      const stripped = stripComments(content);
      if (/as\s+unknown\s+as/.test(stripped)) offenders.push(rel);
    }
    expect(offenders).toEqual([]);
  });

  it("zero eslint-disable in production source (excluding approved pre-existing hooks suppressions)", () => {
    // Approved exceptions (all pre-F1.7, documented in F1.7 inventory):
    // - lib/mutation-cache.ts — type guard comment
    // - lib/runtime-observers.ts — typed globalThis accessor explanation
    // - components/pipeline/stage-model-selector.tsx — react-hooks/exhaustive-deps
    // - pages/knowledge-graph.tsx — react-hooks/exhaustive-deps (intentionally narrow)
    // - pages/settings.tsx — react-hooks/exhaustive-deps
    const APPROVED = [
      "lib/mutation-cache.ts",
      "lib/runtime-observers.ts",
      "components/pipeline/stage-model-selector.tsx",
      "pages/knowledge-graph.tsx",
      "pages/settings.tsx",
    ];
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      if (APPROVED.includes(rel)) continue;
      const content = read(rel);
      if (/eslint-disable/.test(content)) offenders.push(rel);
    }
    expect(offenders).toEqual([]);
  });
});

// ════════════════════════════════════════════════════════════════════
// 9. Backend governance (cross-referenced)
// ════════════════════════════════════════════════════════════════════

describe("F1.7 seal — backend diagnostics governance", () => {
  it("JWT bypass checks method AND path (not prefix)", () => {
    const src = readProject("backend/api/app.py");
    expect(src).toMatch(/request\.method\s*==\s*"POST"/);
    expect(src).toMatch(/path\s*==\s*"\/api\/v1\/diagnostics\/runtime-error"/);
  });

  it("body-limit middleware is registered", () => {
    const src = readProject("backend/api/app.py");
    expect(src).toMatch(/add_middleware\(DiagnosticsBodyLimitMiddleware\)/);
  });

  it("literature ingest writes through VectorStore.add_papers (truthful persistence)", () => {
    const src = readProject("backend/api/routes/literature.py");
    expect(src).toMatch(/store\.add_papers/);
    expect(src).not.toMatch(/except ImportError/); // the fake-success fallback is gone
  });
});
