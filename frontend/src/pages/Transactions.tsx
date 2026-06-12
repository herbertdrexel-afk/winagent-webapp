import { useEffect, useState } from "react";
import { api, type Supplier, type Transaction } from "../api";
import TransactionEditModal from "../components/TransactionEditModal";

function today() { return new Date().toISOString().slice(0, 10); }
function yearStart() { return "2005-01-01"; }

export default function Transactions() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supplierCode, setSupplierCode] = useState("");
  const [from, setFrom] = useState(yearStart());
  const [to, setTo] = useState(today());
  const [rows, setRows] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Transaction | null>(null);

  useEffect(() => {
    api.suppliers.list().then((s) => {
      setSuppliers(s);
      if (s.length > 0) setSupplierCode(s[0].code);
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

  const total = rows.reduce((s, r) => s + parseFloat(r.total_amount), 0);

  function handleSaved(updated: Transaction) {
    setRows((prev) => prev.map((r) => r.id === updated.id ? updated : r));
    setEditing(null);
  }

  return (
    <>
    <div>
      <h1 className="text-2xl font-semibold text-gray-800 mb-4">Transaktionen</h1>

      {/* Filter-Leiste */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Lieferant</label>
          <select
            value={supplierCode}
            onChange={(e) => setSupplierCode(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30"
          >
            {suppliers.map((s) => (
              <option key={s.id} value={s.code}>{s.code} – {s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Von</label>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Bis</label>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
        </div>
        <button onClick={load}
          className="bg-[#1a3a5c] text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#1a3a5c]/80 transition-colors">
          Laden
        </button>
      </div>

      {error && <div className="text-red-600 mb-3">Fehler: {error}</div>}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#1a3a5c] text-white">
            <tr>
              {["Rg-Nr", "Datum", "Kd-Nr", "Kunde", "Artikel", "Menge", "Satz %", "Währung", "Betrag"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Lade…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                {supplierCode ? "Keine Transaktionen im Zeitraum" : "Lieferant auswählen"}
              </td></tr>
            ) : rows.map((r, i) => (
              <tr
                key={r.id}
                onClick={() => setEditing(r)}
                className={
                  (i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40") +
                  " cursor-pointer hover:bg-[#1a3a5c]/10 transition-colors"
                }
                title="Klicken zum Bearbeiten"
              >
                <td className="px-4 py-2 font-mono text-xs">{r.invoice_number}</td>
                <td className="px-4 py-2 text-gray-600">{r.invoice_date}</td>
                <td className="px-4 py-2 text-gray-500 text-xs">{r.customer_ku_nr ?? r.customer_code ?? "–"}</td>
                <td className="px-4 py-2 font-medium">{r.customer_name ?? "–"}</td>
                <td className="px-4 py-2 text-gray-600">{r.art_nr ?? "–"}</td>
                <td className="px-4 py-2 text-right text-gray-600">{r.quantity ?? "–"}</td>
                <td className="px-4 py-2 text-right text-gray-600">
                  {r.provision_rate ? `${r.provision_rate} %` : "–"}
                </td>
                <td className="px-4 py-2 text-gray-600">{r.currency ?? "–"}</td>
                <td className="px-4 py-2 text-right font-medium">
                  {parseFloat(r.total_amount).toLocaleString("de-AT", { minimumFractionDigits: 2 })}
                </td>
              </tr>
            ))}
          </tbody>
          {rows.length > 0 && (
            <tfoot>
              <tr className="border-t-2 border-[#1a3a5c] bg-gray-50 font-semibold">
                <td colSpan={8} className="px-4 py-2">Gesamt ({rows.length} Positionen)</td>
                <td className="px-4 py-2 text-right">
                  {total.toLocaleString("de-AT", { minimumFractionDigits: 2 })}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>

    {editing && (
      <TransactionEditModal
        transaction={editing}
        onClose={() => setEditing(null)}
        onSaved={handleSaved}
      />
    )}
  </>
  );
}
