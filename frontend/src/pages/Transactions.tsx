import { useEffect, useRef, useState } from "react";
import { api, type Supplier, type Transaction, BASE, token } from "../api";
import { useT } from "../context/LocaleContext";
import { formatDate, formatNum } from "../utils/format";
import InvoiceModal from "../components/InvoiceModal";
import PdfImportModal from "../components/PdfImportModal";
import CommissionInvoiceModal from "../components/CommissionInvoiceModal";
import { RefreshCw, X } from "lucide-react";

const THIS_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 5 }, (_, i) => THIS_YEAR - i);
const LS_SUPPLIER = "winagent_tx_supplier";
const LS_YEAR     = "winagent_tx_year";
const LS_FROM     = "winagent_tx_from";
const LS_TO       = "winagent_tx_to";
const LS_PERIOD   = "winagent_tx_period";

type PeriodKey = "this_week" | "this_month" | "last_month" | "q1" | "q2" | "q3" | "q4" | "year" | null;

function isoDate(d: Date) {
  // Lokale Datumsteile verwenden – toISOString() würde bei UTC+x einen Tag zurückspringen
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function computePeriod(key: PeriodKey, year: number): { from: string; to: string } {
  const now = new Date();
  switch (key) {
    case "this_week": {
      const dow = now.getDay(); // 0=Sun
      const diffToMon = dow === 0 ? -6 : 1 - dow;
      const mon = new Date(now); mon.setDate(now.getDate() + diffToMon);
      const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
      return { from: isoDate(mon), to: isoDate(sun) };
    }
    case "this_month": {
      const y = now.getFullYear(), m = now.getMonth();
      return { from: isoDate(new Date(y, m, 1)), to: isoDate(new Date(y, m + 1, 0)) };
    }
    case "last_month": {
      const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const last  = new Date(now.getFullYear(), now.getMonth(), 0);
      return { from: isoDate(first), to: isoDate(last) };
    }
    case "q1": return { from: `${year}-01-01`, to: `${year}-03-31` };
    case "q2": return { from: `${year}-04-01`, to: `${year}-06-30` };
    case "q3": return { from: `${year}-07-01`, to: `${year}-09-30` };
    case "q4": return { from: `${year}-10-01`, to: `${year}-12-31` };
    default:   return { from: `${year}-01-01`, to: `${year}-12-31` };
  }
}

export interface Invoice {
  invoice_number: string;
  invoice_date: string;
  customer_id?: number;
  customer_code?: string;
  customer_ku_nr?: string;
  customer_name?: string;
  currency?: string;
  total_amount: number;
  provision_amount: number;
  provision_rate: number | null;
  positions: Transaction[];
}

function groupInvoices(rows: Transaction[]): Invoice[] {
  const map = new Map<string, Invoice>();
  for (const r of rows) {
    const key = r.invoice_number;
    if (!map.has(key)) {
      map.set(key, {
        invoice_number: r.invoice_number,
        invoice_date: r.invoice_date,
        customer_id: r.customer_id,
        customer_code: r.customer_code,
        customer_ku_nr: r.customer_ku_nr,
        customer_name: r.customer_name,
        currency: r.currency,
        total_amount: 0,
        provision_amount: 0,
        provision_rate: null,
        positions: [],
      });
    }
    const inv = map.get(key)!;
    const amount = parseFloat(r.total_amount as unknown as string) || 0;
    const rate   = parseFloat(r.provision_rate as unknown as string) || 0;
    inv.total_amount     += amount;
    inv.provision_amount += (amount * rate) / 100;
    inv.positions.push(r);
  }
  for (const inv of map.values()) {
    if (inv.total_amount !== 0) {
      inv.provision_rate = (inv.provision_amount / inv.total_amount) * 100;
    }
  }
  return Array.from(map.values());
}

export default function Transactions() {
  const t = useT();

  const [suppliers, setSuppliers]       = useState<Supplier[]>([]);
  const [supplierCode, setSupplierCode] = useState(() => localStorage.getItem(LS_SUPPLIER) ?? "");
  const [year, setYear]                 = useState(() => parseInt(localStorage.getItem(LS_YEAR) ?? String(THIS_YEAR)));
  const [activePeriod, setActivePeriod] = useState<PeriodKey>(() => (localStorage.getItem(LS_PERIOD) as PeriodKey) ?? "year");

  const initYear   = parseInt(localStorage.getItem(LS_YEAR) ?? String(THIS_YEAR));
  const initPeriod = (localStorage.getItem(LS_PERIOD) as PeriodKey) ?? "year";
  const initDates  = computePeriod(initPeriod, initYear);
  const [from, setFrom] = useState(() => localStorage.getItem(LS_FROM) ?? initDates.from);
  const [to,   setTo]   = useState(() => localStorage.getItem(LS_TO)   ?? initDates.to);

  const [rows, setRows]       = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const [editing, setEditing]                               = useState<Invoice | null | undefined>(undefined);
  const [showPdfImport, setShowPdfImport]                   = useState(false);
  const [showCommissionInvoice, setShowCommissionInvoice]   = useState(false);

  const [dbfImporting, setDbfImporting] = useState(false);
  const [dbfResult, setDbfResult]       = useState<string | null>(null);
  const dbfInputRef = useRef<HTMLInputElement>(null);

  const [xmlImporting, setXmlImporting] = useState(false);
  const [xmlResult, setXmlResult]       = useState<string | null>(null);
  const xmlInputRef = useRef<HTMLInputElement>(null);

  // Client-side search
  const [searchNr,    setSearchNr]    = useState("");
  const [searchKunde, setSearchKunde] = useState("");
  const [searchDatum, setSearchDatum] = useState("");

  // Load supplier list once
  useEffect(() => {
    api.suppliers.list().then((s) => {
      setSuppliers(s);
      const saved = localStorage.getItem(LS_SUPPLIER);
      if (!saved || !s.some((x) => x.code === saved)) {
        if (s.length > 0) setSupplierCode(s[0].code);
      }
    });
  }, []);

  // Auto-load whenever supplier or date range changes.
  // Wichtig: Erst laden, wenn die Lieferantenliste geladen ist UND der gewaehlte
  // Lieferant darin vorkommt. Verhindert einen 403 durch einen veralteten
  // localStorage-Lieferanten, auf den ein eingeschraenkter Benutzer keinen Zugriff hat.
  useEffect(() => {
    if (!supplierCode || !from || !to) return;
    if (suppliers.length === 0) return;
    if (!suppliers.some((s) => s.code === supplierCode)) return;
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplierCode, from, to, suppliers]);

  function loadData() {
    if (!supplierCode) return;
    setLoading(true);
    setError(null);
    api.transactions.list(supplierCode, from, to)
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  function selectPeriod(key: PeriodKey) {
    const p = computePeriod(key, year);
    setActivePeriod(key);
    setFrom(p.from);
    setTo(p.to);
    localStorage.setItem(LS_PERIOD, key ?? "year");
    localStorage.setItem(LS_FROM, p.from);
    localStorage.setItem(LS_TO, p.to);
  }

  function changeYear(y: number) {
    setYear(y);
    localStorage.setItem(LS_YEAR, String(y));
    if (activePeriod && ["q1","q2","q3","q4","year"].includes(activePeriod)) {
      const p = computePeriod(activePeriod, y);
      setFrom(p.from);
      setTo(p.to);
      localStorage.setItem(LS_FROM, p.from);
      localStorage.setItem(LS_TO, p.to);
    }
  }

  function setCustomFrom(v: string) {
    setFrom(v);
    setActivePeriod(null);
    localStorage.setItem(LS_FROM, v);
    localStorage.removeItem(LS_PERIOD);
  }

  function setCustomTo(v: string) {
    setTo(v);
    setActivePeriod(null);
    localStorage.setItem(LS_TO, v);
    localStorage.removeItem(LS_PERIOD);
  }

  function handleSaved(updatedPositions: Transaction[]) {
    setRows((prev) => {
      const invoiceNr = updatedPositions[0]?.invoice_number ?? editing?.invoice_number;
      const withoutOld = prev.filter((r) => r.invoice_number !== invoiceNr);
      return [...withoutOld, ...updatedPositions].sort(
        (a, b) => a.invoice_date.localeCompare(b.invoice_date)
      );
    });
    setEditing(undefined);
  }

  function handleDeleted(invoiceNumber: string) {
    setRows((prev) => prev.filter((r) => r.invoice_number !== invoiceNumber));
    setEditing(undefined);
  }

  async function handleDbfFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setDbfImporting(true);
    setDbfResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const tok = token.get();
      const res = await fetch(`${BASE}/sync/dbf/import`, {
        method: "POST",
        headers: tok ? { Authorization: `Bearer ${tok}` } : {},
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || t.common.error);
      setDbfResult(t.transactions.dbfSuccess(data.imported, data.skipped));
      loadData();
    } catch (err: unknown) {
      setDbfResult(t.transactions.importError(err instanceof Error ? err.message : t.common.unknown));
    } finally {
      setDbfImporting(false);
      if (dbfInputRef.current) dbfInputRef.current.value = "";
    }
  }

  async function handleXmlFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setXmlImporting(true);
    setXmlResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      if (supplierCode) form.append("supplier_code", supplierCode);
      const tok = token.get();
      const res = await fetch(`${BASE}/sync/einvoice/import`, {
        method: "POST",
        headers: tok ? { Authorization: `Bearer ${tok}` } : {},
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || t.common.error);
      setXmlResult(`✓ ${data.invoice_number} · ${data.buyer} · ${data.lines_imported} Position(en) · ${data.supplier_matched}`);
      loadData();
    } catch (err: unknown) {
      setXmlResult(t.transactions.importError(err instanceof Error ? err.message : t.common.unknown));
    } finally {
      setXmlImporting(false);
      if (xmlInputRef.current) xmlInputRef.current.value = "";
    }
  }

  function handlePdfImported(imported: Transaction[]) {
    setRows((prev) => {
      const existingNrs = new Set(imported.map((r) => r.invoice_number));
      const withoutDupes = prev.filter((r) => !existingNrs.has(r.invoice_number));
      return [...withoutDupes, ...imported].sort(
        (a, b) => a.invoice_date.localeCompare(b.invoice_date)
      );
    });
    setShowPdfImport(false);
  }

  // Group and filter
  const invoices = groupInvoices(rows);
  const isFiltered = !!(searchNr || searchKunde || searchDatum);

  const filteredInvoices = isFiltered
    ? invoices.filter((inv) => {
        if (searchNr && !inv.invoice_number.toLowerCase().includes(searchNr.toLowerCase())) return false;
        if (searchKunde) {
          const q = searchKunde.toLowerCase();
          const hit =
            (inv.customer_name  ?? "").toLowerCase().includes(q) ||
            (inv.customer_ku_nr ?? "").toLowerCase().includes(q) ||
            (inv.customer_code  ?? "").toLowerCase().includes(q);
          if (!hit) return false;
        }
        if (searchDatum) {
          const q = searchDatum.trim();
          // sowohl ISO (2026-04) als auch T.M.Y (04.2026 / 02.04.2026) erlauben
          if (!inv.invoice_date.includes(q) && !formatDate(inv.invoice_date).includes(q)) return false;
        }
        return true;
      })
    : invoices;

  const totalsByCurrency = filteredInvoices.reduce<
    Record<string, { amount: number; provision: number; invoices: number; positions: number }>
  >((acc, inv) => {
    const cur = inv.currency ?? "–";
    if (!acc[cur]) acc[cur] = { amount: 0, provision: 0, invoices: 0, positions: 0 };
    acc[cur].amount    += inv.total_amount;
    acc[cur].provision += inv.provision_amount;
    acc[cur].invoices  += 1;
    acc[cur].positions += inv.positions.length;
    return acc;
  }, {});
  const currencyTotals = Object.entries(totalsByCurrency).sort(([a], [b]) => a.localeCompare(b));

  // Period chip helper
  function chipCls(key: PeriodKey) {
    return activePeriod === key
      ? "bg-[#2563eb] text-white border-[#2563eb]"
      : "bg-white text-gray-600 border-gray-300 hover:border-[#2563eb] hover:text-[#2563eb]";
  }

  return (
    <>
    <div>
      {/* ── Header row ── */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <h1 className="text-2xl font-semibold text-gray-800">{t.transactions.title}</h1>
        <div className="flex flex-col items-end gap-1">
          <div className="flex flex-wrap justify-end gap-2">
            <button
              onClick={() => setShowCommissionInvoice(true)}
              disabled={!supplierCode || invoices.length === 0}
              className="border border-emerald-600 text-emerald-700 px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-emerald-50 disabled:opacity-40 transition-colors"
            >
              🧾 {t.transactions.commInvoice}
            </button>
            <button
              onClick={() => xmlInputRef.current?.click()}
              disabled={xmlImporting}
              title="XRechnung XML (UBL oder CII) importieren"
              className="border border-emerald-600 text-emerald-700 px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-emerald-50 disabled:opacity-40 transition-colors"
            >
              {xmlImporting ? "⏳…" : `📨 ${t.transactions.eInvoice}`}
            </button>
            <input ref={xmlInputRef} type="file" accept=".xml,.XML" className="hidden" onChange={handleXmlFile} />
            <button
              onClick={() => dbfInputRef.current?.click()}
              disabled={!supplierCode || dbfImporting}
              title="Reybex DBF-Export hochladen"
              className="border border-violet-600 text-violet-700 px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-violet-50 disabled:opacity-40 transition-colors"
            >
              {dbfImporting ? "⏳…" : "🔄 DBF"}
            </button>
            <input ref={dbfInputRef} type="file" accept=".dbf,.DBF" className="hidden" onChange={handleDbfFile} />
            <button
              onClick={() => setShowPdfImport(true)}
              disabled={!supplierCode}
              className="border border-[#2563eb] text-[#2563eb] px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/10 disabled:opacity-40 transition-colors"
            >
              📊 CSV/Excel
            </button>
            <button
              onClick={() => setEditing(null)}
              disabled={!supplierCode}
              className="bg-[#2563eb] text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 disabled:opacity-40 transition-colors"
            >
              {t.transactions.newEntry}
            </button>
          </div>
          {xmlResult && (
            <span className={`text-xs ${xmlResult.startsWith("✓") ? "text-emerald-700" : "text-red-600"}`}>
              {xmlResult}
            </span>
          )}
          {dbfResult && (
            <span className={`text-xs ${dbfResult.startsWith("✓") ? "text-emerald-700" : "text-red-600"}`}>
              {dbfResult}
            </span>
          )}
        </div>
      </div>

      {/* ── Filter box ── */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-4 space-y-3">

        {/* Row 1: Supplier */}
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.transactions.supplier}</label>
            <select
              value={supplierCode}
              onChange={(e) => {
                setSupplierCode(e.target.value);
                localStorage.setItem(LS_SUPPLIER, e.target.value);
              }}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            >
              {suppliers.map((s) => (
                <option key={s.id} value={s.code}>{s.code} – {s.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Row 2: Period chips + year */}
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">{t.transactions.period}</label>
          <div className="flex flex-wrap gap-1.5 items-center">
            {/* Relative chips */}
            {(["this_week", "this_month", "last_month"] as PeriodKey[]).map((key) => (
              <button
                key={key!}
                onClick={() => selectPeriod(key)}
                className={`px-2.5 py-1 text-xs rounded-full border font-medium transition-colors ${chipCls(key)}`}
              >
                {key === "this_week"  ? t.transactions.thisWeek  :
                 key === "this_month" ? t.transactions.thisMonth :
                                        t.transactions.lastMonth}
              </button>
            ))}

            <div className="w-px h-5 bg-gray-200 mx-1" />

            {/* Quarter chips */}
            {(["q1","q2","q3","q4"] as PeriodKey[]).map((key) => (
              <button
                key={key!}
                onClick={() => selectPeriod(key)}
                className={`px-2.5 py-1 text-xs rounded-full border font-medium transition-colors ${chipCls(key)}`}
              >
                {key!.toUpperCase()}
              </button>
            ))}

            <div className="w-px h-5 bg-gray-200 mx-1" />

            {/* Full year chip */}
            <button
              onClick={() => selectPeriod("year")}
              className={`px-2.5 py-1 text-xs rounded-full border font-medium transition-colors ${chipCls("year")}`}
            >
              {t.transactions.year}
            </button>

            {/* Year selector */}
            <select
              value={year}
              onChange={(e) => changeYear(parseInt(e.target.value))}
              className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30 ml-1"
            >
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>

        {/* Row 3: Von / Bis date inputs + search */}
        <div className="flex flex-wrap gap-3 items-end pt-1 border-t border-gray-100">
          {/* Von */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.transactions.from}</label>
            <input
              type="date"
              value={from}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            />
          </div>
          {/* Bis */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.transactions.to}</label>
            <input
              type="date"
              value={to}
              onChange={(e) => setCustomTo(e.target.value)}
              className="border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            />
          </div>

          <div className="w-px h-8 bg-gray-200 self-end mb-0.5 hidden sm:block" />

          {/* Rg-Nr */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.transactions.invoiceNr}</label>
            <input
              type="search"
              value={searchNr}
              onChange={(e) => setSearchNr(e.target.value)}
              placeholder={t.transactions.searchNr}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            />
          </div>

          {/* Kunde */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.transactions.customer}</label>
            <input
              type="search"
              value={searchKunde}
              onChange={(e) => setSearchKunde(e.target.value)}
              placeholder={t.transactions.searchCustomer}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            />
          </div>

          {/* Datum */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.transactions.date}</label>
            <input
              type="search"
              value={searchDatum}
              onChange={(e) => setSearchDatum(e.target.value)}
              placeholder={t.transactions.searchDate}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            />
          </div>

          {/* Clear filter */}
          {isFiltered && (
            <button
              onClick={() => { setSearchNr(""); setSearchKunde(""); setSearchDatum(""); }}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-600 border border-gray-200 hover:border-red-200 px-2.5 py-1.5 rounded-lg transition-colors self-end"
            >
              <X size={12} /> {t.transactions.filterReset}
            </button>
          )}

          {/* Refresh */}
          <button
            onClick={loadData}
            disabled={loading || !supplierCode}
            title={t.common.refresh}
            className="self-end p-1.5 text-gray-400 hover:text-[#2563eb] hover:bg-[#2563eb]/5 rounded-lg transition-colors disabled:opacity-40"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {error && <div className="text-red-600 mb-3">{t.common.error}: {error}</div>}

      {/* ── Table ── */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-[#2563eb] text-white">
            <tr>
              {[
                t.transactions.invoiceNr,
                t.transactions.date,
                t.transactions.customerNr,
                t.transactions.customer,
                t.transactions.pos,
                t.transactions.currency,
                t.transactions.amount,
                t.transactions.provPct,
                t.transactions.provision,
              ].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-400">{t.common.loading}</td>
              </tr>
            ) : filteredInvoices.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-400">
                  {!supplierCode
                    ? t.transactions.selectSupplier
                    : isFiltered
                    ? t.transactions.noData
                    : t.transactions.noInvoicesInPeriod}
                </td>
              </tr>
            ) : (
              filteredInvoices.map((inv, i) => (
                <tr
                  key={inv.invoice_number}
                  onClick={() => setEditing(inv)}
                  className={
                    (i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40") +
                    " cursor-pointer hover:bg-[#2563eb]/10 transition-colors"
                  }
                >
                  <td className="px-4 py-2 font-mono text-xs">{inv.invoice_number}</td>
                  <td className="px-4 py-2 text-gray-600">{formatDate(inv.invoice_date)}</td>
                  <td className="px-4 py-2 text-gray-500 text-xs">{inv.customer_ku_nr ?? inv.customer_code ?? "–"}</td>
                  <td className="px-4 py-2 font-medium">{inv.customer_name ?? "–"}</td>
                  <td className="px-4 py-2 text-center text-gray-500">{inv.positions.length}</td>
                  <td className="px-4 py-2 text-gray-600">{inv.currency ?? "–"}</td>
                  <td className="px-4 py-2 text-right font-medium">
                    {formatNum(inv.total_amount)}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-500">
                    {inv.provision_rate != null && inv.provision_rate > 0
                      ? `${formatNum(inv.provision_rate)} %`
                      : "–"}
                  </td>
                  <td className="px-4 py-2 text-right text-emerald-700 font-medium">
                    {inv.provision_amount > 0
                      ? formatNum(inv.provision_amount)
                      : "–"}
                  </td>
                </tr>
              ))
            )}
          </tbody>

          {filteredInvoices.length > 0 && (
            <tfoot>
              {currencyTotals.map(([cur, tot], idx) => (
                <tr
                  key={cur}
                  className={`${idx === 0 ? "border-t-2 border-[#2563eb]" : "border-t border-gray-200"} bg-gray-50 font-semibold`}
                >
                  <td colSpan={5} className="px-4 py-2 text-sm">
                    {isFiltered
                      ? t.transactions.showing(filteredInvoices.length, invoices.length)
                      : t.transactions.totalRow(tot.invoices, tot.positions)}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{cur}</td>
                  <td className="px-4 py-2 text-right">
                    {formatNum(tot.amount)}
                  </td>
                  <td />
                  <td className="px-4 py-2 text-right text-emerald-700">
                    {formatNum(tot.provision)}
                  </td>
                </tr>
              ))}
            </tfoot>
          )}
        </table>
      </div>
    </div>

    {editing !== undefined && (
      <InvoiceModal
        invoice={editing}
        supplierCode={supplierCode}
        onClose={() => setEditing(undefined)}
        onSaved={handleSaved}
        onDeleted={handleDeleted}
      />
    )}

    {showCommissionInvoice && (
      <CommissionInvoiceModal
        supplierCode={supplierCode}
        periodFrom={from}
        periodTo={to}
        onClose={() => setShowCommissionInvoice(false)}
      />
    )}

    {showPdfImport && (
      <PdfImportModal
        supplierCode={supplierCode}
        onClose={() => setShowPdfImport(false)}
        onImported={handlePdfImported}
      />
    )}
    </>
  );
}
