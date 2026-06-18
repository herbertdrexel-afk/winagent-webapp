import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type SyncResult, BASE, token } from "../api";
import { FileText, Receipt, RefreshCw, ArrowRight, BarChart2, FileDown } from "lucide-react";

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
interface StatData { period_from: string; period_to: string; rows: StatRow[] }

function fmt(n: number) {
  if (n === 0) return "0";
  return n.toLocaleString("de-AT", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtPct(pct: number | null) {
  if (pct === null) return "–";
  return (pct >= 0 ? "+" : "") + pct.toFixed(1).replace(".", ",") + "%";
}
function yearStart() { return new Date().getFullYear() + "-01-01"; }
function today() { return new Date().toISOString().slice(0, 10); }

export default function Dashboard() {
  const navigate = useNavigate();
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [stats, setStats] = useState<StatData | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.sync.status().then((s) => setLastSync(s.last_sync)).catch(() => {});
    loadStats();
  }, []);

  async function loadStats() {
    setStatsLoading(true);
    try {
      const h: Record<string, string> = {};
      const t = token.get();
      if (t) h["Authorization"] = `Bearer ${t}`;
      const res = await fetch(`${BASE}/stats/supplier-summary?period_from=${yearStart()}&period_to=${today()}`, { headers: h });
      if (res.ok) setStats(await res.json());
    } catch { /* silent */ } finally { setStatsLoading(false); }
  }

  async function runSync() {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await api.sync.customers();
      setSyncResult(result);
      const s = await api.sync.status();
      setLastSync(s.last_sync);
    } catch (e: unknown) {
      setSyncResult({ ok: false, total: 0, message: e instanceof Error ? e.message : "Fehler" });
    } finally { setSyncing(false); }
  }

  async function downloadPdf() {
    setDownloading(true);
    try {
      const h: Record<string, string> = {};
      const t = token.get();
      if (t) h["Authorization"] = `Bearer ${t}`;
      const res = await fetch(`${BASE}/stats/supplier-summary/pdf?period_from=${yearStart()}&period_to=${today()}`, { headers: h });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `Lieferant_Statistik_${today()}.pdf`;
      a.click();
    } catch (e: unknown) { alert(e instanceof Error ? e.message : "Fehler"); }
    finally { setDownloading(false); }
  }

  const totals = stats?.rows.reduce(
    (s, r) => ({ ct: s.ct + r.curr_turnover, pt: s.pt + r.prev_turnover, cc: s.cc + r.curr_commission, pc: s.pc + r.prev_commission }),
    { ct: 0, pt: 0, cc: 0, pc: 0 }
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-gray-800">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Willkommen bei WinAgent</p>
      </div>

      {/* Quick tiles */}
      <div className="grid grid-cols-2 xl:grid-cols-3 gap-4">
        {[
          { label: "Rechnungen", sub: "Transaktionen verwalten", icon: FileText, color: "bg-emerald-50 text-emerald-700 border-emerald-200", iconBg: "bg-emerald-100", to: "/transactions" },
          { label: "Provisionsrechnungen", sub: "PR-Liste & Nachdruck", icon: Receipt, color: "bg-violet-50 text-violet-700 border-violet-200", iconBg: "bg-violet-100", to: "/commission-invoices" },
          { label: "Statistik", sub: "Lieferanten Übersicht", icon: BarChart2, color: "bg-blue-50 text-blue-700 border-blue-200", iconBg: "bg-blue-100", to: "/stats" },
        ].map(({ label, sub, icon: Icon, color, iconBg, to }) => (
          <button key={to} onClick={() => navigate(to)}
            className={`flex items-center gap-4 p-5 rounded-xl border text-left hover:shadow-md transition-all ${color}`}>
            <div className={`p-2.5 rounded-lg shrink-0 ${iconBg}`}><Icon size={22} /></div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-base leading-tight">{label}</div>
              <div className="text-xs mt-1 opacity-70">{sub}</div>
            </div>
            <ArrowRight size={16} className="opacity-40 shrink-0" />
          </button>
        ))}
      </div>

      {/* Statistics preview */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-100">
          <BarChart2 size={17} className="text-[#2563eb]" />
          <h2 className="font-semibold text-gray-800">Lieferanten Statistik</h2>
          <span className="text-xs text-gray-400 ml-1">
            {yearStart().slice(0, 7).replace("-", "/")} – {today().slice(0, 7).replace("-", "/")}
          </span>
          <div className="ml-auto flex gap-2">
            <button onClick={() => navigate("/stats")}
              className="text-xs text-[#2563eb] hover:underline">Details →</button>
            <button onClick={downloadPdf} disabled={downloading || !stats}
              className="flex items-center gap-1 text-xs border border-[#2563eb]/30 text-[#2563eb] px-2 py-1 rounded hover:bg-[#2563eb]/5 disabled:opacity-40">
              <FileDown size={12} />
              {downloading ? "…" : "PDF"}
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#2563eb] text-white text-xs">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Lieferant</th>
                <th className="px-3 py-2 text-right font-medium">Umsatz Vorjahr</th>
                <th className="px-3 py-2 text-right font-medium">Umsatz Aktuell</th>
                <th className="px-3 py-2 text-right font-medium">Provision Vorjahr</th>
                <th className="px-3 py-2 text-right font-medium">Provision Aktuell</th>
                <th className="px-3 py-2 text-right font-medium">Differenz</th>
                <th className="px-3 py-2 text-right font-medium">%</th>
              </tr>
            </thead>
            <tbody>
              {statsLoading ? (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-400 text-sm">Lade…</td></tr>
              ) : !stats || stats.rows.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-400 text-sm">Keine Daten</td></tr>
              ) : stats.rows.map((r, i) => (
                <tr key={r.code} className={i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/30"}>
                  <td className="px-4 py-1.5 font-medium text-gray-800">{r.name}</td>
                  <td className="px-3 py-1.5 text-right text-gray-500 text-xs">{fmt(r.prev_turnover)}</td>
                  <td className="px-3 py-1.5 text-right font-medium">{fmt(r.curr_turnover)}</td>
                  <td className="px-3 py-1.5 text-right text-gray-500 text-xs">{fmt(r.prev_commission)}</td>
                  <td className="px-3 py-1.5 text-right font-semibold text-emerald-700">{fmt(r.curr_commission)}</td>
                  <td className={`px-3 py-1.5 text-right text-xs font-medium ${r.comm_diff < 0 ? "text-red-600" : r.comm_diff > 0 ? "text-emerald-700" : "text-gray-400"}`}>
                    {r.comm_diff !== 0 ? (r.comm_diff > 0 ? "+" : "") + fmt(r.comm_diff) : "–"}
                  </td>
                  <td className={`px-3 py-1.5 text-right text-xs ${r.comm_pct === null ? "text-gray-400" : r.comm_pct < 0 ? "text-red-600" : "text-emerald-700"}`}>
                    {fmtPct(r.comm_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
            {totals && (
              <tfoot>
                <tr className="border-t-2 border-[#2563eb] bg-[#f0f5fb] font-semibold text-sm">
                  <td className="px-4 py-2">Gesamt</td>
                  <td className="px-3 py-2 text-right text-gray-600">{fmt(totals.pt)}</td>
                  <td className="px-3 py-2 text-right">{fmt(totals.ct)}</td>
                  <td className="px-3 py-2 text-right text-gray-600">{fmt(totals.pc)}</td>
                  <td className="px-3 py-2 text-right text-emerald-700">{fmt(totals.cc)}</td>
                  <td className={`px-3 py-2 text-right text-xs ${(totals.cc - totals.pc) < 0 ? "text-red-600" : "text-emerald-700"}`}>
                    {totals.cc - totals.pc !== 0 ? ((totals.cc - totals.pc) > 0 ? "+" : "") + fmt(totals.cc - totals.pc) : "–"}
                  </td>
                  <td className={`px-3 py-2 text-right text-xs ${totals.pc ? (((totals.cc / totals.pc) - 1) < 0 ? "text-red-600" : "text-emerald-700") : "text-gray-400"}`}>
                    {fmtPct(totals.pc ? ((totals.cc / totals.pc) - 1) * 100 : null)}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>

      {/* Reybex Sync — compact */}
      <div className="bg-white rounded-xl border border-gray-200 px-5 py-3 flex items-center gap-4 flex-wrap">
        <RefreshCw size={16} className="text-[#2563eb] shrink-0" />
        <span className="font-medium text-sm text-gray-700">Reybex Kunden-Sync</span>
        <button onClick={runSync} disabled={syncing}
          className="flex items-center gap-1.5 border border-[#2563eb] text-[#2563eb] px-3 py-1 rounded-lg text-xs font-medium hover:bg-[#2563eb]/5 disabled:opacity-50 transition-colors">
          <RefreshCw size={12} className={syncing ? "animate-spin" : ""} />
          {syncing ? "Synchronisiere…" : "Jetzt synchronisieren"}
        </button>
        {lastSync && <span className="text-xs text-gray-400">Zuletzt: {new Date(lastSync).toLocaleString("de-AT")}</span>}
        <span className="text-xs text-gray-300">· Automatisch stündlich</span>
        {syncResult && (
          <span className={`text-xs px-2 py-0.5 rounded-full ${syncResult.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"}`}>
            {syncResult.ok ? `✓ ${syncResult.total} Kunden` : `✗ ${syncResult.message}`}
          </span>
        )}
      </div>
    </div>
  );
}
