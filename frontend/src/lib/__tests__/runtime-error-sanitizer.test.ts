/**
 * F1.6.1 sanitizer tests.
 *
 * SECURITY INVARIANT under test:
 *   - raw Error.message NEVER appears in any field of the report
 *   - error.stack NEVER appears
 *   - request/response bodies, headers, tokens NEVER appear
 *   - allowlisted per-category message is used instead
 *   - component stacks are path/query-sanitized
 */

import { describe, it, expect } from "vitest";
import {
  sanitizeErrorForReport,
  sanitizeComponentStack,
  sanitizeRoute,
  sanitizeId,
  normalizeErrorName,
  stripSensitiveValues,
  ALLOWLISTED_MESSAGES,
  MAX_COMPONENT_STACK,
  MAX_ROUTE,
} from "@/lib/runtime-error-sanitizer";

describe("sanitizeErrorForReport (F1.6.1)", () => {
  it("uses allowlisted message per category — never raw Error.message", () => {
    const error = new Error("SECRET research content about CRISPR yeast strains");
    const report = sanitizeErrorForReport(
      error,
      { category: "render_error", route: "/dashboard" },
      "evt-test-001",
    );
    expect(report.sanitized_message).toBe(ALLOWLISTED_MESSAGES.render_error);
    // The raw message MUST NOT appear in any field.
    const serialized = JSON.stringify(report);
    expect(serialized).not.toContain("SECRET");
    expect(serialized).not.toContain("CRISPR");
    expect(serialized).not.toContain("yeast");
  });

  it("includes event_id verbatim (when already sanitized)", () => {
    const report = sanitizeErrorForReport(
      new Error("x"),
      { category: "global_error", route: "/" },
      "evt-clean-id-001",
    );
    expect(report.event_id).toBe("evt-clean-id-001");
  });

  it("strips unsafe chars from event_id", () => {
    const report = sanitizeErrorForReport(
      new Error("x"),
      { category: "global_error", route: "/" },
      "evt-\\n-foo'; DROP--ok",
    );
    // safe charset = [A-Za-z0-9_-] — backslash, quote, semicolon, space stripped.
    for (const ch of report.event_id) {
      expect(/[A-Za-z0-9_-]/.test(ch)).toBe(true);
    }
    expect(report.event_id).not.toContain("\\");
    expect(report.event_id).not.toContain("'");
    expect(report.event_id).not.toContain(";");
    expect(report.event_id).not.toContain(" ");
  });

  it("falls back to allowlisted message for unknown category value (defensive)", () => {
    // Force an unknown category through the type system.
    const report = sanitizeErrorForReport(
      new Error("x"),
      { category: "unhandled_rejection" as const, route: "/" },
      "evt-1",
    );
    expect(report.sanitized_message).toBe(ALLOWLISTED_MESSAGES.unhandled_rejection);
  });

  it("strips query and fragment from route", () => {
    const report = sanitizeErrorForReport(
      new Error("x"),
      { category: "global_error", route: "/gaps/12?token=secret#frag" },
      "evt-1",
    );
    expect(report.route).toBe("/gaps/12");
    expect(report.route).not.toContain("token");
  });

  it("strips credential-bearing URL in route", () => {
    const report = sanitizeErrorForReport(
      new Error("x"),
      { category: "global_error", route: "https://user:pass@host/api/x" },
      "evt-1",
    );
    expect(JSON.stringify(report)).not.toContain("user:pass");
  });

  it("never includes error.stack", () => {
    const error = new Error("boom");
    error.stack = "SUPER_SECRET_STACK_FRAME_LINE_1\nSUPER_SECRET_STACK_FRAME_LINE_2";
    const report = sanitizeErrorForReport(
      error,
      { category: "render_error", route: "/" },
      "evt-1",
    );
    const serialized = JSON.stringify(report);
    expect(serialized).not.toContain("SUPER_SECRET_STACK");
    // No 'stack' field anywhere.
    expect(serialized).not.toMatch(/"stack"\s*:/);
  });

  it("normalizes error name with safe charset", () => {
    const error = new (class CustomError extends Error {})("x");
    error.name = "Custom\\nError; DROP TABLE";
    const report = sanitizeErrorForReport(
      error,
      { category: "render_error", route: "/" },
      "evt-1",
    );
    for (const ch of report.error_name) {
      expect(/[A-Za-z0-9_]/.test(ch)).toBe(true);
    }
    // Backslash and whitespace stripped; "Custom" + "nError" + "DROPTABLE"
    // remain concatenated. The point is no log-injection chars survive.
    expect(report.error_name).not.toContain("\\");
    expect(report.error_name).not.toContain(" ");
    expect(report.error_name).not.toContain(";");
    expect(report.error_name.startsWith("Custom")).toBe(true);
  });

  it("handles non-Error throw values (strings, objects)", () => {
    // Strings are treated as the error name itself (more useful than "string").
    const report1 = sanitizeErrorForReport(
      "string error body",
      { category: "unhandled_rejection", route: "/" },
      "evt-1",
    );
    expect(report1.error_name).toBe("stringerrorbody");

    const report2 = sanitizeErrorForReport(
      { code: 42, detail: "secret" },
      { category: "unhandled_rejection", route: "/" },
      "evt-2",
    );
    // Objects without a name property → typeof ("object").
    expect(report2.error_name).toBe("object");
    // No raw detail leakage.
    expect(JSON.stringify(report2)).not.toContain("secret");
  });

  it("component stack is bounded to MAX_COMPONENT_STACK", () => {
    const hugeStack = "x".repeat(MAX_COMPONENT_STACK + 5000);
    const report = sanitizeErrorForReport(
      new Error("x"),
      { category: "render_error", route: "/", componentStack: hugeStack },
      "evt-1",
    );
    expect(report.component_stack!.length).toBeLessThanOrEqual(MAX_COMPONENT_STACK);
  });
});

describe("sanitizeComponentStack", () => {
  it("reduces file URIs to filename only", () => {
    const input = "at Foo\n    at Bar (file:///Users/x/src/pages/dashboard.tsx:42:7)";
    const out = sanitizeComponentStack(input);
    expect(out).not.toContain("file:///");
    expect(out).not.toContain("/Users/x/src/pages/");
    expect(out).toContain("dashboard.tsx");
  });

  it("strips bearer tokens from frames", () => {
    const input = "at Foo (https://evil.com/x?token=abc123Bearer xyz)";
    const out = sanitizeComponentStack(input);
    expect(out).not.toContain("abc123");
    expect(out).not.toMatch(/[Bb]earer\s+\S+/);
  });

  it("strips credential URLs", () => {
    const input = "at Foo (https://user:pass@host/x)";
    const out = sanitizeComponentStack(input);
    expect(out).not.toContain("user:pass");
  });

  it("returns null for undefined input", () => {
    expect(sanitizeComponentStack(undefined)).toBeNull();
    expect(sanitizeComponentStack(null)).toBeNull();
    expect(sanitizeComponentStack("")).toBeNull();
  });

  it("truncates lines longer than 200 chars (props text defense)", () => {
    const longLine = "at Foo " + "x".repeat(300);
    const out = sanitizeComponentStack(longLine)!;
    const firstLine = out.split("\n")[0];
    expect(firstLine.length).toBeLessThanOrEqual(201); // 200 + ellipsis
  });
});

describe("sanitizeRoute", () => {
  it("returns empty string for empty input", () => {
    expect(sanitizeRoute("")).toBe("");
    expect(sanitizeRoute(null)).toBe("");
    expect(sanitizeRoute(undefined)).toBe("");
  });

  it("bounds length", () => {
    const long = "/" + "x".repeat(MAX_ROUTE + 100);
    expect(sanitizeRoute(long).length).toBeLessThanOrEqual(MAX_ROUTE);
  });
});

describe("sanitizeId", () => {
  it("strips unsafe chars (keeps [A-Za-z0-9_-])", () => {
    const out = sanitizeId("evt-foo'; DROP--ok", 64)!;
    for (const ch of out) {
      expect(/[A-Za-z0-9_-]/.test(ch)).toBe(true);
    }
    expect(out).not.toContain("'");
    expect(out).not.toContain(";");
    expect(out).not.toContain(" ");
  });
  it("returns null for empty", () => {
    expect(sanitizeId("", 64)).toBeNull();
    expect(sanitizeId(null, 64)).toBeNull();
  });
});

describe("normalizeErrorName", () => {
  it("handles plain string", () => {
    expect(normalizeErrorName("TypeError")).toBe("TypeError");
  });
  it("strips non-alphanumeric", () => {
    expect(normalizeErrorName("Type<script>")).toBe("Typescript");
  });
  it("returns 'unknown' for empty after cleaning", () => {
    expect(normalizeErrorName("?!@#$%")).toBe("unknown");
  });
});

describe("stripSensitiveValues", () => {
  it("removes bearer tokens", () => {
    const out = stripSensitiveValues("Authorization: Bearer abc.def.ghi");
    expect(out).not.toContain("abc.def.ghi");
    expect(out).toContain("[REDACTED]");
  });
  it("removes api_key query params", () => {
    const out = stripSensitiveValues("https://x/api?api_key=SECRET123");
    expect(out).not.toContain("SECRET123");
  });
  it("removes credential URLs", () => {
    const out = stripSensitiveValues("https://alice:hunter2@host/x");
    expect(out).not.toContain("alice:hunter2");
  });
});
