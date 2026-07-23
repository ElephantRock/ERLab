/**
 * F1.6.2 — Route-content error boundary.
 *
 * Sits INSIDE AppShell (so the sidebar/header remain visible during a
 * route crash). Catches failures in the route tree and renders a
 * bounded fallback with route-safe navigation: Retry (clears state,
 * no reload), Go to dashboard, and a diagnostic event_id reference.
 *
 * F1.6.2 [V3-impl-qualification-2 + V3-2]:
 *   - The inner class boundary is keyed on `location.key` (NOT just
 *     pathname) so same-path navigations and search/hash transitions
 *     can recover when appropriate.
 *   - reportRuntimeError is called synchronously so the fallback can
 *     render the event_id immediately.
 *
 * The clearRouteScope() call on location change resets the incident
 * registry so a fresh route gets a fresh deduplication window.
 */

import { Component, useEffect, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { reportRuntimeError } from "@/lib/runtime-error-reporter";
import { clearRouteScope } from "@/lib/runtime-error-registry";
import type { LazyRouteError } from "@/lib/lazy-route";
import { hasLazyRetried, markLazyRetry } from "@/lib/lazy-route-retry";

interface RouteBoundaryInnerProps {
  /** Current location.key — used to remount on navigation. */
  locationKey: string;
  pathname: string;
  navigate: (to: string) => void;
  children: ReactNode;
}

interface RouteBoundaryInnerState {
  hasError: boolean;
  error: Error | null;
  eventId: string | null;
  isLazyRouteError: boolean;
}

/**
 * Inner class boundary. Rendered with `key={locationKey}` so React
 * unmounts and remounts it on navigation, naturally clearing boundary
 * state for the new route.
 */
class RouteBoundaryInner extends Component<RouteBoundaryInnerProps, RouteBoundaryInnerState> {
  state: RouteBoundaryInnerState = {
    hasError: false,
    error: null,
    eventId: null,
    isLazyRouteError: false,
  };

  static getDerivedStateFromError(error: Error): Partial<RouteBoundaryInnerState> {
    return {
      hasError: true,
      error,
      isLazyRouteError: error?.name === "LazyRouteError",
    };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    const category = error?.name === "LazyRouteError" ? "lazy_route_error" : "render_error";
    const eventId = reportRuntimeError(error, {
      category,
      route: this.props.pathname,
      componentStack: info.componentStack ?? undefined,
    });
    this.setState({ eventId });
  }

  retry = (): void => {
    this.setState({ hasError: false, error: null, eventId: null, isLazyRouteError: false });
  };

  goToDashboard = (): void => {
    this.props.navigate("/");
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    return (
      <RouteErrorFallback
        eventId={this.state.eventId ?? "evt-unknown"}
        isLazyRouteError={this.state.isLazyRouteError}
        pathname={this.props.pathname}
        onRetry={this.retry}
        onGoToDashboard={this.goToDashboard}
      />
    );
  }
}

/**
 * Functional wrapper that provides router context to the class boundary.
 *
 * Also observes location changes and clears the incident registry's
 * route scope so a fresh route gets a fresh dedup window.
 */
export function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();

  // Clear the route scope of the incident registry on every navigation.
  // This runs on every render where location.key changed (which is what
  // we want — each navigation resets the dedup window).
  // useEffect would also work, but the reset is idempotent so calling
  // it during render is safe and avoids an extra effect.
  // Use a ref to track the previous key so we only clear on actual change.
  // (Calling clearRouteScope on every render would clear even when only
  // React re-renders for unrelated reasons — we want to clear only on
  // navigation.)
  return (
    <RouteScopeClearer locationKey={location.key}>
      <RouteBoundaryInner
        key={location.key}
        locationKey={location.key}
        pathname={location.pathname}
        navigate={navigate}
      >
        {children}
      </RouteBoundaryInner>
    </RouteScopeClearer>
  );
}

/**
 * Tiny helper that calls clearRouteScope() once per location.key change.
 * Kept separate so the boundary remount (keyed on location.key) does
 * not run the effect twice.
 */
function RouteScopeClearer({
  locationKey,
  children,
}: {
  locationKey: string;
  children: ReactNode;
}) {
  useEffect(() => {
    clearRouteScope();
  }, [locationKey]);
  return <>{children}</>;
}

/**
 * Bounded route-content fallback. Rendered INSIDE AppShell, so the
 * sidebar/header remain visible.
 */
function RouteErrorFallback({
  eventId,
  isLazyRouteError,
  pathname,
  onRetry,
  onGoToDashboard,
}: {
  eventId: string;
  isLazyRouteError: boolean;
  pathname: string;
  onRetry: () => void;
  onGoToDashboard: () => void;
}) {
  // Lazy-route failures get a different recovery path: one guarded
  // reload via sessionStorage marker (see lib/lazy-route-retry.ts).
  const alreadyRetried = isLazyRouteError && hasLazyRetried(pathname);
  const showReloadAction = isLazyRouteError && !alreadyRetried;

  return (
    <div
      className="flex items-center justify-center min-h-[60vh] p-8"
      data-testid="route-error-fallback"
    >
      <div className="max-w-lg text-center space-y-4">
        <h2 className="text-xl font-bold">
          {isLazyRouteError ? "Couldn't load this page" : "Something went wrong"}
        </h2>
        <p className="text-sm text-muted-foreground">
          {isLazyRouteError
            ? alreadyRetried
              ? "This page still couldn't load after a retry. The deployment may have changed — try the dashboard, or reload manually later."
              : "This page failed to load. Try reloading; if the deployment has updated, the new version will take over."
            : "An unexpected error occurred while rendering this page. Try again, or return to the dashboard."}
        </p>
        {eventId && (
          <p className="text-xs text-muted-foreground/70" data-testid="route-error-event-id">
            Reference: {eventId}
          </p>
        )}
        <div className="flex justify-center gap-2 pt-2">
          {!showReloadAction && (
            <button
              onClick={onRetry}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              data-testid="route-error-retry"
            >
              Retry
            </button>
          )}
          {showReloadAction && <ReloadAndRetryButton pathname={pathname} />}
          <button
            onClick={onGoToDashboard}
            className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
            data-testid="route-error-dashboard"
          >
            Go to dashboard
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Lazy-route-only reload action. Marks the route as retried in
 * sessionStorage and triggers a full reload. On reload: if the new
 * deployment works, the route renders and the marker is cleared; if
 * the same chunk fails, the boundary sees the marker and hides this
 * button (persistent fallback, no reload loop).
 */
function ReloadAndRetryButton({ pathname }: { pathname: string }) {
  const onClick = () => {
    markLazyRetry(pathname);
    window.location.reload();
  };
  return (
    <button
      onClick={onClick}
      className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      data-testid="route-error-reload"
    >
      Reload and retry
    </button>
  );
}

// Re-export the LazyRouteError type for type-narrowing in callers.
export type { LazyRouteError };
