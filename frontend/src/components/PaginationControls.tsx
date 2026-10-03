export default function PaginationControls({ page, pageCount, total, pageSize, onPageChange }: {
  page: number; pageCount: number; total: number; pageSize: number; onPageChange: (page: number) => void;
}) {
  if (total <= pageSize) return null;
  return <nav aria-label="Result pages" className="flex items-center justify-between gap-3 border-t border-white/8 px-4 py-3 text-xs text-slate-400">
    <span>{(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total} loaded records</span>
    <div className="flex items-center gap-2">
      <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)} className="rounded border border-white/10 px-2 py-1 disabled:opacity-40">Previous</button>
      <span>Page {page} of {pageCount}</span>
      <button type="button" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)} className="rounded border border-white/10 px-2 py-1 disabled:opacity-40">Next</button>
    </div>
  </nav>;
}
