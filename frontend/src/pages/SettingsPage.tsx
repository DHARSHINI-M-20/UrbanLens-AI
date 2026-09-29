import { useState } from "react";

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4">
      <span className="text-[13px] font-medium text-slate-300">{label}</span>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition ${checked ? "bg-cyan-500" : "bg-white/10"}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition ${checked ? "left-[22px]" : "left-0.5"}`}
        />
      </button>
    </label>
  );
}

export default function SettingsPage() {
  const [notifPrefs, setNotifPrefs] = useState({ lowConfidence: true, newMatches: true, dailyDigest: false });
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [threshold, setThreshold] = useState(70);

  return (
    <div>
      <div className="mb-5">
        <span className="text-[10px] font-bold tracking-widest text-cyan-400">PREFERENCES</span>
        <h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Settings</h1>
        <p className="m-0 mt-1 text-[13px] text-slate-500">Configure how UrbanLens processes and alerts you.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
          <h3 className="m-0 mb-4 text-sm font-bold text-white">Notifications</h3>
          <div className="flex flex-col gap-3">
            <ToggleRow
              label="Alert on low-confidence detections"
              checked={notifPrefs.lowConfidence}
              onChange={(v) => setNotifPrefs((p) => ({ ...p, lowConfidence: v }))}
            />
            <ToggleRow
              label="Notify on new property matches"
              checked={notifPrefs.newMatches}
              onChange={(v) => setNotifPrefs((p) => ({ ...p, newMatches: v }))}
            />
            <ToggleRow
              label="Send daily digest email"
              checked={notifPrefs.dailyDigest}
              onChange={(v) => setNotifPrefs((p) => ({ ...p, dailyDigest: v }))}
            />
          </div>
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
          <h3 className="m-0 mb-4 text-sm font-bold text-white">Pipeline</h3>
          <div className="flex flex-col gap-4">
            <ToggleRow label="Auto-refresh live intelligence layer" checked={autoRefresh} onChange={setAutoRefresh} />
            <div>
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-300">VLM escalation confidence threshold</span>
                <span className="font-bold text-cyan-400">{threshold}%</span>
              </div>
              <input
                type="range"
                min={40}
                max={95}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full accent-cyan-400"
              />
              <p className="m-0 mt-2 text-[11px] text-slate-500">
                Observations below this confidence are escalated from small models to the VLM.
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5 lg:col-span-2">
          <h3 className="m-0 mb-1 text-sm font-bold text-white">About UrbanLens AI</h3>
          <p className="m-0 text-xs leading-6 text-slate-500">
            UrbanLens AI converts Google Street View panoramas into structured street-level intelligence —
            buildings, signage, streetlights and electric poles — routed through lightweight models first and
            escalated to a VLM only for uncertain observations, then matched against property and
            infrastructure records.
          </p>
        </div>
      </div>
    </div>
  );
}
