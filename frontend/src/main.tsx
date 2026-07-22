import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsProvider, useSettings } from "./contexts/settings-context";
import { AuthProvider } from "./contexts/auth-context";
import { Toaster } from "sonner";
import { ErrorBoundary } from "./components/error-boundary";
import { initSentry } from "./lib/sentry";
import { buildMutationCacheForClient } from "./lib/mutation-cache";
import App from "./App";
import "./i18n/config";
import "./globals.css";

initSentry();

// F1.5c: cache-owned mutation side-effects.
//
// useMutation's component-level onSuccess is bound to the component that
// invoked the hook. When that component unmounts before the mutationFn
// resolves (e.g. user navigates away mid-PATCH), the observer is removed
// and onSuccess never fires — declared invalidations are silently lost,
// and the cache drifts from backend truth.
//
// We move cache-integrity invalidations to a global MutationCache whose
// onSuccess is bound to the Mutation instance (which lives in the cache,
// not on a component). Each mutation that needs post-success invalidation
// declares its targets via `meta.invalidateQueries` / `meta.invalidatePrefixes`.
// The cache handler reads these and performs the invalidation regardless
// of component mount state.
//
// Component-level onSuccess stays for UX feedback (toasts) — losing a
// toast on unmount is acceptable; losing a cache invalidation is not.
//
// QueryClient and MutationCache form a cycle (the cache needs the client
// to invalidate; the client needs the cache at construction). We break
// the cycle with a mutable holder object — a constant binding that lets
// the cache resolve the client lazily without disabling any lint rule.
const queryClientRef: { current?: QueryClient } = {};
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
  mutationCache: buildMutationCacheForClient(() => {
    // Lazily resolve the client. By the time any mutation succeeds, the
    // assignment below has run and queryClientRef.current is populated.
    if (!queryClientRef.current) {
      throw new Error("QueryClient accessed before initialization");
    }
    return queryClientRef.current;
  }),
});
queryClientRef.current = queryClient;

/** Toaster needs to be inside SettingsProvider to read the theme. */
function ThemedToaster() {
  const { theme } = useSettings();
  return <Toaster position="bottom-right" theme={theme} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <SettingsProvider>
        <AuthProvider>
          <BrowserRouter>
            <ErrorBoundary>
              <App />
            </ErrorBoundary>
            <ThemedToaster />
          </BrowserRouter>
        </AuthProvider>
      </SettingsProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
