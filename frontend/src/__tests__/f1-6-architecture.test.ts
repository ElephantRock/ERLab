/**
 * F1.6.4 — architectural seal for runtime error observability.
 *
 * Source-level invariants that prevent regressions in the observability
 * architecture. These are NOT behavioral tests — they read source files
 * and assert structural invariants.
 */

import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

// __dirname is frontend/src/__tests__ — resolve upward.
const TESTS_DIR = __dirname;                       // .../frontend/src/__tests__
const SRC_ROOT = path.resolve(TESTS_DIR, "..");    // .../frontend/src
const FRONTEND_ROOT = path.resolve(SRC_ROOT, "..");// .../frontend
const PROJECT_ROOT = path.resolve(FRONTEND_ROOT, ".."); // repo root

function readSrc(rel: string): string {
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
      const rel = path.join(dir, entry.name);
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

/** Walk ONLY test files and return their contents (for replica detection). */
function walkTests(): string[] {
  return walkSrc(false).filter((rel) => rel.includes(".test."));
}

describe("F1.6.4 architectural seal — composition", () => {
  it("main.tsx mounts RootErrorBoundary wrapping router/providers/AppShell", () => {
    const src = readFrontend("src/main.tsx");
    expect(src).toMatch(/<RootErrorBoundary>/);
    expect(src).toMatch(/import \{ RootErrorBoundary \}/);
  });

  it("App.tsx mounts RouteErrorBoundary inside AppShell; AuthenticatedRoutes is a descendant", () => {
    const src = readFrontend("src/App.tsx");
    expect(src).toMatch(/<AppShell>/);
    expect(src).toMatch(/<RouteErrorBoundary>/);
    expect(src).toMatch(/<AuthenticatedRoutes/);
    // RouteErrorBoundary appears between AppShell and AuthenticatedRoutes.
    const appShellIdx = src.indexOf("<AppShell>");
    const boundaryIdx = src.indexOf("<RouteErrorBoundary>");
    const routesIdx = src.indexOf("<AuthenticatedRoutes");
    expect(appShellIdx).toBeGreaterThanOrEqual(0);
    expect(boundaryIdx).toBeGreaterThan(appShellIdx);
    expect(routesIdx).toBeGreaterThan(boundaryIdx);
  });

  it("main.tsx calls installRuntimeObservers and wires import.meta.hot.dispose", () => {
    const src = readFrontend("src/main.tsx");
    expect(src).toMatch(/installRuntimeObservers\(\)/);
    expect(src).toMatch(/import\.meta\.hot\.dispose/);
  });
});

describe("F1.6.4 architectural seal — Sentry single-transport [V3-5]", () => {
  it("sentry.ts source contains defaultIntegrations:false", () => {
    const src = readFrontend("src/lib/sentry.ts");
    expect(src).toMatch(/defaultIntegrations:\s*false/);
  });

  it("sentry.ts source contains integrations:[]", () => {
    const src = readFrontend("src/lib/sentry.ts");
    expect(src).toMatch(/integrations:\s*\[\s*\]/);
  });

  it("zero production Sentry.captureException call sites", () => {
    // Walk src/ excluding test files; assert no actual call expressions
    // (comments mentioning the symbol are allowed).
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      const content = readSrc(rel);
      // Strip line comments + block comments before matching so doc
      // references don't trip the check.
      const stripped = content
        .replace(/\/\/.*$/gm, "")
        .replace(/\/\*[\s\S]*?\*\//g, "");
      if (/Sentry\.captureException\s*\(/.test(stripped)) {
        offenders.push(rel);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("zero production Sentry.captureMessage call sites", () => {
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      const content = readSrc(rel);
      const stripped = content
        .replace(/\/\/.*$/gm, "")
        .replace(/\/\*[\s\S]*?\*\//g, "");
      if (/Sentry\.captureMessage\s*\(/.test(stripped)) {
        offenders.push(rel);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("zero Sentry.ErrorBoundary usage in production source", () => {
    const offenders: string[] = [];
    for (const rel of walkSrc(true)) {
      const content = readSrc(rel);
      const stripped = content
        .replace(/\/\/.*$/gm, "")
        .replace(/\/\*[\s\S]*?\*\//g, "");
      if (/Sentry\.ErrorBoundary/.test(stripped)) {
        offenders.push(rel);
      }
    }
    expect(offenders).toEqual([]);
  });
});

describe("F1.6.4 architectural seal — reporter never-throw [V3-2]", () => {
  it("reportRuntimeError wraps the entire orchestration in try/catch", () => {
    const src = readFrontend("src/lib/runtime-error-reporter.ts");
    // Outer try/catch that returns fallbackEventId.
    expect(src).toMatch(/const fallbackEventId = generateEventId\(\)/);
    // The outer catch returns the fallback event_id. Look for both the
    // comment AND the return statement existing in the function.
    expect(src).toMatch(/\/\/ Any unexpected internal failure/);
    expect(src).toMatch(/return fallbackEventId;/);
  });

  it("sendRuntimeErrorReport invocation is fire-and-forget (void ... .catch)", () => {
    const src = readFrontend("src/lib/runtime-error-reporter.ts");
    expect(src).toMatch(/void sendRuntimeErrorReport\(/);
    expect(src).toMatch(/\.catch\(\(\) =>/);
  });

  it("zero reporter call sites passing request/response/headers/Authorization as PAYLOAD fields", () => {
    // The `body` parameter to callContract is the sanctioned transport
    // shape — what we forbid is naming payload FIELDS request/response/
    // headers/Authorization inside the sanitized report.
    const files = [
      "src/lib/runtime-error-reporter.ts",
      "src/lib/runtime-error-sanitizer.ts",
      "src/api/contracts/diagnostics.ts",
    ];
    const offenders: string[] = [];
    for (const f of files) {
      const content = readFrontend(f);
      // Strip comments.
      const stripped = content
        .replace(/\/\/.*$/gm, "")
        .replace(/\/\*[\s\S]*?\*\//g, "");
      // Forbid these as object keys (e.g. `request: ...` or `headers: ...`).
      // The diagnostics-client.ts is excluded because it legitimately
      // uses { body: report } — body is the transport shape, not a payload field.
      if (/\b(request|response|headers|Authorization)\s*:/i.test(stripped)) {
        offenders.push(f);
      }
    }
    expect(offenders).toEqual([]);
  });
});

describe("F1.6.4 architectural seal — no test-owned boundary replicas", () => {
  it("principal tests use production RootErrorBoundary/RouteErrorBoundary (no replicas)", () => {
    // Search test files for class-boundary reimplementations.
    const offenders: string[] = [];
    for (const content of walkTests()) {
      // A test-owned replica would define getDerivedStateFromError or
      // componentDidCatch inside a test file. Strip comments first.
      const stripped = content
        .replace(/\/\/.*$/gm, "")
        .replace(/\/\*[\s\S]*?\*\//g, "");
      if (/static\s+getDerivedStateFromError/.test(stripped)) {
        offenders.push("getDerivedStateFromError replica found");
      }
      if (/componentDidCatch\s*\(/.test(stripped)) {
        offenders.push("componentDidCatch replica found");
      }
    }
    expect(offenders).toEqual([]);
  });
});

describe("F1.6.4 architectural seal — backend governance [V3-4 V3-5]", () => {
  it("app.py JWT bypass checks method AND path (not just prefix)", () => {
    const src = readProject("backend/api/app.py");
    expect(src).toMatch(/request\.method\s*==\s*"POST"/);
    expect(src).toMatch(/path\s*==\s*"\/api\/v1\/diagnostics\/runtime-error"/);
    // The condition must be a compound (method AND path).
    const condMatch = src.match(/request\.method\s*==\s*"POST"\s*\n?\s*and\s*\n?\s*path\s*==\s*"\/api\/v1\/diagnostics\/runtime-error"/);
    expect(condMatch).not.toBeNull();
  });

  it("diagnostics_body_limit.py exists and is registered via add_middleware", () => {
    const middlewareSrc = readProject("backend/api/middleware/diagnostics_body_limit.py");
    expect(middlewareSrc).toMatch(/class DiagnosticsBodyLimitMiddleware/);
    expect(middlewareSrc).toMatch(/MAX_BODY_BYTES\s*=\s*8\s*\*\s*1024/);

    const appSrc = readProject("backend/api/app.py");
    expect(appSrc).toMatch(/add_middleware\(DiagnosticsBodyLimitMiddleware\)/);
  });

  it("diagnostics.py registers exactly one POST route", () => {
    const src = readProject("backend/api/routes/diagnostics.py");
    const postRoutes = src.match(/@router\.post\(/g);
    expect(postRoutes?.length).toBe(1);
    // The one route is /runtime-error.
    expect(src).toMatch(/@router\.post\(\s*["']\/runtime-error["']/);
  });
});

describe("F1.6.4 architectural seal — sanitizer security [V3-5]", () => {
  it("sanitizer uses allowlisted messages (never raw Error.message)", () => {
    const src = readFrontend("src/lib/runtime-error-sanitizer.ts");
    expect(src).toMatch(/ALLOWLISTED_MESSAGES/);
    expect(src).toMatch(/render_error/);
    expect(src).toMatch(/lazy_route_error/);
    expect(src).toMatch(/global_error/);
    expect(src).toMatch(/unhandled_rejection/);
  });

  it("sanitizer never reads error.message into the payload", () => {
    const src = readFrontend("src/lib/runtime-error-sanitizer.ts");
    // Strip comments before checking — doc references are allowed.
    const stripped = src
      .replace(/\/\/.*$/gm, "")
      .replace(/\/\*[\s\S]*?\*\//g, "");
    // The only place .message could appear is in normalizeErrorName
    // (which uses .name, not .message). Forbid .message references in
    // the sanitizer's executable code.
    expect(stripped).not.toMatch(/error\.message/);
    expect(stripped).not.toMatch(/\.stack\b/);
  });
});

describe("F1.6.4 architectural seal — registry fingerprint [V3-1]", () => {
  it("fingerprint does NOT include category", () => {
    const src = readFrontend("src/lib/runtime-error-registry.ts");
    // Extract the buildFingerprint function and verify category is absent.
    const fnMatch = src.match(/function buildFingerprint[\s\S]*?return fnv1a32\(([\s\S]*?)\);/);
    expect(fnMatch).not.toBeNull();
    const fingerprintBody = fnMatch![1];
    // category must NOT be referenced in the fingerprint composite.
    expect(fingerprintBody).not.toMatch(/\bcategory\b/);
  });

  it("registry has TTL with expiresAt metadata", () => {
    const src = readFrontend("src/lib/runtime-error-registry.ts");
    expect(src).toMatch(/expiresAt/);
    expect(src).toMatch(/INCIDENT_WINDOW_MS/);
  });

  it("registry has a hard size cap", () => {
    const src = readFrontend("src/lib/runtime-error-registry.ts");
    expect(src).toMatch(/MAX_FINGERPRINT_RECORDS/);
    expect(src).toMatch(/enforceSizeCap/);
  });

  it("registry uses a synchronous composite key (no async hashing)", () => {
    const src = readFrontend("src/lib/runtime-error-registry.ts");
    // crypto.subtle is async; forbid it.
    expect(src).not.toMatch(/crypto\.subtle/);
    expect(src).not.toMatch(/await\s+.*hash/i);
  });
});
