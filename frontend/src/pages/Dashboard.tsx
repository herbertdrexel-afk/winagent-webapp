import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BASE, token } from "../api";
import { useT } from "../context/LocaleContext";
import { BarChart2, FileDown } from "lucide-react";

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
  return n.toLocaleString("de-DE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtPct(pct: number | null) {
  if (pct === null) return "–";
  return (pct >= 0 ? "+" : "") + pct.toFixed(1).replace(".", ",") + "%";
}
function fmtAxis(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toLocaleString("de-DE", { maximumFractionDigits: 1 }) + "M";
  if (n >= 1_000)     return (n / 1_000).toLocaleString("de-DE", { maximumFractionDigits: 0 }) + "k";
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
  const t = useT();
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
          <span className="text-xs text-gray-600">{t.dashboard.currTurnover}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm inline-block" style={{ background: C_PREV }} />
          <span className="text-xs text-gray-600">{t.dashboard.prevTurnover}</span>
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
            <span className="text-gray-500">{t.dashboard.currTurnover}</span>
            <span className="font-medium" style={{ color: C_CURR }}>{fmt(tooltip.row.curr_turnover)}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-gray-500">{t.dashboard.prevTurnover}</span>
            <span className="text-gray-600">{fmt(tooltip.row.prev_turnover)}</span>
          </div>
          {tooltip.row.prev_turnover > 0 && (
            <div className="flex justify-between gap-4 mt-0.5 pt-0.5 border-t border-gray-100">
              <span className="text-gray-500">{t.dashboard.commChange}</span>
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

// ── Umsatzanteil Donut (Kuchendiagramm) ────────────────────────────────────
const PIE_COLORS = [
  "#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#64748b", "#0ea5e9",
  "#a3e635", "#e11d48",
];

function arcPath(cx: number, cy: number, rO: number, rI: number, a0: number, a1: number) {
  const pt = (r: number, a: number) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const [x1, y1] = pt(rO, a0);
  const [x2, y2] = pt(rO, a1);
  const [x3, y3] = pt(rI, a1);
  const [x4, y4] = pt(rI, a0);
  return `M${x1},${y1} A${rO},${rO} 0 ${large} 1 ${x2},${y2} L${x3},${y3} A${rI},${rI} 0 ${large} 0 ${x4},${y4} Z`;
}

function TurnoverDonut({ rows }: { rows: StatRow[] }) {
  const t = useT();
  const [hover, setHover] = useState<number | null>(null);

  const data = rows
    .map((r) => ({ code: r.code, name: r.name, value: r.curr_turnover }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value);
  const total = data.reduce((s, d) => s + d.value, 0);

  if (total === 0) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm py-8">{t.common.noData}</div>;
  }

  const size = 176, stroke = 40, rO = size / 2, rI = size / 2 - stroke, cx = size / 2, cy = size / 2;
  const TAU = Math.PI * 2;
  let acc = -Math.PI / 2;
  const segs = data.map((d, i) => {
    const frac = d.value / total;
    const a0 = acc, a1 = acc + frac * TAU;
    acc = a1;
    return { ...d, i, frac, a0, a1, color: PIE_COLORS[i % PIE_COLORS.length] };
  });
  const single = segs.length === 1;

  const center = hover != null ? segs[hover] : null;

  return (
    <div>
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-1 pb-2">
        {t.dashboard.turnoverShare}
      </div>
      <div className="flex items-start gap-3">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0"
          onMouseLeave={() => setHover(null)}>
          {single ? (
            <circle cx={cx} cy={cy} r={(rO + rI) / 2} fill="none"
              stroke={segs[0].color} strokeWidth={stroke} />
          ) : (
            segs.map((s) => (
              <path key={s.code} d={arcPath(cx, cy, rO, rI, s.a0, s.a1)}
                fill={s.color}
                stroke="#fff" strokeWidth={1.5}
                opacity={hover == null || hover === s.i ? 1 : 0.35}
                style={{ transition: "opacity .12s" }}
                onMouseEnter={() => setHover(s.i)} />
            ))
          )}
          {/* Center label */}
          <text x={cx} y={center ? cy - 6 : cy - 3} textAnchor="middle"
            fontSize={center ? 13 : 11} fontWeight={700} fill="#374151"
            fontFamily="system-ui, sans-serif">
            {center ? center.code : t.dashboard.total}
          </text>
          <text x={cx} y={center ? cy + 12 : cy + 14} textAnchor="middle"
            fontSize={center ? 11 : 12} fontWeight={600}
            fill={center ? center.color : "#111827"}
            fontFamily="system-ui, sans-serif">
            {center ? `${(center.frac * 100).toFixed(1).replace(".", ",")}%` : fmtAxis(total)}
          </text>
        </svg>

        {/* Legend */}
        <div className="flex-1 min-w-0 text-xs space-y-1 max-h-[176px] overflow-y-auto pr-1">
          {segs.map((s) => (
            <div key={s.code}
              className={`flex items-center gap-1.5 rounded px-1 py-0.5 cursor-default ${hover === s.i ? "bg-gray-100" : ""}`}
              onMouseEnter={() => setHover(s.i)} onMouseLeave={() => setHover(null)}>
              <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: s.color }} />
              <span className="font-medium text-gray-700 shrink-0" style={{ minWidth: 26 }}>{s.code}</span>
              <span className="text-gray-400 truncate flex-1">{s.name}</span>
              <span className="font-semibold text-gray-700 shrink-0 tabular-nums">
                {(s.frac * 100).toFixed(1).replace(".", ",")}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate();
  const t = useT();
  const [stats, setStats]           = useState<StatData | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [downloading, setDownloading]   = useState(false);

  useEffect(() => {
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
        <h1 className="text-2xl font-semibold text-gray-800">{t.dashboard.title}</h1>
        <p className="text-sm text-gray-500 mt-0.5">WinAgent</p>
      </div>

      {/* Umsatz chart + table in one card */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">

        {/* Card header */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-100">
          <BarChart2 size={17} className="text-[#2563eb]" />
          <h2 className="font-semibold text-gray-800">{t.dashboard.supplierStats}</h2>
          <span className="text-xs text-gray-400 ml-1">
            {yearStart().slice(0, 7).replace("-", "/")} – {today().slice(0, 7).replace("-", "/")}
          </span>
          <div className="ml-auto flex gap-2">
            <button onClick={() => navigate("/stats")}
              className="text-xs text-[#2563eb] hover:underline">{t.dashboard.details}</button>
            <button onClick={downloadPdf} disabled={downloading || !stats}
              className="flex items-center gap-1 text-xs border border-[#2563eb]/30 text-[#2563eb] px-2 py-1 rounded hover:bg-[#2563eb]/5 disabled:opacity-40">
              <FileDown size={12} />
              {downloading ? "…" : "PDF"}
            </button>
          </div>
        </div>

        {/* Chart area */}
        {statsLoading ? (
          <div className="h-[260px] flex items-center justify-center text-gray-400 text-sm">{t.common.loading}</div>
        ) : !stats || stats.rows.length === 0 ? (
          <div className="h-[160px] flex items-center justify-center text-gray-400 text-sm">{t.common.noData}</div>
        ) : (
          <div className="flex flex-col xl:flex-row xl:items-start">
            <div className="flex-1 min-w-0">
              <TurnoverChart rows={stats.rows} />
            </div>
            <div className="shrink-0 xl:w-[360px] border-t xl:border-t-0 xl:border-l border-gray-100 p-4">
              <TurnoverDonut rows={stats.rows} />
            </div>
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto border-t border-gray-100">
          <table className="w-full text-sm min-w-[540px]">
            <thead className="bg-[#2563eb] text-white text-xs">
              <tr>
                <th className="px-4 py-2 text-left font-medium">{t.dashboard.supplier}</th>
                <th className="px-3 py-2 text-right font-medium">{t.dashboard.prevTurnover}</th>
                <th className="px-3 py-2 text-right font-medium">{t.dashboard.currTurnover}</th>
                <th className="px-3 py-2 text-right font-medium">{t.dashboard.prevCommission}</th>
                <th className="px-3 py-2 text-right font-medium">{t.dashboard.currCommission}</th>
                <th className="px-3 py-2 text-right font-medium">{t.dashboard.commDiff}</th>
                <th className="px-3 py-2 text-right font-medium">%</th>
              </tr>
            </thead>
            <tbody>
              {statsLoading ? (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-400 text-sm">{t.common.loading}</td></tr>
              ) : !stats || stats.rows.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-400 text-sm">{t.common.noData}</td></tr>
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
                  <td className="px-4 py-2">{t.dashboard.total}</td>
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

    </div>
  );
}
