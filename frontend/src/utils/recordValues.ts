/** Parse a finite numeric field without converting missing or malformed values to zero. */
export function nullableNumber(value: unknown): number | null {
  if (value == null || (typeof value === "string" && value.trim() === "")) return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Convert a provider confidence in [0, 1] into a display percentage. */
export function nullablePercent(value: unknown): number | null {
  const parsed = nullableNumber(value);
  return parsed == null || parsed < 0 || parsed > 1 ? null : Math.round(parsed * 100);
}

export function hasCoordinates(latitude: number | null, longitude: number | null): boolean {
  return latitude != null && longitude != null
    && latitude >= -90 && latitude <= 90
    && longitude >= -180 && longitude <= 180;
}

export function nullableCoordinate(value: unknown, limit: number): number | null {
  const parsed = nullableNumber(value);
  return parsed != null && Math.abs(parsed) <= limit ? parsed : null;
}
