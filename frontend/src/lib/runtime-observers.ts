/**
 * F1.6.2 — production global runtime observers.
 *
 * React error boundaries do NOT catch every JavaScript failure. This
 * module installs production-owned listeners for:
 *   - window 'error'              (event-handler exceptions, script errors)
 *   - window 'unhandledrejection' (orphan promise chains)
 *
 * The listeners call reportRuntimeError (the never-throw reporter)
 * which sanitizes, deduplicates against the boundary-caught registry,
 * and dispatches to the governed backend endpoint.
 *
 * F1.6.2 [V3-impl-qualification-2 (HMR)]:
 *   - Ownership via a stable Symbol on globalThis. A fresh module under
 *     HMR sees the same registry, so repeated install is a no-op and
 *     only the owning teardown removes the listeners.
 *
 * Installation contract:
 *   first installation      adds two listeners
 *   repeated installation   adds nothing, returns existing uninstall
 *   secondary teardown      removes nothing
 *   owning teardown         removes exactly the two listeners
 *   HMR replacement         leaves exactly one pair
 *
 * main.tsx wires:
 *   const uninstall = installRuntimeObservers();
 *   if (import.meta.hot) {
 *     import.meta.hot.dispose(() => uninstall());
 *   }
 */

import { reportRuntimeError } from "@/lib/runtime-error-reporter";

// ── Symbol-keyed ownership on globalThis ──────────────────────────────
// We access globalThis via a typed accessor (no `as any` — the cast is
// confined to a single typed helper that returns the registry or null).

const EROCK_OBSERVERS_SYMBOL = Symbol.for("erock.runtimeObservers");

interface ErockObserverRegistry {
  uninstall: () => void;
}

function getRegistry(): ErockObserverRegistry | null {
  if (typeof globalThis === "undefined") return null;
  const g = globalThis as Record<symbol, unknown>;
  const existing = g[EROCK_OBSERVERS_SYMBOL];
  if (existing && typeof existing === "object" && "uninstall" in existing) {
    return existing as ErockObserverRegistry;
  }
  return null;
}

function setRegistry(registry: ErockObserverRegistry | null): void {
  if (typeof globalThis === "undefined") return;
  const g = globalThis as Record<symbol, unknown>;
  if (registry === null) {
    delete g[EROCK_OBSERVERS_SYMBOL];
  } else {
    g[EROCK_OBSERVERS_SYMBOL] = registry;
  }
}

// ── Installation ─────────────────────────────────────────────────────

/**
 * Install the global error and unhandledrejection listeners. Idempotent
 * — repeated installation is a no-op. Returns a teardown function that
 * removes exactly the listeners this call (or the first call) installed.
 */
export function installRuntimeObservers(): () => void {
  // Check the Symbol-keyed registry on globalThis. If a prior install
  // (possibly from a previous HMR generation) already added listeners,
  // return that uninstall closure without adding new ones.
  const existing = getRegistry();
  if (existing) {
    return existing.uninstall;
  }

  const onError = (event: ErrorEvent): void => {
    // ErrorEvent carries: message, filename, lineno, colno, error.
    // Prefer the Error object; fall back to the message string.
    const error: unknown = event.error ?? event.message ?? "global error";
    const route = typeof window !== "undefined" ? window.location.pathname : "";
    // Fire-and-forget — reportRuntimeError never throws and the
    // transport is async (swallowed).
    reportRuntimeError(error, { category: "global_error", route });
  };

  const onUnhandledRejection = (event: PromiseRejectionEvent): void => {
    // PromiseRejectionEvent carries: reason.
    const reason: unknown = event.reason;
    const route = typeof window !== "undefined" ? window.location.pathname : "";
    reportRuntimeError(reason, { category: "unhandled_rejection", route });
  };

  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onUnhandledRejection);

  let uninstalled = false;
  const uninstall = (): void => {
    if (uninstalled) return; // secondary teardown removes nothing
    uninstalled = true;
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onUnhandledRejection);
    const current = getRegistry();
    if (current?.uninstall === uninstall) {
      setRegistry(null);
    }
  };

  setRegistry({ uninstall });

  return uninstall;
}

// ── Test helpers ─────────────────────────────────────────────────────

/**
 * Test-only: force-uninstall any installed observers and clear the
 * Symbol-keyed registry. Used by observer tests to start from a clean
 * state.
 */
export function _forceUninstallForTesting(): void {
  const existing = getRegistry();
  if (existing) {
    existing.uninstall();
    setRegistry(null);
  }
}
