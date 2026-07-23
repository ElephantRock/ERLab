import { Routes, Route } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { AppShell } from "./components/layout/app-shell";
import { RouteErrorBoundary } from "./components/route-error-boundary";
import { useRTL } from "./hooks/useRTL";
import LoginPage from "./pages/login";
import { AuthenticatedRoutes, ProtectedRoute } from "./AppRoutes";

export default function App() {
  useRTL();
  const { user, loading } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <AppShell>
              <RouteErrorBoundary>
                <AuthenticatedRoutes />
              </RouteErrorBoundary>
            </AppShell>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
