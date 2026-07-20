import { useEffect, useState } from "react";
import { FileDown, RefreshCw } from "lucide-react";
import { BASE, token } from "../api";
import { useT } from "../context/LocaleContext";
import DateRangePicker from "../components/DateRangePicker";

// ── helpers ──────────────────────────────────────────────────────────────────
function fmt(n: number, zero = "0") {
  if (n === 0) return zero;
  return n.toLocaleString("de-DE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtPct(pct: number | null) {
  if (pct === null) return "***%";
  return (pct >= 0 ? "+" : "") + pct.toFixed(1).replace(".", ",") + "%";
}
function yearStart() { return new Date().getFullYear() + "-01-01"; }
function today()     { return new Date().toISOString().slice(0, 10); }
function authHeaders(): Record<string, string> {
  const tok = token.get();
  return tok ? { Authorization: `Bearer ${tok}` } : {};
}

// ── types ────────────────────────────────────────────────────────────────────
interface SupplierRow { code: string; name: string; curr_turnover: number; curr_commission: number; prev_turnover: number; prev_commission: number; comm_diff: number; comm_pct: number | null; }
interface CustomerRow {
  customer_name: string; customer_city?: string; country_code?: string; zip?: string;
  curr_turnover: number; curr_provision: number; prev_turnover: number;
  du_pr_pct: number | null; share_pct: number; growth_pct: number | null;
}

function custLabel(r: CustomerRow): string {
  const loc = [r.zip, r.customer_city].filter(Boolean).join(" ").trim();
  const withCc = loc ? (r.country_code ? `${r.country_code}-${loc}` : loc) : "";
  return withCc ? `${r.customer_name}, ${withCc}` : r.customer_name;
}
interface DetailQRow  { label: string; prev_turnover: number; budget_turnover: number; curr_turnover: number; prev_commission: number; budget_commission: number; curr_commission: number; }
interface DetailSupplier { code: string; name: string; rows: DetailQRow[]; }

// ── Tab: Lieferant Statistik ──────────────────────────────────────────────────
function SupplierSummaryTab() {
  const t = useT();
  const [from, setFrom] = useState(yearStart());
  const [to,   setTo  ] = useState(today());
  const [rows, setRows] = useState<SupplierRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/stats/supplier-summary?period_from=${from}&period_to=${to}`, { headers: authHeaders() });
      if (res.ok) { const d = await res.json(); setRows(d.rows); }
    } finally { setLoading(false); }
  }

  async function downloadPdf() {
    setDownloading(true);
    try {
      const res = await fetch(`${BASE}/stats/supplier-summary/pdf?period_from=${from}&period_to=${to}`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
      a.download = `Lieferant_Statistik_${from}_${to}.pdf`; a.click();
    } finally { setDownloading(false); }
  }

  const totals = rows.reduce((s, r) => ({ ct: s.ct + r.curr_turnover, pt: s.pt + r.prev_turnover, cc: s.cc + r.curr_commission, pc: s.pc + r.prev_commission }), { ct: 0, pt: 0, cc: 0, pc: 0 });
  const tot_diff = totals.cc - totals.pc;
  const tot_pct  = totals.pc ? ((totals.cc / totals.pc - 1) * 100) : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <DateRangePicker from={from} to={to} onChange={(f, newTo) => { setFrom(f); setTo(newTo); }} />
        <button onClick={load} disabled={loading} className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> {t.stats.load}
        </button>
        <button onClick={downloadPdf} disabled={downloading || !rows.length} className="flex items-center gap-1.5 border border-blue-600 text-blue-600 px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-50 disabled:opacity-50">
          <FileDown size={14} /> {downloading ? "…" : "PDF"}
        </button>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm whitespace-nowrap">
          <thead>
            <tr className="bg-blue-600 text-white">
              <th className="px-4 py-2 text-left" rowSpan={2}>{t.stats.supplier}</th>
              <th className="px-3 py-2 text-center border-l border-white/20" colSpan={2}>{t.stats.turnoverLabel}</th>
              <th className="px-3 py-2 text-center border-l border-white/20" colSpan={2}>{t.stats.commissionLabel}</th>
              <th className="px-3 py-2 text-center border-l border-white/20" colSpan={2}>{t.stats.commDiff}</th>
            </tr>
            <tr className="bg-blue-500 text-white text-xs">
              <th className="px-3 py-1.5 text-right border-l border-white/20">{t.stats.prevYear}</th>
              <th className="px-3 py-1.5 text-right">{t.stats.current}</th>
              <th className="px-3 py-1.5 text-right border-l border-white/20">{t.stats.prevYear}</th>
              <th className="px-3 py-1.5 text-right">{t.stats.current}</th>
              <th className="px-3 py-1.5 text-right border-l border-white/20">{t.stats.amount}</th>
              <th className="px-3 py-1.5 text-right">%</th>
            </tr>
          </thead>
          <tbody>
            {loading ? <tr><td colSpan={7} className="py-8 text-center text-gray-400">{t.common.loading}</td></tr>
            : rows.map((r, i) => (
              <tr key={r.code} className={i % 2 === 0 ? "bg-white" : "bg-blue-50/40"}>
                <td className="px-4 py-1.5 font-medium text-gray-800">{r.name}</td>
                <td className="px-3 py-1.5 text-right text-gray-500">{fmt(r.prev_turnover)}</td>
                <td className="px-3 py-1.5 text-right font-medium">{fmt(r.curr_turnover)}</td>
                <td className="px-3 py-1.5 text-right text-gray-500">{fmt(r.prev_commission)}</td>
                <td className="px-3 py-1.5 text-right font-semibold text-emerald-700">{fmt(r.curr_commission)}</td>
                <td className={`px-3 py-1.5 text-right text-xs font-medium ${r.comm_diff < 0 ? "text-red-600" : r.comm_diff > 0 ? "text-emerald-700" : "text-gray-400"}`}>
                  {r.comm_diff !== 0 ? (r.comm_diff > 0 ? "+" : "") + fmt(r.comm_diff) : "0"}
                </td>
                <td className={`px-3 py-1.5 text-right text-xs ${r.comm_pct === null ? "text-gray-400" : r.comm_pct < 0 ? "text-red-600" : "text-emerald-700"}`}>{fmtPct(r.comm_pct)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-blue-600 bg-blue-50 font-semibold">
              <td className="px-4 py-2">{t.stats.total}</td>
              <td className="px-3 py-2 text-right text-gray-600">{fmt(totals.pt)}</td>
              <td className="px-3 py-2 text-right">{fmt(totals.ct)}</td>
              <td className="px-3 py-2 text-right text-gray-600">{fmt(totals.pc)}</td>
              <td className="px-3 py-2 text-right text-emerald-700">{fmt(totals.cc)}</td>
              <td className={`px-3 py-2 text-right text-xs ${tot_diff < 0 ? "text-red-600" : "text-emerald-700"}`}>{tot_diff !== 0 ? (tot_diff > 0 ? "+" : "") + fmt(tot_diff) : "0"}</td>
              <td className={`px-3 py-2 text-right text-xs ${tot_pct === null ? "text-gray-400" : tot_pct < 0 ? "text-red-600" : "text-emerald-700"}`}>{fmtPct(tot_pct)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

// ── Tab: AdrUms (Kunden nach Provision/Umsatz) ───────────────────────────────
function CustomerTurnoverTab({ sortBy }: { sortBy: "provision" | "turnover" }) {
  const t = useT();
  const [from, setFrom] = useState(yearStart());
  const [to,   setTo  ] = useState(today());
  const [rows, setRows] = useState<CustomerRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => { load(); }, [sortBy]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/stats/customer-turnover?period_from=${from}&period_to=${to}&sort_by=${sortBy}`, { headers: authHeaders() });
      if (res.ok) { const d = await res.json(); setRows(d.rows); }
    } finally { setLoading(false); }
  }

  async function downloadPdf() {
    setDownloading(true);
    try {
      const res = await fetch(`${BASE}/stats/customer-turnover/pdf?period_from=${from}&period_to=${to}&sort_by=${sortBy}`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
      a.download = `AdrUms_${sortBy}_${from}_${to}.pdf`; a.click();
    } finally { setDownloading(false); }
  }

  const totT = rows.reduce((s, r) => s + r.curr_turnover, 0);
  const totP = rows.reduce((s, r) => s + r.curr_provision, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <DateRangePicker from={from} to={to} onChange={(f, newTo) => { setFrom(f); setTo(newTo); }} />
        <button onClick={load} disabled={loading} className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> {t.stats.load}
        </button>
        <button onClick={downloadPdf} disabled={downloading || !rows.length} className="flex items-center gap-1.5 border border-blue-600 text-blue-600 px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-50 disabled:opacity-50">
          <FileDown size={14} /> {downloading ? "…" : "PDF"}
        </button>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
        {sortBy === "provision" ? (
          <table className="w-full text-sm whitespace-nowrap">
            <thead className="bg-blue-600 text-white text-xs">
              <tr>
                <th className="px-4 py-2 text-left font-medium">{t.stats.nameCompany}</th>
                <th className="px-3 py-2 text-right font-medium">{t.stats.turnoverPrev}</th>
                <th className="px-3 py-2 text-right font-medium">{t.stats.turnoverCurr}</th>
                <th className="px-3 py-2 text-right font-medium">{t.stats.commissionLabel}</th>
                <th className="px-3 py-2 text-right font-medium">{t.stats.duPrPct}</th>
                <th className="px-3 py-2 text-right font-medium">{t.stats.sharePct}</th>
                <th className="px-3 py-2 text-center font-medium">{t.stats.rank}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? <tr><td colSpan={7} className="py-8 text-center text-gray-400">{t.common.loading}</td></tr>
              : rows.map((r, i) => (
                <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-blue-50/40"}>
                  <td className="px-4 py-1.5 text-gray-800">{custLabel(r)}</td>
                  <td className="px-3 py-1.5 text-right text-gray-500 text-xs">{fmt(r.prev_turnover)}</td>
                  <td className="px-3 py-1.5 text-right font-medium">{fmt(r.curr_turnover)}</td>
                  <td className="px-3 py-1.5 text-right font-semibold text-emerald-700">{fmt(r.curr_provision)}</td>
                  <td className="px-3 py-1.5 text-right text-xs text-gray-600">{r.du_pr_pct != null ? r.du_pr_pct.toFixed(2).replace(".", ",") : "–"}</td>
                  <td className="px-3 py-1.5 text-right text-xs text-gray-600">{r.curr_provision ? `${r.share_pct.toFixed(1).replace(".", ",")}%` : "~"}</td>
                  <td className="px-3 py-1.5 text-center text-xs text-gray-400">{i + 1}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-blue-600 bg-blue-50 font-semibold">
                <td className="px-4 py-2">{t.stats.grandTotal}</td>
                <td className="px-3 py-2 text-right text-gray-500">{fmt(rows.reduce((s,r)=>s+r.prev_turnover,0))}</td>
                <td className="px-3 py-2 text-right">{fmt(totT)}</td>
                <td className="px-3 py-2 text-right text-emerald-700">{fmt(totP)}</td>
                <td colSpan={3} />
              </tr>
            </tfoot>
          </table>
        ) : (
          <table className="w-full text-sm whitespace-nowrap">
            <thead className="bg-blue-600 text-white text-xs">
              <tr>
                <th className="px-4 py-2 text-left font-medium">{t.stats.nameCompany}</th>
                <th className="px-3 py-2 text-right font-medium">{t.stats.turnoverPrev}</th>
                <th className="px-3 py-2 text-right font-medium">{t.stats.turnoverCurr}</th>
                <th className="px-3 py-2 text-right font-medium">{t.stats.growthPct}</th>
                <th className="px-3 py-2 text-center font-medium">{t.stats.rank}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? <tr><td colSpan={5} className="py-8 text-center text-gray-400">{t.common.loading}</td></tr>
              : rows.map((r, i) => (
                <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-blue-50/40"}>
                  <td className="px-4 py-1.5 text-gray-800">{custLabel(r)}</td>
                  <td className="px-3 py-1.5 text-right text-gray-500 text-xs">{fmt(r.prev_turnover)}</td>
                  <td className="px-3 py-1.5 text-right font-medium">{fmt(r.curr_turnover)}</td>
                  <td className="px-3 py-1.5 text-right text-xs text-gray-600">
                    {r.growth_pct == null ? "~" : r.growth_pct > 9999 ? "*****" : `${r.growth_pct.toFixed(0)}%`}
                  </td>
                  <td className="px-3 py-1.5 text-center text-xs text-gray-400">{i + 1}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-blue-600 bg-blue-50 font-semibold">
                <td className="px-4 py-2">{t.stats.grandTotal}</td>
                <td className="px-3 py-2 text-right text-gray-500">{fmt(rows.reduce((s,r)=>s+r.prev_turnover,0))}</td>
                <td className="px-3 py-2 text-right">{fmt(totT)}</td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          </table>
        )}
      </div>
    </div>
  );
}

// ── Tab: Lieferant Detail (quarterly) ───────────────────────────────────────
function SupplierDetailTab() {
  const t = useT();
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<DetailSupplier[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/stats/supplier-detail?year=${year}`, { headers: authHeaders() });
      if (res.ok) { const d = await res.json(); setData(d.suppliers); }
    } finally { setLoading(false); }
  }

  async function downloadPdf() {
    setDownloading(true);
    try {
      const res = await fetch(`${BASE}/stats/supplier-detail/pdf?year=${year}`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
      a.download = `Lieferant_Detail_${year}.pdf`; a.click();
    } finally { setDownloading(false); }
  }

  function pctStr(curr: number, prev: number) {
    if (!prev) return "***%";
    const p = (curr / prev - 1) * 100;
    return (p >= 0 ? "+" : "") + p.toFixed(0) + "%";
  }

  const BOLD_LABELS = new Set(["1.HY", "2.HY", "Jahr"]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">{t.stats.year}</label>
          <input type="number" value={year} onChange={e => setYear(parseInt(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-24 focus:outline-none focus:ring-2 focus:ring-blue-600/30" />
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> {t.stats.load}
        </button>
        <button onClick={downloadPdf} disabled={downloading || !data.length} className="flex items-center gap-1.5 border border-blue-600 text-blue-600 px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-50 disabled:opacity-50">
          <FileDown size={14} /> {downloading ? "…" : "PDF"}
        </button>
      </div>

      {loading && <div className="text-center text-gray-400 py-8">{t.common.loading}</div>}
      {!loading && data.map(s => (
        <div key={s.code} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-2 bg-gray-50 border-b border-gray-100 font-semibold text-gray-800 text-sm">{s.name}</div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs whitespace-nowrap">
              <thead className="bg-blue-600 text-white">
                <tr>
                  <th className="px-3 py-1.5 text-left w-12">des.</th>
                  <th className="px-3 py-1.5 text-right">{t.stats.turnoverPrev}</th>
                  <th className="px-3 py-1.5 text-right">Budget</th>
                  <th className="px-3 py-1.5 text-right">+/-</th>
                  <th className="px-3 py-1.5 text-right">{t.stats.turnoverCurr}</th>
                  <th className="px-3 py-1.5 text-right">+/-</th>
                  <th className="px-3 py-1.5 text-right">{t.stats.commPrev}</th>
                  <th className="px-3 py-1.5 text-right">{t.stats.commissionLabel} Budget</th>
                  <th className="px-3 py-1.5 text-right">{t.stats.commCurr}</th>
                  <th className="px-3 py-1.5 text-right">+/-</th>
                  <th className="px-3 py-1.5 text-right">{t.stats.commDiff}</th>
                  <th className="px-3 py-1.5 text-right">+/-</th>
                </tr>
              </thead>
              <tbody>
                {s.rows.map((r, i) => {
                  const isBold = BOLD_LABELS.has(r.label);
                  const diff = r.curr_commission - r.prev_commission;
                  return (
                    <tr key={r.label} className={`${isBold ? "bg-blue-50 font-semibold" : i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}`}>
                      <td className="px-3 py-1 text-gray-600">{r.label}</td>
                      <td className="px-3 py-1 text-right text-gray-500">{fmt(r.prev_turnover)}</td>
                      <td className="px-3 py-1 text-right text-gray-400">{r.budget_turnover ? fmt(r.budget_turnover) : ""}</td>
                      <td className="px-3 py-1 text-right text-gray-400">{r.budget_turnover && r.prev_turnover ? pctStr(r.budget_turnover, r.prev_turnover) : ""}</td>
                      <td className="px-3 py-1 text-right font-medium">{fmt(r.curr_turnover)}</td>
                      <td className={`px-3 py-1 text-right ${r.curr_turnover > r.prev_turnover ? "text-emerald-700" : "text-red-600"}`}>
                        {r.prev_turnover ? pctStr(r.curr_turnover, r.prev_turnover) : "***%"}
                      </td>
                      <td className="px-3 py-1 text-right text-gray-500">{fmt(r.prev_commission)}</td>
                      <td className="px-3 py-1 text-right text-gray-400">{r.budget_commission ? fmt(r.budget_commission) : ""}</td>
                      <td className="px-3 py-1 text-right text-emerald-700 font-medium">{fmt(r.curr_commission)}</td>
                      <td className={`px-3 py-1 text-right ${r.curr_commission > r.prev_commission ? "text-emerald-700" : "text-red-600"}`}>
                        {r.prev_commission ? pctStr(r.curr_commission, r.prev_commission) : "***%"}
                      </td>
                      <td className={`px-3 py-1 text-right font-medium ${diff > 0 ? "text-emerald-700" : diff < 0 ? "text-red-600" : "text-gray-400"}`}>
                        {diff !== 0 ? (diff > 0 ? "+" : "") + fmt(diff) : "0"}
                      </td>
                      <td className={`px-3 py-1 text-right ${r.curr_commission > r.prev_commission ? "text-emerald-700" : "text-red-600"}`}>
                        {r.prev_commission ? pctStr(r.curr_commission, r.prev_commission) : "***%"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
type Tab = "summary" | "adrumsProvision" | "adrumsUmsatz" | "detail";

export default function SupplierStats() {
  const t = useT();
  const [tab, setTab] = useState<Tab>("summary");

  const TABS: { id: Tab; label: string }[] = [
    { id: "summary",         label: t.stats.tabSummary },
    { id: "adrumsProvision", label: t.stats.tabAdrumsP },
    { id: "adrumsUmsatz",    label: t.stats.tabAdrumsU },
    { id: "detail",          label: t.stats.tabDetail },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-gray-800">{t.stats.title}</h1>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map(tab_ => (
          <button key={tab_.id} onClick={() => setTab(tab_.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === tab_.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {tab_.label}
          </button>
        ))}
      </div>

      {tab === "summary"         && <SupplierSummaryTab />}
      {tab === "adrumsProvision" && <CustomerTurnoverTab sortBy="provision" />}
      {tab === "adrumsUmsatz"    && <CustomerTurnoverTab sortBy="turnover" />}
      {tab === "detail"          && <SupplierDetailTab />}
    </div>
  );
}
