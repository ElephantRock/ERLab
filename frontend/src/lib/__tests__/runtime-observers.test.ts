/**
 * F1.6.2 global runtime observers tests.
 *
 * Verifies:
 *   - first install adds 2 listeners
 *   - repeated install adds 0, returns existing uninstall
 *   - teardown removes exactly 2
 *   - secondary teardown removes 0
 *   - AbortError filtered (no report)
 *   - ApiError IS reportable (no blanket suppression)
 *   - reporter failure swallowed
 *   - listener is fire-and-forget
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/api/clients/diagnostics-client", () => ({
  sendRuntimeErrorReport: vi.fn().mockResolvedValue({ status: "accepted", event_id: "evt-x" }),
}));

import {
  installRuntimeObservers,
  _forceUninstallForTesting,
} from "@/lib/runtime-observers";
import * as reporter from "@/lib/runtime-error-reporter";
import { _resetForTesting as resetIncidentRegistry } from "@/lib/runtime-error-registry";

beforeEach(() => {
  resetIncidentRegistry();
  _forceUninstallForTesting();
});

afterEach(() => {
  _forceUninstallForTesting();
});

describe("installRuntimeObservers (F1.6.2)", () => {
  it("first install adds 2 listeners (error + unhandledrejection)", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    installRuntimeObservers();
    const added = addSpy.mock.calls.map(([event]) => event);
    expect(added).toContain("error");
    expect(added).toContain("unhandledrejection");
    addSpy.mockRestore();
  });

  it("repeated install adds 0 listeners, returns existing uninstall", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const uninstall1 = installRuntimeObservers();
    const callsAfterFirst = addSpy.mock.calls.length;
    const uninstall2 = installRuntimeObservers();
    expect(addSpy.mock.calls.length).toBe(callsAfterFirst); // no new listeners
    // Same uninstall closure returned.
    expect(uninstall2).toBe(uninstall1);
    addSpy.mockRestore();
    uninstall1();
  });

  it("owning teardown removes exactly 2 listeners", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const uninstall = installRuntimeObservers();
    uninstall();
    const removed = removeSpy.mock.calls.map(([event]) => event);
    expect(removed.filter((e) => e === "error").length).toBe(1);
    expect(removed.filter((e) => e === "unhandledrejection").length).toBe(1);
    removeSpy.mockRestore();
  });

  it("secondary teardown removes 0 listeners", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const uninstall = installRuntimeObservers();
    uninstall();
    removeSpy.mockClear();
    uninstall(); // second call
    expect(removeSpy.mock.calls.length).toBe(0);
    removeSpy.mockRestore();
  });

  it("HMR-like re-install after dispose leaves exactly one pair", () => {
    const u1 = installRuntimeObservers();
    u1(); // dispose (HMR .dispose)
    // Fresh install (new module generation)
    const u2 = installRuntimeObservers();
    // Should have added fresh listeners.
    const addSpy = vi.spyOn(window, "addEventListener");
    const u3 = installRuntimeObservers(); // repeated
    expect(addSpy.mock.calls.length).toBe(0); // no new — u2's are still installed
    addSpy.mockRestore();
    u2();
    u3();
  });
});

describe("observer filtering (F1.6.2)", () => {
  it("AbortError dispatched as window error → no transport call", async () => {
    const { sendRuntimeErrorReport } = await import("@/api/clients/diagnostics-client");
    vi.mocked(sendRuntimeErrorReport).mockClear();
    installRuntimeObservers();
    const abort = new DOMException("aborted", "AbortError");
    window.dispatchEvent(new ErrorEvent("error", { error: abort }));
    // Allow microtasks.
    await new Promise((r) => setTimeout(r, 0));
    expect(sendRuntimeErrorReport).not.toHaveBeenCalled();
  });

  it("unhandled rejection of AbortError → no transport call", async () => {
    const { sendRuntimeErrorReport } = await import("@/api/clients/diagnostics-client");
    vi.mocked(sendRuntimeErrorReport).mockClear();
    installRuntimeObservers();
    const abort = new Error("aborted");
    abort.name = "AbortError";
    window.dispatchEvent(
      new PromiseRejectionEvent(
        "unhandledrejection",
        { reason: abort, promise: Promise.resolve() },
      ),
    );
    await new Promise((r) => setTimeout(r, 0));
    expect(sendRuntimeErrorReport).not.toHaveBeenCalled();
  });

  it("ApiError reaching the global observer IS reported (no blanket suppression)", async () => {
    const { sendRuntimeErrorReport } = await import("@/api/clients/diagnostics-client");
    vi.mocked(sendRuntimeErrorReport).mockClear();
    installRuntimeObservers();
    class ApiError extends Error {
      name = "ApiError";
      constructor(public status: number, public detail: string) {
        super(detail);
      }
    }
    const apiErr = new ApiError(500, "boom");
    window.dispatchEvent(new ErrorEvent("error", { error: apiErr }));
    await new Promise((r) => setTimeout(r, 0));
    expect(sendRuntimeErrorReport).toHaveBeenCalledTimes(1);
  });

  it("transport failure is swallowed (no unhandled rejection side-effect)", async () => {
    const { sendRuntimeErrorReport } = await import("@/api/clients/diagnostics-client");
    vi.mocked(sendRuntimeErrorReport).mockRejectedValueOnce(new Error("net down"));
    installRuntimeObservers();
    // Track if any unhandled rejection is emitted by the swallow path.
    let unhandledSeen = false;
    const onRej = () => { unhandledSeen = true; };
    window.addEventListener("unhandledrejection", onRej);
    window.dispatchEvent(
      new ErrorEvent("error", { error: new Error("trigger report") }),
    );
    await new Promise((r) => setTimeout(r, 10));
    window.removeEventListener("unhandledrejection", onRej);
    // The reporter catches the transport rejection; no new unhandled
    // rejection is emitted for the SAME error.
    expect(unhandledSeen).toBe(false);
  });

  it("listener is fire-and-forget (reportRuntimeError returns synchronously)", () => {
    const reporterSpy = vi.spyOn(reporter, "reportRuntimeError");
    installRuntimeObservers();
    reporterSpy.mockClear();
    // The listener calls reportRuntimeError synchronously.
    window.dispatchEvent(new ErrorEvent("error", { error: new Error("test") }));
    expect(reporterSpy).toHaveBeenCalledTimes(1);
    reporterSpy.mockRestore();
  });
});
