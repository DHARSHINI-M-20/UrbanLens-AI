import { Search, X } from "lucide-react";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
}

export default function SearchBar({ value, onChange }: SearchBarProps) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-2.5">
      <Search size={16} className="shrink-0 text-slate-500" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search building ID, street, OCR..."
        className="w-full bg-transparent text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none"
      />
      {value && (
        <button onClick={() => onChange("")} className="shrink-0 text-slate-500 hover:text-white">
          <X size={15} />
        </button>
      )}
    </div>
  );
}
