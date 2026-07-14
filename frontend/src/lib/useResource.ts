/**
 * useResource — the only sanctioned data-fetching hook.
 *
 * INTERFACE_CONTRACT §1. Derived from PRODUCT.md §6 (honesty in state) and
 * §2 (trust must be earned visibly).
 *
 * Why this exists: 11 of 20 pages hand-rolled `useEffect + useState +
 * loading + error`, producing no caching, no dedup, no retry, dead code,
 * state-after-unmount bugs, and silent `console.warn` error swallowing.
 * The root cause was that TanStack Query existed but was *optional*.
 * `useResource` makes it the only legal path (enforced by the
 * `erock/no-raw-use-effect-fetch` lint rule).
 *
 * Design: the return is a **discriminated union**, not four booleans. This
 * makes impossible states unrepresentable — there is no `loading && error`,
 * no `data` without `ready`. Callers pattern-match on `status`; the type
 * system guarantees every state is handled.
 *
 * Errors surface as `{ status: "error", retry }`, never thrown to the
 * caller. This is the structural cure for the `console.warn` swallow
 * pattern — the `retry` closure is reachable from render, so the failure
 * cannot disappear. PRODUCT.md §6: "if data failed to load, it says so."
 *
 * `empty` is distinct from `ready` (via the optional `isEmpty` predicate)
 * so an empty result is never dressed up as success — see PRODUCT.md
 * anti-pattern *The Decorative Indicator*.
 *
 * Backed by TanStack Query's `useQuery`: caching, dedup, refetch-on-focus,
 * and retry are inherited, not re-implemented.
 */

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

// ── Public types ──────────────────────────────────────────────────────

/**
 * The four states a resource can be in. Discriminated by `status`.
 *
 * - `loading`: initial fetch in flight, no data yet.
 * - `ready`: fetch succeeded and produced non-empty data.
 * - `error`: fetch failed; the caller MUST surface this (it carries retry).
 * - `empty`: fetch succeeded but the `isEmpty` predicate matched.
 *   Distinct from `ready` so empty states aren't dressed as success.
 */
export type ResourceState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: Error; retry: () => void }
  | { status: "empty"; data: T };

export interface UseResourceOptions<T> {
  /**
   * Per-resource stale time override. Defaults to the QueryClient's
   * `staleTime` (30s). Override only when freshness is product-critical
   * (e.g. a running-pipeline view) and cite why in the call site.
   */
  staleTime?: number;
  /**
   * Predicate distinguishing "loaded nothing" from "loaded something".
   * When it returns true, the state is `empty` rather than `ready`, so
   * the empty UI is reachable from `<DataView>` without the page
   * re-checking length.
   *
   * Default: treats `[]`, `""`, `null`, `undefined`, objects with a zero
   * `.total`, and objects with a zero-length array under standard keys
   * (`ideas`, `gaps`, `runs`, `pending`, `items`, `results`, `data`) as empty.
   *
   * For domain-shaped payloads with NON-standard list keys (e.g.
   * `{ cycles: [] }`, `{ sessions: [] }`), the default will NOT detect
   * empty. Pass `isEmpty` explicitly:
   *
   *   useResource(["history"], fetch, { isEmpty: (d) => d.cycles.length === 0 })
   *
   * The default list is intentionally NOT expanded with every domain noun.
   * Empty semantics belong to the resource owner, not a global heuristic.
   * (INTERFACE_CONTRACT §2, Tier 3.5.)
   */
  isEmpty?: (data: T) => boolean;
  /**
   * Whether the query is enabled. Pass `false` to defer fetching until a
   * condition is met (e.g. an id is known).
   */
  enabled?: boolean;
}

// ── Defaults ──────────────────────────────────────────────────────────

/**
 * Default empty-detector. Conservative: only treats obviously-empty shapes
 * as empty. Pages with custom empty semantics (e.g. "empty means zero
 * ideas even if the array exists") pass their own `isEmpty`.
 */
function defaultIsEmpty<T>(data: T): boolean {
  if (data == null) return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === "string") return data.length === 0;
  if (typeof data === "object") {
    const obj = data as Record<string, unknown>;
    // Common API shapes: { total: 0 }, { ideas: [] }, { pending: [] }
    if (typeof obj.total === "number") return obj.total === 0;
    const lists = ["ideas", "gaps", "runs", "pending", "items", "results", "data"];
    for (const k of lists) {
      const v = obj[k];
      if (Array.isArray(v)) return v.length === 0;
    }
  }
  return false;
}

// ── The hook ──────────────────────────────────────────────────────────

/**
 * Fetch a resource and return its state as a discriminated union.
 *
 * @param key     Stable query key (array). Same conventions as TanStack Query.
 * @param fetcher Async function returning the data. Errors thrown here
 *                become `{ status: "error" }` — they do NOT propagate.
 * @param options Optional `{ staleTime?, isEmpty?, enabled? }`.
 *
 * @example
 * const ideas = useResource(["ideas", { limit: 50 }], () => listIdeas({ limit: 50 }));
 * switch (ideas.status) {
 *   case "loading": return <Loading />;
 *   case "error":   return <Errored onRetry={ideas.retry} />;
 *   case "empty":   return <Empty what="ideas" />;
 *   case "ready":   return <IdeaGrid ideas={ideas.data} />;
 * }
 */
export function useResource<T>(
  key: readonly unknown[],
  fetcher: () => Promise<T>,
  options: UseResourceOptions<T> = {},
): ResourceState<T> {
  const { staleTime, isEmpty = defaultIsEmpty, enabled = true } = options;

  // We disable TanStack's own retry here (QueryClient default is retry: 1)
  // because the contract wants the `retry` to be an *explicit* caller
  // action surfaced through the render state, not a silent background
  // behavior that delays the error from appearing. The QueryClient-level
  // `retry: 1` is still active for pages that use `useQuery` directly.
  const queryOptions: UseQueryOptions<T, Error, T, readonly unknown[]> = {
    queryKey: key,
    queryFn: fetcher,
    enabled,
    retry: false,
    ...(staleTime !== undefined ? { staleTime } : {}),
  };

  const query = useQuery<T, Error, T, readonly unknown[]>(queryOptions);

  // `refetch` returns a Promise; wrap it so callers get a fire-and-forget
  // retry closure without having to handle the promise.
  const retry = () => {
    void query.refetch();
  };

  if (query.isPending) {
    return { status: "loading" };
  }

  if (query.error) {
    return { status: "error", error: query.error, retry };
  }

  // Success path. Discriminate empty from ready.
  const data = query.data as T;
  if (isEmpty(data)) {
    return { status: "empty", data };
  }

  return { status: "ready", data };
}
