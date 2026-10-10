import { Link } from "react-router-dom";
import { ShieldX } from "lucide-react";

export default function AccessDeniedPage() {
  return <main className="grid min-h-screen place-items-center bg-[#0b1020] p-6 text-white"><section className="max-w-md rounded-3xl border border-white/10 bg-white/[0.04] p-8 text-center">
    <ShieldX className="mx-auto text-amber-300" size={38} /><h1 className="mt-4 text-2xl font-extrabold">Access denied</h1>
    <p className="text-sm leading-6 text-slate-400">Your account does not have permission to open this page. Contact an administrator if you need access.</p>
    <Link className="mt-3 inline-flex rounded-xl bg-cyan-500 px-4 py-2.5 text-sm font-bold text-slate-950" to="/">Return to dashboard</Link>
  </section></main>;
}
