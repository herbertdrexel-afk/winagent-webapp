import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type SyncResult, BASE, token } from "../api";
import { BarChart2, FileDown, RefreshCw } from "lucide-react";

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
function fmtAxis(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toLocaleString("de-AT", { maximumFractionDigits: 1 }) + "M";
  if (n >= 1_000)     return (n / 1_000).toLocaleString("de-AT", { maximumFractionDigits: 0 }) + "k";
  return String(n);
}
function yearStart() { return new Date().getFullYear() + "-01-01"; }
function today()     { return new Date().toISOString().slice(0, 10); }

// ── Umsatz Balkendiagramm ──────────────────────────────────────────────────
const C_CURR = "#2563eb";   // Aktuell — WinAgent-Blau
const C_PREV = "#93c5fd";   // Vorjahr  — helles Blau

function niceMax(val: number): number {
  if (val === 0) return 100;
  const mag = Math.pow(10, Math.floor(Math.log10(val)));
  return Math.ceil(val / mag) * mag;
}

function TurnoverChart({ rows }: { rows: StatRow[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<{
    x: number; y: number; row: StatRow;
  } | null>(null);

  const ML = 62, MR = 16, MT = 16, MB = 44;
  const BAR_W   = 26;
  const GAP_IN  = 4;
  const GAP_OUT = 28;
  const GROUP_W = BAR_W * 2 + GAP_IN + GAP_OUT;
  const H       = 200;
  const chartW  = Math.max(300, rows.length * GROUP_W);
  const SVG_W   = ML + chartW + MR;
  const SVG_H   = MT + H + MB;

  const maxVal  = Math.max(...rows.flatMap(r => [r.curr_turnover, r.prev_turnover]), 1);
  const yMax    = niceMax(maxVal);
  const TICKS   = 4;
  const scaleY  = (v: number) => H - (v / yMax) * H;

  function groupX(i: number) { return ML + i * GROUP_W + GAP_OUT / 2; }

  function handleMouseMove(e: React.MouseEvent<SVGElement>, row: StatRow) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, row });
  }

  return (
    <div className="relative">
      {/* Legend */}
      <div className="flex items-center gap-5 px-5 pb-2 pt-1">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm inline-block" style={{ background: C_CURR }} />
          <span className="text-xs text-gray-600">Aktuell</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm inline-block" style={{ background: C_PREV }} />
          <span className="text-xs text-gray-600">Vorjahr</span>
        </div>
      </div>

      <div className="overflow-x-auto pb-1">
        <svg
          ref={svgRef}
          width={SVG_W}
          height={SVG_H}
          style={{ display: "block", minWidth: SVG_W }}
          onMouseLeave={() => setTooltip(null)}
        >
          {/* Gridlines + Y-axis labels */}
          {Array.from({ length: TICKS + 1 }, (_, i) => {
            const v  = (yMax / TICKS) * i;
            const gy = MT + scaleY(v);
            return (
              <g key={i}>
                <line x1={ML} x2={ML + chartW} y1={gy} y2={gy}
                  stroke={i === 0 ? "#c3c2b7" : "#e5e7eb"} strokeWidth={i === 0 ? 1 : 0.5} />
                <text x={ML - 6} y={gy + 4} textAnchor="end"
                  fontSize={10} fill="#898781" fontFamily="system-ui, sans-serif">
                  {fmtAxis(v)}
                </text>
              </g>
            );
          })}

          {/* Bars */}
          {rows.map((row, i) => {
            const gx      = groupX(i);
            const xPrev   = gx;
            const xCurr   = gx + BAR_W + GAP_IN;
            const hPrev   = Math.max((row.prev_turnover / yMax) * H, 1);
            const hCurr   = Math.max((row.curr_turnover / yMax) * H, 1);
            const yPrev   = MT + H - hPrev;
            const yCurr   = MT + H - hCurr;
            const baseY   = MT + H;

            return (
              <g key={row.code}
                onMouseMove={(e) => handleMouseMove(e, row)}
                onMouseLeave={() => setTooltip(null)}
                style={{ cursor: "default" }}
              >
                {/* Invisible hit target */}
                <rect x={gx - 2} y={MT} width={BAR_W * 2 + GAP_IN + 4} height={H + 2} fill="transparent" />

                {/* Vorjahr bar */}
                <rect x={xPrev} y={yPrev} width={BAR_W} height={hPrev}
                  rx={3} ry={3} fill={C_PREV} />
                {/* Clip bottom radius */}
                <rect x={xPrev} y={yPrev + hPrev - 4} width={BAR_W} height={4} fill={C_PREV} />

                {/* Aktuell bar */}
                <rect x={xCurr} y={yCurr} width={BAR_W} height={hCurr}
                  rx={3} ry={3} fill={C_CURR} />
                <rect x={xCurr} y={yCurr + hCurr - 4} width={BAR_W} height={4} fill={C_CURR} />

                {/* X-axis label */}
                <text x={gx + BAR_W + GAP_IN / 2} y={baseY + 14}
                  textAnchor="middle" fontSize={11} fill="#374151"
                  fontWeight={600} fontFamily="system-ui, sans-serif">
                  {row.code}
                </text>
                <text x={gx + BAR_W + GAP_IN / 2} y={baseY + 27}
                  textAnchor="middle" fontSize={9} fill="#9ca3af"
                  fontFamily="system-ui, sans-serif">
                  {row.name.length > 12 ? row.name.slice(0, 11) + "…" : row.name}
                </text>
              </g>
            );
          })}

          {/* Baseline */}
          <line x1={ML} x2={ML + chartW} y1={MT + H} y2={MT + H}
            stroke="#c3c2b7" strokeWidth={1} />
        </svg>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-10 pointer-events-none bg-white border border-gray-200 rounded-xl shadow-lg px-3 py-2 text-xs"
          style={{
            left: Math.min(tooltip.x + 12, 340),
            top: tooltip.y - 10,
            minWidth: 160,
          }}
        >
          <div className="font-semibold text-gray-800 mb-1">{tooltip.row.name}</div>
          <div className="flex justify-between gap-4">
            <span className="text-gray-500">Aktuell</span>
            <span className="font-medium" style={{ color: C_CURR }}>{fmt(tooltip.row.curr_turnover)}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-gray-500">Vorjahr</span>
            <span className="text-gray-600">{fmt(tooltip.row.prev_turnover)}</span>
          </div>
          {tooltip.row.prev_turnover > 0 && (
            <div className="flex justify-between gap-4 mt-0.5 pt-0.5 border-t border-gray-100">
              <span className="text-gray-500">Änderung</span>
              <span className={
                tooltip.row.curr_turnover >= tooltip.row.prev_turnover
                  ? "text-emerald-700 font-medium"
                  : "text-red-600 font-medium"
              }>
                {fmtPct(((tooltip.row.curr_turnover - tooltip.row.prev_turnover) / tooltip.row.prev_turnover) * 100)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate();
  const [syncing, setSyncing]       = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [lastSync, setLastSync]     = useState<string | null>(null);
  const [stats, setStats]           = useState<StatData | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [downloading, setDownloading]   = useState(false);

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
      const res = await fetch(
        `${BASE}/stats/supplier-summary?period_from=${yearStart()}&period_to=${today()}`,
        { headers: h },
      );
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
      const res = await fetch(
        `${BASE}/stats/supplier-summary/pdf?period_from=${yearStart()}&period_to=${today()}`,
        { headers: h },
      );
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
    { ct: 0, pt: 0, cc: 0, pc: 0 },
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-gray-800">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Willkommen bei WinAgent</p>
      </div>

      {/* Umsatz chart + table in one card */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">

        {/* Card header */}
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

        {/* Chart area */}
        {statsLoading ? (
          <div className="h-[260px] flex items-center justify-center text-gray-400 text-sm">Lade…</div>
        ) : !stats || stats.rows.length === 0 ? (
          <div className="h-[160px] flex items-center justify-center text-gray-400 text-sm">Keine Daten</div>
        ) : (
          <TurnoverChart rows={stats.rows} />
        )}

        {/* Table */}
        <div className="overflow-x-auto border-t border-gray-100">
          <table className="w-full text-sm min-w-[540px]">
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
