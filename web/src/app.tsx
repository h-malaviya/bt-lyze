import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/use-auth";
import type { Role } from "./lib/api";
import { AdminDashboard } from "./pages/admin-dashboard";
import { LoginPage } from "./pages/login-page";
import { PanelDashboard } from "./pages/panel-dashboard";

function ProtectedRoute({ role }: { role: Role }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="grid min-h-screen place-items-center bg-fog text-sm font-semibold text-ink/50">Loading workspace…</div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={user.role === "admin" ? "/admin" : "/panel"} replace />;
  return <Outlet />;
}

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "admin" ? "/admin" : "/panel"} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute role="panel" />}>
        <Route path="/panel" element={<PanelDashboard />} />
      </Route>
      <Route element={<ProtectedRoute role="admin" />}>
        <Route path="/admin" element={<AdminDashboard />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
