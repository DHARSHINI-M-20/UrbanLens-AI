import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { canVisit, DEFAULT_ROUTE } from "./permissions";

export function SessionLoading() {
  return <main className="grid min-h-screen place-items-center bg-[#0b1020] p-6 text-slate-200"><p role="status" className="rounded-2xl border border-white/10 bg-white/[0.04] px-6 py-5">Verifying your UrbanLens session…</p></main>;
}

export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <SessionLoading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export function RequirePermission() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <SessionLoading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!canVisit(user.role, location.pathname)) return <Navigate to="/403" replace state={{ attempted: location.pathname }} />;
  return <Outlet />;
}

export function LoginOnly() {
  const { user, loading } = useAuth();
  if (loading) return <SessionLoading />;
  return user ? <Navigate to={DEFAULT_ROUTE[user.role]} replace /> : <Outlet />;
}
