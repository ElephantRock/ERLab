/**
 * F1.6.3 — lazy-route wrapper with bounded failure classification.
 *
 * Wraps each `lazy(() => import(...))` in AppRoutes.tsx so that an
 * import failure throws a `LazyRouteError` (which the route boundary
 * classifies as category=lazy_route_error) instead of an opaque
 * chunk-load error.
 *
 * F1.6.3 [V3-3]: the retry marker is cleared ONLY by the LoadedRoute
 * wrapper's useEffect AFTER the import succeeds and the component
 * mounts. An ancestor sentinel cannot safely clear the marker because
 * it would render BEFORE the lazy child finishes loading.
 *
 * The wrapper:
 *   1. Awaits the import.
 *   2. On success: returns a wrapper component that, on mount, clears
 *      the lazy-retry marker for the current route, then renders the
 *      loaded component.
 *   3. On failure: throws LazyRouteError (no module path leaked).
 */

import {
  lazy,
  useEffect,
  type ComponentType,
  type LazyExoticComponent,
} from "react";
import { useLocation } from "react-router-dom";
import { clearLazyRetry } from "@/lib/lazy-route-retry";

type RouteModule = { default: ComponentType<Record<string, unknown>> };

/**
 * Error thrown when a lazy route module fails to load. Carries no
 * module path or stack — the route boundary classifies it as
 * category=lazy_route_error and uses an allowlisted message.
 */
export class LazyRouteError extends Error {
  name = "LazyRouteError";
  constructor() {
    super("A route module could not be loaded.");
    // Maintain proper prototype chain for ES5 targets.
    Object.setPrototypeOf(this, LazyRouteError.prototype);
  }
}

/**
 * Wrap a lazy import so failure becomes a typed LazyRouteError.
 *
 * Usage in AppRoutes.tsx:
 *   const DashboardPage = lazyRoute(() => import("./pages/dashboard"));
 */
export function lazyRoute(
  loader: () => Promise<RouteModule>,
): LazyExoticComponent<ComponentType<Record<string, unknown>>> {
  return lazy(async () => {
    try {
      const module = await loader();
      // The wrapper component mounts AFTER the import succeeds. It
      // clears the retry marker via useEffect — NEVER before. This is
      // the ONLY successful-clear point for the lazy-retry lifecycle.
      return {
        default: function LoadedRouteWrapper(props) {
          const location = useLocation();
          useEffect(() => {
            clearLazyRetry(location.pathname);
          }, [location.pathname]);
          const Inner = module.default;
          return <Inner {...props} />;
        },
      };
    } catch {
      // modulePath NOT included — defense against leaking internals.
      throw new LazyRouteError();
    }
  });
}
