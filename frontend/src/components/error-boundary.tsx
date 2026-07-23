/**
 * F1.6.2 — Root error boundary.
 *
 * Sits at the OUTERMOST composition layer in main.tsx, wrapping the
 * router/providers/AppShell. Its purpose is to catch failures in the
 * providers/router/AppShell themselves — the components whose breakage
 * means we cannot safely assume navigation context is available.
 *
 * Fallback is intentionally full-screen: when the router itself is
 * broken we cannot render a dashboard link. We DO surface a diagnostic
 * event_id so the user can reference it.
 *
 * F1.6.2 [V3-2]: calls reportRuntimeError synchronously in
 * componentDidCatch so the fallback can render the event_id immediately.
 *
 * The narrow RouteErrorBoundary (src/components/route-error-boundary.tsx)
 * handles failures INSIDE the route tree, preserving the AppShell.
 */

import { Component, type ReactNode } from "react";
import { reportRuntimeError } from "@/lib/runtime-error-reporter";

interface Props {
  children: ReactNode;
  /** Optional fallback render prop. Default is a full-screen card. */
  fallback?: (opts: { eventId: string; retry: () => void }) => ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  eventId: string | null;
}

/**
 * Root boundary. Aliased as `ErrorBoundary` for backward compatibility
 * with the F1.5 composition.
 */
export class RootErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, eventId: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // Synchronous: register + emit + return event_id immediately so the
    // fallback (rendered on the next tick) can display it.
    const eventId = reportRuntimeError(error, {
      category: "render_error",
      route: typeof window !== "undefined" ? window.location.pathname : "",
      componentStack: info.componentStack ?? undefined,
    });
    this.setState({ eventId });
  }

  retry = (): void => {
    this.setState({ hasError: false, error: null, eventId: null });
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    const eventId = this.state.eventId ?? "evt-unknown";
    if (this.props.fallback) {
      return this.props.fallback({ eventId, retry: this.retry });
    }
    return <RootFallback eventId={eventId} onRetry={this.retry} />;
  }
}

/**
 * Default root fallback — full-screen, no navigation assumptions.
 *
 * @internal
 */
function RootFallback({ eventId, onRetry }: { eventId: string; onRetry: () => void }) {
  return (
    <div
      className="flex items-center justify-center min-h-screen p-8"
      data-testid="root-error-fallback"
    >
      <div className="max-w-md text-center space-y-4">
        <h2 className="text-xl font-bold">Something went wrong</h2>
        <p className="text-sm text-muted-foreground">
          An unexpected error occurred. Try reloading the page.
        </p>
        {eventId && (
          <p className="text-xs text-muted-foreground/70" data-testid="root-error-event-id">
            Reference: {eventId}
          </p>
        )}
        <button
          onClick={onRetry}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          data-testid="root-error-retry"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

/**
 * Backward-compat alias. Existing call sites in App.tsx and main.tsx
 * that imported `ErrorBoundary` continue to work; new code should use
 * `RootErrorBoundary` or `RouteErrorBoundary` explicitly.
 */
export const ErrorBoundary = RootErrorBoundary;
