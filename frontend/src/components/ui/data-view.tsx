/**
 * DataView — the single render primitive for any resource-bound surface.
 *
 * INTERFACE_CONTRACT §2. Derived from PRODUCT.md §6 (honesty in state).
 *
 * Composes the four `ResourceState` cases from `useResource` into
 * renderable output. The ready case is a **render-prop** so the four
 * states never leak into the page's JSX tree — a page becomes:
 *
 *   fetch → <DataView> → content
 *
 * Reuses the three existing primitives (`EmptyState`, `ErrorCard`,
 * `Skeleton`) rather than reinventing them. This completes their role:
 * they were already the intended patterns; `DataView` makes them the only
 * path by composing them into the canonical flow.
 *
 * Convention (already stated by ErrorCard, enforced here structurally):
 *   mutations → toast.error()
 *   queries   → <DataView>
 *
 * The loading state is content-shaped, not a generic spinner: pass
 * `loading.lines` to match the skeleton to the shape of the content
 * (a list shows list skeletons, a detail page shows detail skeletons).
 * This is already the dashboard's pattern — DataView makes it universal.
 *
 * ── testId ownership (Tier 2.5 hardening) ───────────────────────────
 *
 * The `testId` prop sets a stem from which ALL state testids derive.
 * Two layers own testids, and they MUST NOT collide:
 *
 *   WRAPPER (owned by DataView itself):
 *     `${stem}-loading`
 *     `${stem}-error`
 *     `${stem}-empty`
 *     `${stem}-ready`
 *
 *   INNER PRIMITIVES (default when a stem is set):
 *     `${stem}-error-card`    (the <ErrorCard> inside the error branch)
 *     `${stem}-empty-state`   (the <EmptyState> inside the empty branch)
 *
 * Rules for pages:
 *   - Page-level tests should target the WRAPPER ids (e.g. `ideas-error`).
 *     These identify which DataView state is rendered.
 *   - The INNER ids are for assertions that need to reach inside (rare).
 *   - DO NOT pass `error.testId` or `empty.testId` equal to a wrapper-owned
 *     id (e.g. `error={{ testId: "ideas-error" }}` when `testId="ideas"`).
 *     That creates duplicate testids and `getByTestId` will throw. The
 *     default (`${stem}-error-card`) is correct in almost all cases.
 *   - If no stem is passed, wrappers get `data-view-*` and inner primitives
 *     get `error-card` / `empty-state`.
 *
 * ── page-owned testId collisions (Tier 3.5 hardening) ──────────────
 *
 * When adopting DataView with `testId="x"`, the page must not ALREADY use
 * any of the wrapper-owned ids for another purpose:
 *
 *   x-loading, x-error, x-empty, x-ready
 *
 * If one of those ids already exists on the page (e.g. a mutation-error
 * banner with `data-testid="autonomous-error"`), either:
 *   - rename the existing page id (e.g. `autonomous-mutation-error`), or
 *   - choose a more specific DataView stem (e.g. `testId="autonomous-history"`).
 *
 * This is the third collision class (after wrapper-vs-inner). If a fourth
 * occurs after this documentation, escalate to a dev-only runtime invariant.
 */

import * as React from "react";
import { CircleSlash, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { EmptyState } from "./empty-state";
import { ErrorCard } from "./error-card";
import { Skeleton } from "./skeleton";
import { Button } from "./button";
import type { ResourceState } from "@/lib/useResource";
import type { LucideIcon } from "lucide-react";

export interface DataViewProps<T> {
  /** The resource state from `useResource`. */
  resource: ResourceState<T>;

  /**
   * Empty-state configuration. `what` describes the noun ("ideas", "gaps")
   * for the message; `action` is an optional CTA (e.g. "Start a run").
   * Defaults to a generic "nothing here yet" state.
   */
  empty?: {
    what?: string;
    icon?: LucideIcon;
    title?: string;
    message?: string;
    action?: React.ReactNode;
    /** testId forwarded to the inner <EmptyState>. Defaults to
     *  `${stem}-empty-state` when a stem is set, else `empty-state`.
     *  MUST NOT equal a wrapper-owned id (`${stem}-empty`). See the
     *  testId ownership section in the file header. */
    testId?: string;
  };

  /**
   * Loading-state configuration. `lines` controls how many skeleton lines
   * render so the skeleton approximates the content shape. Defaults to 3.
   * Pass more for dense lists, fewer for short detail panes.
   */
  loading?: {
    lines?: number;
  };

  /**
   * Error-state override hook. By default the error renders as `<ErrorCard>`
   * with a "Try again" button wired to the resource's `retry`. Pass
   * `onRetry` only if you need custom retry semantics (rare).
   */
  error?: {
    onRetry?: () => void;
    /** Optional page-specific message. Defaults to a generic "Failed to
     *  load. Please try again." Pages with domain context ("Failed to
     *  load pending approvals") should override for clarity. */
    message?: string;
    /** testId forwarded to the inner <ErrorCard>. Defaults to
     *  `${stem}-error-card` when a stem is set, else `error-card`.
     *  MUST NOT equal a wrapper-owned id (`${stem}-error`). See the
     *  testId ownership section in the file header. */
    testId?: string;
  };

  /**
   * Render-prop for the ready (and empty-with-data) cases. Receives the
   * data. The empty-with-data case (where `isEmpty` matched but data is
   * still present, e.g. `{ total: 0, ideas: [] }`) calls the children
   * only if `empty` is NOT configured — otherwise the empty state wins,
   * which is the safer default.
   */
  children: (data: T) => React.ReactNode;

  /** Optional className for the outer wrapper. */
  className?: string;

  /**
   * Optional testId stem for the four state wrappers. Sets the namespace
   * for ALL testids in this DataView — wrappers get `${stem}-{loading,
   * error,empty,ready}`; inner primitives default to `${stem}-{error-card,
   * empty-state}`. Pages should target the wrapper ids in tests. See the
   * "testId ownership" section in the file header for the full rule and
   * the collision-avoidance convention. Defaults to `data-view` (no stem).
   */
  testId?: string;
}

/**
 * Default icon for the generic empty state. Avoids coupling DataView to a
 * specific domain icon — pages pass their own via `empty.icon`.
 *
 * Uses the real lucide-react CircleSlash icon (a circle with a horizontal
 * line — the same visual the prior hand-rolled SVG rendered) so the type
 * is the exact LucideIcon contract expected by EmptyState's icon prop,
 * with no type assertion needed.
 */
const DEFAULT_EMPTY_ICON: LucideIcon = CircleSlash;

/**
 * Render a `ResourceState`. Pattern-match on `status`; each branch is
 * exhaustive (TypeScript verifies it).
 */
export function DataView<T>({
  resource,
  empty,
  loading,
  error,
  children,
  className,
  testId,
}: DataViewProps<T>): React.ReactNode {
  const loadingLines = loading?.lines ?? 3;
  const stem = testId ?? "data-view";

  switch (resource.status) {
    case "loading":
      return (
        <div
          className={cn("space-y-3", className)}
          data-testid={`${stem}-loading`}
          role="status"
          aria-live="polite"
        >
          {Array.from({ length: loadingLines }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
          <span className="sr-only">Loading…</span>
        </div>
      );

    case "error": {
      // ErrorCard is already the convention; the only addition is a
      // "Try again" button wired to retry. PRODUCT.md §6: errors always
      // offer a way forward, never a dead end.
      //
      // testId defaults: the wrapper gets `${stem}-error`; the inner
      // ErrorCard gets `${stem}-error-card` (NOT `${stem}-error`, which
      // would duplicate the wrapper). This prevents the duplicate-testid
      // trap when a page sets the stem and forgets the inner testId.
      const onRetry = error?.onRetry ?? resource.retry;
      const innerErrorTestId = error?.testId ?? (testId ? `${stem}-error-card` : "error-card");
      return (
        <div className={cn("space-y-3", className)} data-testid={`${stem}-error`}>
          <ErrorCard
            message={error?.message ?? "Failed to load. Please try again."}
            error={resource.error.message}
            testId={innerErrorTestId}
          />
          <div>
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
              Try again
            </Button>
          </div>
        </div>
      );
    }

    case "empty": {
      // Empty is first-class, distinct from ready. If the page configured
      // an empty state, use it. Otherwise render a generic one. The
      // underlying data is still reachable on the resource object for
      // pages that need to render a "shell" alongside the empty message.
      //
      // Same testId-defaults reasoning as the error branch: the wrapper
      // owns `${stem}-empty`; the inner EmptyState defaults to
      // `${stem}-empty-state` to avoid duplication.
      const innerEmptyTestId = empty?.testId ?? (testId ? `${stem}-empty-state` : "empty-state");
      if (empty) {
        return (
          <div className={cn(className)} data-testid={`${stem}-empty`}>
            <EmptyState
              icon={empty.icon ?? DEFAULT_EMPTY_ICON}
              title={empty.title ?? `No ${empty.what ?? "items"} yet`}
              message={empty.message}
              action={empty.action}
              testId={innerEmptyTestId}
            />
          </div>
        );
      }
      // No empty configured: render generic. PRODUCT.md anti-pattern
      // *The Decorative Indicator* — an empty state is never dressed up
      // as success.
      return (
        <div className={cn(className)} data-testid={`${stem}-empty`}>
          <EmptyState
            icon={DEFAULT_EMPTY_ICON}
            title="Nothing here yet"
            message="Check back after the next pipeline run."
          />
        </div>
      );
    }

    case "ready":
      // The render-prop. The four states never leak into the page's JSX.
      return (
        <div className={cn(className)} data-testid={`${stem}-ready`}>
          {children(resource.data)}
        </div>
      );
  }
}
