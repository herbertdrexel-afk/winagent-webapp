import { useEffect, useRef, useState } from "react";
import { api, type Supplier, type Transaction, BASE, token } from "../api";
import InvoiceModal from "../components/InvoiceModal";
import PdfImportModal from "../components/PdfImportModal";
import CommissionInvoiceModal from "../components/CommissionInvoiceModal";
import DateRangePicker from "../components/DateRangePicker";

function today() { return new Date().toISOString().slice(0, 10); }
function yearStart() { return new Date().getFullYear() + "-01-01"; }

const LS_SUPPLIER = "winagent_tx_supplier";
const LS_FROM = "winagent_tx_from";
const LS_TO = "winagent_tx_to";

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
    const rate = parseFloat(r.provision_rate as unknown as string) || 0;
    inv.total_amount += amount;
    inv.provision_amount += (amount * rate) / 100;
    inv.positions.push(r);
  }
  // Derive effective rate after grouping
  for (const inv of map.values()) {
    if (inv.total_amount !== 0) {
      inv.provision_rate = (inv.provision_amount / inv.total_amount) * 100;
    }
  }
  return Array.from(map.values());
}

export default function Transactions() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supplierCode, setSupplierCode] = useState(() => localStorage.getItem(LS_SUPPLIER) ?? "");
  const [from, setFrom] = useState(() => localStorage.getItem(LS_FROM) ?? yearStart());
  const [to, setTo] = useState(() => localStorage.getItem(LS_TO) ?? today());
  const [rows, setRows] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Invoice | null | undefined>(undefined);
  const [showPdfImport, setShowPdfImport] = useState(false);
  const [showCommissionInvoice, setShowCommissionInvoice] = useState(false);
  const [dbfImporting, setDbfImporting] = useState(false);
  const [dbfResult, setDbfResult] = useState<string | null>(null);
  const dbfInputRef = useRef<HTMLInputElement>(null);
  const [xmlImporting, setXmlImporting] = useState(false);
  const [xmlResult, setXmlResult] = useState<string | null>(null);
  const xmlInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.suppliers.list().then((s) => {
      setSuppliers(s);
      const saved = localStorage.getItem(LS_SUPPLIER);
      if (!saved || !s.some((x) => x.code === saved)) {
        if (s.length > 0) setSupplierCode(s[0].code);
      }
    });
  }, []);

  function load() {
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
      const t = token.get();
      const res = await fetch(`${BASE}/sync/dbf/import`, {
        method: "POST",
        headers: t ? { Authorization: `Bearer ${t}` } : {},
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Fehler");
      setDbfResult(`✓ ${data.imported} Rechnungen importiert, ${data.skipped} übersprungen`);
      load();
    } catch (err: unknown) {
      setDbfResult(`Fehler: ${err instanceof Error ? err.message : "Unbekannt"}`);
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
      const t = token.get();
      const res = await fetch(`${BASE}/sync/einvoice/import`, {
        method: "POST",
        headers: t ? { Authorization: `Bearer ${t}` } : {},
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Fehler");
      setXmlResult(`✓ ${data.invoice_number} · ${data.buyer} · ${data.lines_imported} Position(en) · ${data.supplier_matched}`);
      load();
    } catch (err: unknown) {
      setXmlResult(`Fehler: ${err instanceof Error ? err.message : "Unbekannt"}`);
    } finally {
      setXmlImporting(false);
      if (xmlInputRef.current) xmlInputRef.current.value = "";
    }
  }

  function handlePdfImported(imported: Transaction[]) {
    setRows((prev) => {
      const existingNrs = new Set(imported.map((t) => t.invoice_number));
      const withoutDupes = prev.filter((r) => !existingNrs.has(r.invoice_number));
      return [...withoutDupes, ...imported].sort(
        (a, b) => a.invoice_date.localeCompare(b.invoice_date)
      );
    });
    setShowPdfImport(false);
  }

  const invoices = groupInvoices(rows);

  // Totals per currency
  const totalsByCurrency = invoices.reduce<Record<string, { amount: number; provision: number; invoices: number; positions: number }>>((acc, inv) => {
    const cur = inv.currency ?? "–";
    if (!acc[cur]) acc[cur] = { amount: 0, provision: 0, invoices: 0, positions: 0 };
    acc[cur].amount += inv.total_amount;
    acc[cur].provision += inv.provision_amount;
    acc[cur].invoices += 1;
    acc[cur].positions += inv.positions.length;
    return acc;
  }, {});
  const currencyTotals = Object.entries(totalsByCurrency).sort(([a], [b]) => a.localeCompare(b));

  return (
    <>
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-gray-800">Rechnungen</h1>
        <div className="flex flex-col items-end gap-1">
          <div className="flex gap-2">
            <button
              onClick={() => setShowCommissionInvoice(true)}
              disabled={!supplierCode || invoices.length === 0}
              className="border border-emerald-600 text-emerald-700 px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-emerald-50 disabled:opacity-40 transition-colors"
            >
              🧾 Provisionsrechnung
            </button>
            <button
              onClick={() => xmlInputRef.current?.click()}
              disabled={xmlImporting}
              title="XRechnung XML (UBL oder CII) importieren"
              className="border border-emerald-600 text-emerald-700 px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-emerald-50 disabled:opacity-40 transition-colors"
            >
              {xmlImporting ? "⏳ Importiere…" : "📨 E-Rechnung"}
            </button>
            <input ref={xmlInputRef} type="file" accept=".xml,.XML" className="hidden" onChange={handleXmlFile} />
            <button
              onClick={() => dbfInputRef.current?.click()}
              disabled={!supplierCode || dbfImporting}
              title="Reybex DBF-Export hochladen"
              className="border border-violet-600 text-violet-700 px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-violet-50 disabled:opacity-40 transition-colors"
            >
              {dbfImporting ? "⏳ Importiere…" : "🔄 DBF importieren"}
            </button>
            <input ref={dbfInputRef} type="file" accept=".dbf,.DBF" className="hidden" onChange={handleDbfFile} />
            <button
              onClick={() => setShowPdfImport(true)}
              disabled={!supplierCode}
              className="border border-[#2563eb] text-[#2563eb] px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/10 disabled:opacity-40 transition-colors"
            >
              📊 CSV / Excel importieren
            </button>
            <button
              onClick={() => setEditing(null)}
              disabled={!supplierCode}
              className="bg-[#2563eb] text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 disabled:opacity-40 transition-colors"
            >
              + Neue Rechnung
            </button>
          </div>
          {xmlResult && (
            <span className={`text-xs ${xmlResult.startsWith("Fehler") ? "text-red-600" : "text-emerald-700"}`}>
              {xmlResult}
            </span>
          )}
          {dbfResult && (
            <span className={`text-xs ${dbfResult.startsWith("Fehler") ? "text-red-600" : "text-emerald-700"}`}>
              {dbfResult}
            </span>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Lieferant</label>
          <select
            value={supplierCode}
            onChange={(e) => { setSupplierCode(e.target.value); localStorage.setItem(LS_SUPPLIER, e.target.value); }}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
          >
            {suppliers.map((s) => (
              <option key={s.id} value={s.code}>{s.code} – {s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Zeitraum</label>
          <DateRangePicker from={from} to={to} onChange={(f, t) => {
            setFrom(f); setTo(t);
            localStorage.setItem(LS_FROM, f);
            localStorage.setItem(LS_TO, t);
          }} />
        </div>
        <button onClick={load}
          className="bg-[#2563eb] text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 transition-colors">
          Laden
        </button>
      </div>

      {error && <div className="text-red-600 mb-3">Fehler: {error}</div>}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#2563eb] text-white">
            <tr>
              {["Rg-Nr", "Datum", "Kd-Nr", "Kunde", "Pos.", "Währung", "Betrag", "Prov. %", "Provision"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">Lade…</td></tr>
            ) : invoices.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">
                {supplierCode ? "Keine Rechnungen im Zeitraum" : "Lieferant auswählen"}
              </td></tr>
            ) : invoices.map((inv, i) => (
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
            ))}
          </tbody>
          {invoices.length > 0 && (
            <tfoot>
              {currencyTotals.map(([cur, t], idx) => (
                <tr key={cur} className={`${idx === 0 ? "border-t-2 border-[#2563eb]" : "border-t border-gray-200"} bg-gray-50 font-semibold`}>
                  <td colSpan={5} className="px-4 py-2">
                    {`Gesamt (${t.invoices} Rechnungen, ${t.positions} Positionen)`}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{cur}</td>
                  <td className="px-4 py-2 text-right">
                    {t.amount.toLocaleString("de-AT", { minimumFractionDigits: 2 })}
                  </td>
                  <td></td>
                  <td className="px-4 py-2 text-right text-emerald-700">
                    {t.provision.toLocaleString("de-AT", { minimumFractionDigits: 2 })}
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
