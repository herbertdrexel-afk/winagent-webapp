// Zentrale Formatierung: Datum T.M.Y, Zahlen im Format 28.222,20

/** ISO-Datum (YYYY-MM-DD) oder Date → "TT.MM.JJJJ". Leere/ungültige Werte → "". */
export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "";
  if (value instanceof Date) {
    if (isNaN(value.getTime())) return "";
    return toDMY(value.getFullYear(), value.getMonth() + 1, value.getDate());
  }
  const s = String(value).trim();
  // Reines ISO-Datum ohne/mit Zeitanteil: YYYY-MM-DD[...]
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[3]}.${m[2]}.${m[1]}`;
  // Fallback: als Date parsen
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return toDMY(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

function toDMY(y: number, m: number, d: number): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d)}.${pad(m)}.${y}`;
}

/** Zahl → "28.222,20" (Punkt als Tausender, Komma als Dezimal). */
export function formatNum(
  value: number | string | null | undefined,
  fractionDigits = 2,
): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (n == null || isNaN(n)) return "";
  return n.toLocaleString("de-DE", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}
