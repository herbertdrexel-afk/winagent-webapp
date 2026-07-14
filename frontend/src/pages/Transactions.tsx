import { useEffect, useRef, useState } from "react";
import { api, type Supplier, type Transaction, BASE, token } from "../api";
import { useT } from "../context/LocaleContext";
import InvoiceModal from "../components/InvoiceModal";
import PdfImportModal from "../components/PdfImportModal";
import CommissionInvoiceModal from "../components/CommissionInvoiceModal";
import { RefreshCw, X } from "lucide-react";

const THIS_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 4 }, (_, i) => THIS_YEAR - i);
const LS_SUPPLIER = "winagent_tx_supplier";
const LS_YEAR = "winagent_tx_year";

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
    inv.total_amount    += amount;
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

  const [suppliers, setSuppliers]         = useState<Supplier[]>([]);
  const [supplierCode, setSupplierCode]   = useState(() => localStorage.getItem(LS_SUPPLIER) ?? "");
  const [year, setYear]                   = useState(() => parseInt(localStorage.getItem(LS_YEAR) ?? String(THIS_YEAR)));

  // Period is always the full chosen year
  const from = `${year}-01-01`;
  const to   = `${year}-12-31`;

  const [rows, setRows]         = useState<Transaction[]>([]);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const [editing, setEditing]                         = useState<Invoice | null | undefined>(undefined);
  const [showPdfImport, setShowPdfImport]             = useState(false);
  const [showCommissionInvoice, setShowCommissionInvoice] = useState(false);

  const [dbfImporting, setDbfImporting] = useState(false);
  const [dbfResult, setDbfResult]       = useState<string | null>(null);
  const dbfInputRef = useRef<HTMLInputElement>(null);

  const [xmlImporting, setXmlImporting] = useState(false);
  const [xmlResult, setXmlResult]       = useState<string | null>(null);
  const xmlInputRef = useRef<HTMLInputElement>(null);

  // Client-side search
  const [searchNr,      setSearchNr]      = useState("");
  const [searchKunde,   setSearchKunde]   = useState("");
  const [searchDatum,   setSearchDatum]   = useState("");

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

  // Auto-load whenever supplier or year changes
  useEffect(() => {
    if (!supplierCode) return;
    loadData();
  }, [supplierCode, year]);

  function loadData() {
    if (!supplierCode) return;
    setLoading(true);
    setError(null);
    api.transactions.list(supplierCode, from, to)
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
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
        if (searchNr) {
          if (!inv.invoice_number.toLowerCase().includes(searchNr.toLowerCase())) return false;
        }
        if (searchKunde) {
          const q = searchKunde.toLowerCase();
          const hit =
            (inv.customer_name  ?? "").toLowerCase().includes(q) ||
            (inv.customer_ku_nr ?? "").toLowerCase().includes(q) ||
            (inv.customer_code  ?? "").toLowerCase().includes(q);
          if (!hit) return false;
        }
        if (searchDatum) {
          if (!inv.invoice_date.includes(searchDatum)) return false;
        }
        return true;
      })
    : invoices;

  // Totals always from filtered set
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

      {/* ── Filter bar ── */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          {/* Supplier */}
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

          {/* Year */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.stats.year}</label>
            <select
              value={year}
              onChange={(e) => {
                const y = parseInt(e.target.value);
                setYear(y);
                localStorage.setItem(LS_YEAR, String(y));
              }}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            >
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>

          {/* Divider */}
          <div className="w-px h-8 bg-gray-200 self-end mb-0.5 hidden sm:block" />

          {/* Search: Rg-Nr */}
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

          {/* Search: Kunde */}
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

          {/* Search: Datum */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.transactions.date}</label>
            <input
              type="search"
              value={searchDatum}
              onChange={(e) => setSearchDatum(e.target.value)}
              placeholder={t.transactions.searchDate}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
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
                  <td className="px-4 py-2 text-gray-600">{inv.invoice_date}</td>
                  <td className="px-4 py-2 text-gray-500 text-xs">{inv.customer_ku_nr ?? inv.customer_code ?? "–"}</td>
                  <td className="px-4 py-2 font-medium">{inv.customer_name ?? "–"}</td>
                  <td className="px-4 py-2 text-center text-gray-500">{inv.positions.length}</td>
                  <td className="px-4 py-2 text-gray-600">{inv.currency ?? "–"}</td>
                  <td className="px-4 py-2 text-right font-medium">
                    {inv.total_amount.toLocaleString("de-AT", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-500">
                    {inv.provision_rate != null && inv.provision_rate > 0
                      ? `${inv.provision_rate.toLocaleString("de-AT", { minimumFractionDigits: 2 })} %`
                      : "–"}
                  </td>
                  <td className="px-4 py-2 text-right text-emerald-700 font-medium">
                    {inv.provision_amount > 0
                      ? inv.provision_amount.toLocaleString("de-AT", { minimumFractionDigits: 2 })
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
                    {tot.amount.toLocaleString("de-AT", { minimumFractionDigits: 2 })}
                  </td>
                  <td />
                  <td className="px-4 py-2 text-right text-emerald-700">
                    {tot.provision.toLocaleString("de-AT", { minimumFractionDigits: 2 })}
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
