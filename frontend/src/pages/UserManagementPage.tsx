import { useEffect, useState, type FormEvent } from "react";
import { authApi } from "../auth/authApi";
import { roleLabel, type AuthUser, type UserRole } from "../auth/permissions";
import { useAuth } from "../auth/AuthProvider";

export default function UserManagementPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState(""); const [name, setName] = useState("");
  const [role, setRole] = useState<UserRole>("analyst"); const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try { setUsers(await authApi.users()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load user accounts."); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    let active = true;
    const loadUsers = async () => {
      try { const loaded = await authApi.users(); if (active) { setUsers(loaded); setError(null); } }
      catch (cause: unknown) { if (active) setError(cause instanceof Error ? cause.message : "Could not load user accounts."); }
      finally { if (active) setLoading(false); }
    };
    void loadUsers();
    const timer = window.setInterval(() => void loadUsers(), 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setMessage(null);
    try {
      await authApi.createUser({ email, name, role, password });
      setEmail(""); setName(""); setPassword(""); setMessage("Account created."); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create account."); }
    finally { setBusy(false); }
  }

  async function change(user: AuthUser, update: { role?: UserRole; active?: boolean }) {
    setBusy(true); setError(null); setMessage(null);
    try { await authApi.updateUser(user.id, update); setMessage("Account updated."); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update account."); }
    finally { setBusy(false); }
  }

  return <div>
    <div className="mb-5"><span className="text-[10px] font-bold tracking-widest text-cyan-400">ADMINISTRATION</span><h1 className="m-0 mt-1 text-2xl font-extrabold text-white">User Management</h1><p className="m-0 mt-1 text-sm text-slate-400">Create accounts, assign roles, and activate or deactivate access.</p></div>
    {error && <p role="alert" className="rounded-xl border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-200">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-3 text-sm text-emerald-200">{message}</p>}
    <form onSubmit={(event) => void create(event)} className="mb-5 grid gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:grid-cols-2 lg:grid-cols-5">
      <input required type="email" autoComplete="off" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} className="min-w-0 rounded-lg border border-white/10 bg-[#11162d] px-3 py-2 text-sm text-white" />
      <input required maxLength={120} placeholder="Display name" value={name} onChange={(event) => setName(event.target.value)} className="min-w-0 rounded-lg border border-white/10 bg-[#11162d] px-3 py-2 text-sm text-white" />
      <select value={role} onChange={(event) => setRole(event.target.value as UserRole)} className="rounded-lg border border-white/10 bg-[#11162d] px-3 py-2 text-sm text-white">{(["administrator", "analyst", "reviewer", "viewer"] as const).map((item) => <option key={item} value={item}>{roleLabel(item)}</option>)}</select>
      <input required minLength={12} type="password" autoComplete="new-password" placeholder="Temporary password (12+ chars)" value={password} onChange={(event) => setPassword(event.target.value)} className="min-w-0 rounded-lg border border-white/10 bg-[#11162d] px-3 py-2 text-sm text-white" />
      <button disabled={busy} className="rounded-lg bg-cyan-500 px-3 py-2 text-sm font-bold text-slate-950 disabled:opacity-50">Create user</button>
    </form>
    {loading ? <p role="status" className="text-sm text-slate-400">Loading accounts…</p> : <div className="overflow-x-auto rounded-2xl border border-white/10"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-white/[0.04] text-xs uppercase text-slate-400"><tr>{["User", "Role", "Status", "Actions"].map((item) => <th key={item} className="px-4 py-3">{item}</th>)}</tr></thead><tbody>{users.map((account) => { const self = account.id === currentUser?.id; return <tr key={account.id} className="border-t border-white/5 text-slate-200"><td className="px-4 py-3"><strong>{account.name}</strong><span className="block text-xs text-slate-500">{account.email}{self ? " · You" : ""}</span></td><td className="px-4 py-3"><select aria-label={`Role for ${account.email}`} disabled={busy || self} value={account.role} onChange={(event) => void change(account, { role: event.target.value as UserRole })} className="rounded-md border border-white/10 bg-[#11162d] px-2 py-1">{(["administrator", "analyst", "reviewer", "viewer"] as const).map((item) => <option key={item} value={item}>{roleLabel(item)}</option>)}</select></td><td className="px-4 py-3">{account.active ? "Active" : "Inactive"}</td><td className="px-4 py-3"><button disabled={busy || self} onClick={() => void change(account, { active: !account.active })} className="rounded-md border border-white/15 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-50">{account.active ? "Deactivate" : "Activate"}</button></td></tr>;})}</tbody></table>{!users.length && <p className="p-5 text-sm text-slate-400">No accounts found.</p>}</div>}
  </div>;
}
