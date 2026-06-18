import { useEffect, useState } from "react";
import { FileDown, RefreshCw } from "lucide-react";
import { BASE, token } from "../api";
import DateRangePicker from "../components/DateRangePicker";

interface StatRow {
  code: string;
  name: string;
  curr_turnover: number;
  curr_commission: number;
  prev_turnover: number;
  prev_commission: number;
  comm_diff: number;
  comm_pct: number | null;
}
interface StatData {
  period_from: string;
  period_to: string;
  rows: StatRow[];
}

function fmt(n: number, zero = "0") {
  if (n === 0) return zero;
  return n.toLocaleString("de-AT", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtPct(pct: number | null) {
  if (pct === null) return "***,*%";
  return (pct >= 0 ? "+" : "") + pct.toFixed(1).replace(".", ",") + "%";
}

function yearStart() { return new Date().getFullYear() + "-01-01"; }
function today() { return new Date().toISOString().slice(0, 10); }

export default function SupplierStats() {
  const [from, setFrom] = useState(yearStart());
  const [to, setTo] = useState(today());
  const [data, setData] = useState<StatData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const headers: Record<string, string> = {};
      const t = token.get();
      if (t) headers["Authorization"] = `Bearer ${t}`;
      const res = await fetch(`${BASE}/stats/supplier-summary?period_from=${from}&period_to=${to}`, { headers });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setData(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setLoading(false);
    }
  }

  async function downloadPdf() {
    setDownloading(true);
    try {
      const headers: Record<string, string> = {};
      const t = token.get();
      if (t) headers["Authorization"] = `Bearer ${t}`;
      const res = await fetch(`${BASE}/stats/supplier-summary/pdf?period_from=${from}&period_to=${to}`, { headers });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `Lieferant_Statistik_${from}_${to}.pdf`;
      a.click();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Fehler");
    } finally {
      setDownloading(false);
    }
  }

  const totals = data?.rows.reduce(
    (s, r) => ({
      curr_turnover: s.curr_turnover + r.curr_turnover,
      prev_turnover: s.prev_turnover + r.prev_turnover,
      curr_commission: s.curr_commission + r.curr_commission,
      prev_commission: s.prev_commission + r.prev_commission,
    }),
    { curr_turnover: 0, prev_turnover: 0, curr_commission: 0, prev_commission: 0 }
  );
  const tot_diff = totals ? totals.curr_commission - totals.prev_commission : 0;
  const tot_pct = totals?.prev_commission ? ((totals.curr_commission / totals.prev_commission - 1) * 100) : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-semibold text-gray-800">Lieferanten Statistik</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <DateRangePicker from={from} to={to} onChange={(f, t) => { setFrom(f); setTo(t); }} />
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1.5 bg-[#1a3a5c] text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-[#1a3a5c]/80 disabled:opacity-50 transition-colors">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Laden
          </button>
          <button onClick={downloadPdf} disabled={downloading || !data}
            className="flex items-center gap-1.5 border border-[#1a3a5c] text-[#1a3a5c] px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-[#1a3a5c]/10 disabled:opacity-50 transition-colors">
            <FileDown size={14} />
            {downloading ? "Generiere…" : "PDF"}
          </button>
        </div>
      </div>

      {error && <div className="text-red-600 text-sm">Fehler: {error}</div>}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm whitespace-nowrap">
          <thead>
            {/* Group header */}
            <tr className="bg-[#1a3a5c] text-white">
              <th className="px-4 py-2 text-left font-medium" rowSpan={2}>Lieferant</th>
              <th className="px-3 py-2 text-center font-medium border-l border-white/20" colSpan={2}>Umsatz</th>
              <th className="px-3 py-2 text-center font-medium border-l border-white/20" colSpan={2}>Provision Vorjahr / Aktuell</th>
              <th className="px-3 py-2 text-center font-medium border-l border-white/20" colSpan={2}>Differenz</th>
            </tr>
            <tr className="bg-[#2d5a8e] text-white text-xs">
              <th className="px-3 py-1.5 text-right border-l border-white/20">Vorjahr</th>
              <th className="px-3 py-1.5 text-right">Aktuell</th>
              <th className="px-3 py-1.5 text-right border-l border-white/20">Vorjahr</th>
              <th className="px-3 py-1.5 text-right">Aktuell</th>
              <th className="px-3 py-1.5 text-right border-l border-white/20">Betrag</th>
              <th className="px-3 py-1.5 text-right">%</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Lade…</td></tr>
            ) : !data ? null : data.rows.map((r, i) => (
              <tr key={r.code} className={i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40"}>
                <td className="px-4 py-2 font-medium text-gray-800">{r.name}</td>
                <td className="px-3 py-2 text-right text-gray-600">{fmt(r.prev_turnover)}</td>
                <td className="px-3 py-2 text-right font-medium">{fmt(r.curr_turnover)}</td>
                <td className="px-3 py-2 text-right text-gray-600 border-l border-gray-100">{fmt(r.prev_commission)}</td>
                <td className="px-3 py-2 text-right font-semibold text-emerald-700">{fmt(r.curr_commission)}</td>
                <td className={`px-3 py-2 text-right border-l border-gray-100 font-medium ${r.comm_diff < 0 ? "text-red-600" : r.comm_diff > 0 ? "text-emerald-700" : "text-gray-400"}`}>
                  {r.comm_diff !== 0 ? (r.comm_diff > 0 ? "+" : "") + fmt(r.comm_diff) : "0"}
                </td>
                <td className={`px-3 py-2 text-right text-xs ${r.comm_pct === null ? "text-gray-400" : r.comm_pct < 0 ? "text-red-600" : "text-emerald-700"}`}>
                  {fmtPct(r.comm_pct)}
                </td>
              </tr>
            ))}
          </tbody>
          {totals && (
            <tfoot>
              <tr className="border-t-2 border-[#1a3a5c] bg-[#f0f5fb] font-semibold">
                <td className="px-4 py-2">Gesamt</td>
                <td className="px-3 py-2 text-right">{fmt(totals.prev_turnover)}</td>
                <td className="px-3 py-2 text-right">{fmt(totals.curr_turnover)}</td>
                <td className="px-3 py-2 text-right border-l border-gray-200">{fmt(totals.prev_commission)}</td>
                <td className="px-3 py-2 text-right text-emerald-700">{fmt(totals.curr_commission)}</td>
                <td className={`px-3 py-2 text-right border-l border-gray-200 ${tot_diff < 0 ? "text-red-600" : "text-emerald-700"}`}>
                  {tot_diff !== 0 ? (tot_diff > 0 ? "+" : "") + fmt(tot_diff) : "0"}
                </td>
                <td className={`px-3 py-2 text-right text-xs ${tot_pct === null ? "text-gray-400" : tot_pct < 0 ? "text-red-600" : "text-emerald-700"}`}>
                  {fmtPct(tot_pct)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
