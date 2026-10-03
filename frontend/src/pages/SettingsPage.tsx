export default function SettingsPage() {
  return (
    <div>
      <div className="mb-5">
        <span className="text-[10px] font-bold tracking-widest text-cyan-400">PREFERENCES</span>
        <h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Settings</h1>
        <p className="m-0 mt-1 text-[13px] text-slate-500">Prototype preference display. These values do not change backend behavior.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
          <h3 className="m-0 mb-2 text-sm font-bold text-white">Notification preferences</h3>
          <p className="m-0 text-xs leading-5 text-slate-400">Not connected. Notification toggles are not persisted and no email or notification service is configured.</p>
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
          <h3 className="m-0 mb-2 text-sm font-bold text-white">Pipeline preferences</h3>
          <p className="m-0 text-xs leading-5 text-slate-400">Auto-refresh and escalation threshold are not configurable from this dashboard. Routing uses backend configuration; changing a display value would not affect it.</p>
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5 lg:col-span-2">
          <h3 className="m-0 mb-1 text-sm font-bold text-white">About UrbanLens AI</h3>
          <p className="m-0 text-xs leading-6 text-slate-500">
            UrbanLens AI demonstrates a street-level observation workflow. The seeded dashboard dataset is
            simulated and does not contain real Google Street View imagery or an authoritative property register.
            Local provider and Bedrock integration code exists, but this page does not claim measured accuracy or
            operational cloud escalation.
          </p>
        </div>
      </div>
    </div>
  );
}
