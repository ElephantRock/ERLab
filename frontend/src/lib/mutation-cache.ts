/**
 * F1.5c: Cache-owned mutation side-effects.
 *
 * PROBLEM
 *   useMutation's component-level onSuccess is bound to the component that
 *   invoked the hook. When that component unmounts before the mutationFn
 *   resolves (e.g. user navigates away mid-PATCH), the observer is removed
 *   and onSuccess never fires — declared invalidations are silently lost,
 *   and the cache drifts from backend truth.
 *
 * FIX
 *   Move cache-integrity invalidations to a global MutationCache whose
 *   onSuccess is bound to the Mutation instance in the cache (not to a
 *   component observer). Each mutation that needs post-success
 *   invalidation declares its targets via meta fields. The cache handler
 *   reads these and performs the invalidation regardless of component
 *   mount state.
 *
 *   Component-level onSuccess stays for UX feedback (toasts) — losing a
 *   toast on unmount is acceptable; losing a cache invalidation is not.
 *
 * USAGE
 *   Production wires the cache in main.tsx via buildMutationCache(client).
 *   Tests that need to verify cache-owned behavior construct their
 *   QueryClient with the same cache via createQueryClientWithMutationCache().
 */

import { MutationCache, type QueryClient } from "@tanstack/react-query";

/** Query-key shape used by both exact and prefix invalidation. */
export type QueryKey = readonly unknown[];

export interface MutationSideEffectMeta {
  /**
   * Exact query keys to invalidate after success. Each entry is a full
   * query key, e.g. ["gap", 12] or ["literature-ingested"].
   */
  invalidateQueries?: readonly QueryKey[];
  /**
   * Query-key prefixes to invalidate after success. Each entry is a
   * partial key matched by TanStack's default prefix matching,
   * e.g. ["literature-search"] (matches ["literature-search", "foo"]).
   */
  invalidatePrefixes?: readonly QueryKey[];
}

/**
 * Build the production MutationCache. The caller provides an `invalidate`
 * interface that the cache calls when a mutation succeeds — this decouples
 * the QueryClient/MutationCache construction cycle (the cache needs the
 * client to invalidate; the client needs the cache at construction).
 * Cache-level onSuccess fires whether or not any component observer is
 * still mounted.
 */
export function buildMutationCache(invalidate: InvalidateCallbacks): MutationCache {
  return new MutationCache({
    onSuccess: (_data, _variables, _onMutateResult, mutation) => {
      const meta = mutation.meta as MutationSideEffectMeta | undefined;
      if (!meta) return;

      if (meta.invalidateQueries) {
        for (const key of meta.invalidateQueries) {
          invalidate.invalidateQueries(key);
        }
      }
      if (meta.invalidatePrefixes) {
        for (const prefix of meta.invalidatePrefixes) {
          invalidate.invalidatePrefixes(prefix);
        }
      }
    },
  });
}

/** Callbacks the MutationCache invokes to invalidate query cache entries. */
export interface InvalidateCallbacks {
  invalidateQueries(key: readonly unknown[]): void;
  invalidatePrefixes(prefix: readonly unknown[]): void;
}

/**
 * Convenience: build a MutationCache bound to a QueryClient via a getter
 * function. The getter breaks the construction cycle — the client is
 * captured by reference and resolved lazily when a mutation succeeds.
 */
export function buildMutationCacheForClient(clientGetter: () => QueryClient): MutationCache {
  return buildMutationCache({
    invalidateQueries(key: readonly unknown[]) {
      clientGetter().invalidateQueries({ queryKey: [...key] });
    },
    invalidatePrefixes(prefix: readonly unknown[]) {
      clientGetter().invalidateQueries({ queryKey: [...prefix] });
    },
  });
}

/** Type guard for MutationSideEffectMeta (defensive in cache handler). */
export function isMutationSideEffectMeta(value: unknown): value is MutationSideEffectMeta {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  if (v.invalidateQueries !== undefined && !Array.isArray(v.invalidateQueries)) return false;
  if (v.invalidatePrefixes !== undefined && !Array.isArray(v.invalidatePrefixes)) return false;
  return true;
}
