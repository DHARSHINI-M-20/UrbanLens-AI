import { useEffect, useState, type FormEvent } from "react";
import { Eye, EyeOff, LockKeyhole, MapPinned, Sparkles } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { canVisit, DEFAULT_ROUTE } from "../auth/permissions";
import { API_MODE } from "../utils/api";
import { authApi } from "../auth/authApi";

export default function LoginPage() {
  const { login, error: sessionError } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailTouched, setEmailTouched] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const [registrationEnabled, setRegistrationEnabled] = useState(false);
  const [showSetup, setShowSetup] = useState(false);
  const [showRegistration, setShowRegistration] = useState(false);
  const [setupName, setSetupName] = useState("");
  const [setupEmail, setSetupEmail] = useState("");
  const [setupPassword, setSetupPassword] = useState("");
  const [registerName, setRegisterName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerRole, setRegisterRole] = useState<"analyst" | "reviewer" | "viewer">("viewer");
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const passwordValid = password.length > 0;
  const showEmailError = (emailTouched || submitted) && email.length > 0 && !emailValid;

  useEffect(() => {
    let active = true;
    void authApi.setupStatus().then(({ setup_required, registration_enabled }) => {
      if (active) {
        setSetupRequired(setup_required);
        setRegistrationEnabled(registration_enabled);
      }
    }).catch(() => { if (active) setSetupRequired(false); });
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault(); setSubmitted(true); setError(null);
    if (!emailValid || !passwordValid) return;
    setBusy(true);
    try {
      const user = await login(email.trim(), password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && canVisit(user.role, from) ? from : DEFAULT_ROUTE[user.role], { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign-in failed. Please try again.");
    } finally { setBusy(false); }
  }

  async function setupAdministrator(event: FormEvent) {
    event.preventDefault(); setError(null); setBusy(true);
    try {
      await authApi.createInitialAdministrator({ email: setupEmail.trim(), name: setupName.trim(), password: setupPassword });
      const user = await login(setupEmail.trim(), setupPassword);
      navigate(DEFAULT_ROUTE[user.role], { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the initial administrator.");
    } finally { setBusy(false); }
  }

  async function registerAccount(event: FormEvent) {
    event.preventDefault(); setError(null); setBusy(true);
    try {
      await authApi.register({ email: registerEmail.trim(), name: registerName.trim(), role: registerRole, password: registerPassword });
      const user = await login(registerEmail.trim(), registerPassword);
      navigate(DEFAULT_ROUTE[user.role], { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create your account.");
    } finally { setBusy(false); }
  }

  return <main className="relative grid min-h-screen place-items-center overflow-hidden bg-[#0b1020] px-4 py-10 text-white">
    <div className="pointer-events-none absolute -left-20 top-0 h-80 w-80 rounded-full bg-indigo-600/20 blur-[110px]" />
    <div className="pointer-events-none absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-cyan-500/10 blur-[120px]" />
    <section className="relative w-full max-w-md rounded-3xl border border-white/10 bg-[#11162d]/95 p-7 shadow-2xl shadow-black/40 sm:p-9">
      <div className="mb-8 flex items-center gap-3">
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-cyan-400 via-indigo-500 to-violet-500"><Sparkles size={22} /></div>
        <div><div className="text-lg font-extrabold">UrbanLens AI</div><div className="text-[10px] tracking-[0.2em] text-cyan-300">CITY INTELLIGENCE</div></div>
      </div>
      <h1 className="m-0 text-2xl font-extrabold">Welcome back</h1>
      <p className="mb-6 mt-2 text-sm leading-6 text-slate-400">Sign in to review authorized urban observations and evidence.</p>
      {(error || sessionError) && <p role="alert" className="mb-4 rounded-xl border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-200">{error ?? sessionError}</p>}
      {showRegistration ? <form onSubmit={(event) => void registerAccount(event)}>
        <p className="mb-4 rounded-xl border border-cyan-300/15 bg-cyan-300/5 p-3 text-xs leading-5 text-cyan-100">Create your account, choose a role, and you’ll be signed in. New accounts appear in the Administrator’s User Management page. Administrator access is assigned by an existing administrator.</p>
        <label className="mb-4 block text-xs font-semibold text-slate-300">Full name
          <input required maxLength={120} autoComplete="name" value={registerName} onChange={(event) => setRegisterName(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#0b1020] px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/60" placeholder="Your name" />
        </label>
        <label className="mb-4 block text-xs font-semibold text-slate-300">Email address
          <input required type="email" autoComplete="email" value={registerEmail} onChange={(event) => setRegisterEmail(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#0b1020] px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/60" placeholder="name@example.com" />
        </label>
        <label className="mb-4 block text-xs font-semibold text-slate-300">Role
          <select value={registerRole} onChange={(event) => setRegisterRole(event.target.value as typeof registerRole)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#0b1020] px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/60">
            <option value="analyst">Urban Analyst</option><option value="reviewer">Reviewer</option><option value="viewer">Viewer</option>
          </select>
        </label>
        <label className="mb-5 block text-xs font-semibold text-slate-300">Password (at least 12 characters)
          <input required minLength={12} autoComplete="new-password" type="password" value={registerPassword} onChange={(event) => setRegisterPassword(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#0b1020] px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/60" placeholder="Create a password" />
        </label>
        <button type="submit" disabled={busy} className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-4 py-3 text-sm font-bold text-white disabled:opacity-60">{busy ? "Creating account…" : "Create account and sign in"}</button>
        <button type="button" onClick={() => { setShowRegistration(false); setError(null); }} className="mt-3 w-full py-2 text-xs text-slate-400 hover:text-white">Back to sign in</button>
      </form> : showSetup ? <form onSubmit={(event) => void setupAdministrator(event)}>
        <p className="mb-4 rounded-xl border border-cyan-300/15 bg-cyan-300/5 p-3 text-xs leading-5 text-cyan-100">Create the first platform administrator. After signing in, open User Management to create Urban Analyst, Reviewer, and Viewer accounts.</p>
        <label className="mb-4 block text-xs font-semibold text-slate-300">Administrator name
          <input required maxLength={120} autoComplete="name" value={setupName} onChange={(event) => setSetupName(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#0b1020] px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/60" placeholder="Your name" />
        </label>
        <label className="mb-4 block text-xs font-semibold text-slate-300">Email address
          <input required type="email" autoComplete="email" value={setupEmail} onChange={(event) => setSetupEmail(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#0b1020] px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/60" placeholder="name@example.com" />
        </label>
        <label className="mb-5 block text-xs font-semibold text-slate-300">Password (at least 12 characters)
          <input required minLength={12} autoComplete="new-password" type="password" value={setupPassword} onChange={(event) => setSetupPassword(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#0b1020] px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/60" placeholder="Create a password" />
        </label>
        <button type="submit" disabled={busy} className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-4 py-3 text-sm font-bold text-white disabled:opacity-60">{busy ? "Creating account…" : "Create Administrator"}</button>
        <button type="button" onClick={() => { setShowSetup(false); setError(null); }} className="mt-3 w-full py-2 text-xs text-slate-400 hover:text-white">Back to sign in</button>
      </form> : <form onSubmit={(event) => void submit(event)} noValidate>
        <label className="mb-4 block text-xs font-semibold text-slate-300">Email address
          <input autoComplete="username" type="email" value={email} onChange={(event) => setEmail(event.target.value)} onBlur={() => setEmailTouched(true)} aria-invalid={showEmailError}
            className="mt-2 w-full rounded-xl border border-white/10 bg-[#0b1020] px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-cyan-400/60" placeholder="name@example.com" />
          {showEmailError && <span className="mt-1 block text-[11px] text-red-300">Enter a valid email address.</span>}
        </label>
        <label className="mb-5 block text-xs font-semibold text-slate-300">Password
          <span className="mt-2 flex rounded-xl border border-white/10 bg-[#0b1020] focus-within:border-cyan-400/60">
            <LockKeyhole className="ml-4 mt-3.5 shrink-0 text-slate-500" size={16} />
            <input autoComplete="current-password" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} aria-invalid={submitted && !passwordValid}
              className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm text-white outline-none placeholder:text-slate-600" placeholder="Enter your password" />
            <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"} className="px-4 text-slate-400 hover:text-white">{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
          </span>
        </label>
        <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-900/30 transition hover:brightness-110 disabled:cursor-wait disabled:opacity-60">
          <MapPinned size={16} /> {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      }
      {registrationEnabled && !showSetup && !showRegistration && <button type="button" onClick={() => { setShowRegistration(true); setError(null); }} className="mt-4 w-full rounded-xl border border-white/10 px-4 py-3 text-sm font-semibold text-cyan-200 hover:bg-white/5">New user? Create an account</button>}
      {setupRequired && !showSetup && !showRegistration && <button type="button" onClick={() => { setShowSetup(true); setError(null); }} className="mt-3 w-full rounded-xl border border-white/10 px-4 py-3 text-sm font-semibold text-violet-200 hover:bg-white/5">First time here? Create the initial administrator</button>}
      <p className="mb-0 mt-6 border-t border-white/8 pt-4 text-[11px] leading-5 text-slate-500">Demo observations are simulated and are not real Street View imagery or an official property register.</p>
      {API_MODE === "aws" && <p className="mb-0 mt-2 text-[11px] leading-5 text-amber-200/80">Cloud data is served by a separate public read-only API. This login does not add server-side roles to that cloud API.</p>}
    </section>
  </main>;
}
