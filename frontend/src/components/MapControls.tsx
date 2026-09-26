import { Layers3, LocateFixed, Minus, Plus } from "lucide-react";
import type L from "leaflet";

interface MapControlsProps {
  map: L.Map | null;
  center: [number, number];
  onToggleLayer: () => void;
}

export default function MapControls({ map, center, onToggleLayer }: MapControlsProps) {
  const buttons = [
    { icon: Plus, title: "Zoom in", onClick: () => map?.zoomIn() },
    { icon: Minus, title: "Zoom out", onClick: () => map?.zoomOut() },
    { icon: LocateFixed, title: "Recenter", onClick: () => map?.flyTo(center, 15, { duration: 0.8 }) },
    { icon: Layers3, title: "Toggle map layer", onClick: onToggleLayer },
  ];

  return (
    <div className="absolute right-4 top-4 z-[400] flex flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0f172a]/90 backdrop-blur-md">
      {buttons.map((btn, i) => {
        const Icon = btn.icon;
        return (
          <button
            key={btn.title}
            title={btn.title}
            onClick={btn.onClick}
            className={`flex h-9 w-9 items-center justify-center text-slate-300 transition hover:bg-white/10 hover:text-cyan-400 ${
              i !== buttons.length - 1 ? "border-b border-white/10" : ""
            }`}
          >
            <Icon size={16} />
          </button>
        );
      })}
    </div>
  );
}
