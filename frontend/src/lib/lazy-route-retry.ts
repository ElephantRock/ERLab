/**
 * F1.6.3 — lazy-route retry marker (sessionStorage-backed).
 *
 * Tracks whether a route has already been reloaded once for the current
 * build. Prevents reload loops when the deployment itself is broken.
 *
 * F1.6.3 [V3-impl-qualification-4]: production build identifier. The
 * marker MUST NOT key on a permanent "unknown" build — that could
 * suppress guarded recovery for subsequent deployments in the same
 * browser session.
 *
 * Key shape: `erock_lazy_retry_<buildHash>_<route>`
 *
 * Lifecycle (F1.6.3 [V3-3]):
 *   - lazy import fails → marker absent → route boundary shows
 *     "Reload and retry"
 *   - user selects Reload and retry → markLazyRetry writes marker,
 *     window.location.reload() fires
 *   - reload succeeds → LoadedRouteWrapper mounts → clearLazyRetry
 *     removes the marker
 *   - reload fails again → marker present → boundary shows persistent
 *     fallback (no reload action)
 *
 * Same build + route + repeated failure → no reload loop.
 * Different build hash → guarded retry available again (new marker key).
 * Missing build hash → 'dev' used (so dev-mode retries are not
 * permanently suppressed).
 */

const KEY_PREFIX = "erock_lazy_retry_";

/**
 * Get the current build identifier. NEVER returns "unknown" — falls
 * back to "dev" in dev mode (V3-impl-qualification-4).
 */
function getBuildKey(): string {
  try {
    const v = (import.meta.env.VITE_BUILD_HASH as string | undefined) ?? "";
    if (v && v !== "unknown") return v;
    if (import.meta.env.DEV) return "dev";
    // Production build with no hash configured — use timestamp bucket
    // so retries are not permanently suppressed.
    return `t${Math.floor(Date.now() / (5 * 60 * 1000))}`; // 5-min bucket
  } catch {
    return "dev";
  }
}

function storageKey(route: string): string {
  // Sanitize route to a safe key fragment.
  const safeRoute = route.replace(/[^A-Za-z0-9/_-]/g, "_").slice(0, 128);
  return `${KEY_PREFIX}${getBuildKey()}_${safeRoute}`;
}

/**
 * Mark that the given route has been reloaded once for the current build.
 * Idempotent — writing twice has the same effect as writing once.
 */
export function markLazyRetry(route: string): void {
  try {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(storageKey(route), "1");
  } catch {
    // sessionStorage may be unavailable (private mode, etc). Fail
    // closed: treat as if the marker is set so we don't loop. The
    // fallback UI will show the persistent variant.
  }
}

/**
 * Has the given route already been reloaded once for the current build?
 */
export function hasLazyRetried(route: string): boolean {
  try {
    if (typeof window === "undefined") return false;
    return window.sessionStorage.getItem(storageKey(route)) === "1";
  } catch {
    // If sessionStorage throws on read, fail closed (treat as retried).
    return true;
  }
}

/**
 * Clear the retry marker for a route. Called ONLY by LoadedRouteWrapper
 * AFTER the lazy import succeeds and the component mounts.
 */
export function clearLazyRetry(route: string): void {
  try {
    if (typeof window === "undefined") return;
    window.sessionStorage.removeItem(storageKey(route));
  } catch {
    // ignore
  }
}

/**
 * Test-only: clear all lazy-retry markers. Used by adversarial tests
 * to start from a clean state.
 */
export function _clearAllForTesting(): void {
  try {
    if (typeof window === "undefined") return;
    for (let i = window.sessionStorage.length - 1; i >= 0; i--) {
      const key = window.sessionStorage.key(i);
      if (key && key.startsWith(KEY_PREFIX)) {
        window.sessionStorage.removeItem(key);
      }
    }
  } catch {
    // ignore
  }
}
