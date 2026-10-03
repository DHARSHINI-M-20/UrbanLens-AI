export interface Page<T> {
  items: T[];
  page: number;
  pageCount: number;
  total: number;
}

/** Client-side page over the already bounded API collection response. */
export function paginate<T>(items: T[], requestedPage: number, pageSize: number): Page<T> {
  const safeSize = Math.max(1, Math.floor(pageSize));
  const pageCount = Math.max(1, Math.ceil(items.length / safeSize));
  const page = Math.min(pageCount, Math.max(1, Math.floor(requestedPage)));
  return { items: items.slice((page - 1) * safeSize, page * safeSize), page, pageCount, total: items.length };
}
