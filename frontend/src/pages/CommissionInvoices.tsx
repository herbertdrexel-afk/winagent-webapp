import { useEffect, useState } from "react";
import { api, type CommissionInvoiceRecord } from "../api";
import { token } from "../api";

function fmt(n: number | string | undefined) {
  if (n == null) return "–";
  return parseFloat(n as string).toLocaleString("de-AT", { minimumFractionDigits: 2 });
}

interface EditState {
  id: number;
  description: string;
  amount: string;
  invoice_date: string;
  period_from: string;
  period_to: string;
  v_code: string;
  notes: string;
}

export default function CommissionInvoices() {
  const [rows, setRows] = useState<CommissionInvoiceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setRows(await api.commission.invoices());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setLoading(false);
    }
  }

  function openEdit(r: CommissionInvoiceRecord) {
    setEditing({
      id: r.id,
      description: r.description ?? "",
      amount: String(r.amount),
      invoice_date: r.invoice_date,
      period_from: r.period_from,
      period_to: r.period_to,
      v_code: r.v_code ?? "NA",
      notes: r.notes ?? "",
    });
  }

  async function save() {
    if (!editing) return;
    setSaving(true);
    try {
      await api.commission.updateInvoice(editing.id, {
        description: editing.description,
        amount: parseFloat(editing.amount),
        invoice_date: editing.invoice_date,
        period_from: editing.period_from,
        period_to: editing.period_to,
        v_code: editing.v_code,
        notes: editing.notes || undefined,
      });
      setEditing(null);
      await load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Fehler");
    } finally {
      setSaving(false);
    }
  }

  async function del(id: number) {
    if (!confirm("Provisionsrechnung wirklich löschen?")) return;
    try {
      await api.commission.deleteInvoice(id);
      await load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Fehler");
    }
  }

  async function reprintPdf(id: number, prNumber: string) {
    try {
      const res = await fetch(api.commission.reprintPdfUrl(id), {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${prNumber}.pdf`;
      a.click();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Fehler beim Drucken");
    }
  }

  function authHeaders(): Record<string, string> {
    const t = token.get();
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-gray-800">Provisionsrechnungen</h1>
        <button onClick={load} className="border border-[#2563eb] text-[#2563eb] px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/10 transition-colors">
          Aktualisieren
        </button>
      </div>

      {error && <div className="text-red-600 mb-3">Fehler: {error}</div>}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#2563eb] text-white">
            <tr>
              {["Firma / Name", "Code", "Re.Num.", "Datum", "Bezeichnung", "Wä.", "zu Überweisen", "Zeitraum von", "bis", "V.", ""].map((h) => (
                <th key={h} className="px-3 py-3 text-left font-medium whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={11} className="px-4 py-8 text-center text-gray-400">Lade…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={11} className="px-4 py-8 text-center text-gray-400">
                Noch keine Provisionsrechnungen vorhanden. Rechnungen werden automatisch beim Erstellen eines PDFs gespeichert.
              </td></tr>
            ) : rows.map((r, i) => (
              <tr key={r.id}
                className={(i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40") + " hover:bg-[#2563eb]/10 transition-colors"}
              >
                <td className="px-3 py-2 font-medium">{r.supplier_name ?? "–"}</td>
                <td className="px-3 py-2 text-gray-600 font-mono text-xs">{r.supplier_code ?? "–"}</td>
                <td className="px-3 py-2 font-mono text-xs text-[#2563eb] font-semibold">{r.pr_number}</td>
                <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{r.invoice_date}</td>
                <td className="px-3 py-2 text-gray-700">{r.description ?? "–"}</td>
                <td className="px-3 py-2 text-gray-600">{r.currency}</td>
                <td className="px-3 py-2 text-right font-semibold">{fmt(r.amount)}</td>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{r.period_from}</td>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{r.period_to}</td>
                <td className="px-3 py-2 text-gray-400 text-xs">{r.v_code ?? "NA"}</td>
                <td className="px-3 py-2">
                  <div className="flex gap-1 justify-end">
                    <button
                      onClick={() => reprintPdf(r.id, r.pr_number)}
                      title="PDF drucken"
                      className="text-[#2563eb] hover:text-[#2563eb]/70 px-1.5 py-0.5 rounded text-xs border border-[#2563eb]/30 hover:bg-[#2563eb]/10"
                    >
                      PDF
                    </button>
                    <button
                      onClick={() => openEdit(r)}
                      title="Bearbeiten"
                      className="text-gray-500 hover:text-gray-800 px-1.5 py-0.5 rounded text-xs border border-gray-300 hover:bg-gray-100"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => del(r.id)}
                      title="Löschen"
                      className="text-red-400 hover:text-red-600 px-1.5 py-0.5 rounded text-xs border border-red-200 hover:bg-red-50"
                    >
                      ✕
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setEditing(null); }}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-800">Provisionsrechnung bearbeiten</h2>
              <button onClick={() => setEditing(null)} className="text-gray-400 hover:text-gray-600 text-xl px-2">✕</button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Rechnungsdatum</label>
                  <input type="date" value={editing.invoice_date}
                    onChange={(e) => setEditing({ ...editing, invoice_date: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">V-Code</label>
                  <input type="text" value={editing.v_code}
                    onChange={(e) => setEditing({ ...editing, v_code: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Bezeichnung</label>
                <input type="text" value={editing.description}
                  onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Betrag (zu überweisen)</label>
                <input type="number" step="0.01" value={editing.amount}
                  onChange={(e) => setEditing({ ...editing, amount: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Zeitraum von</label>
                  <input type="date" value={editing.period_from}
                    onChange={(e) => setEditing({ ...editing, period_from: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">bis</label>
                  <input type="date" value={editing.period_to}
                    onChange={(e) => setEditing({ ...editing, period_to: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Notizen</label>
                <textarea value={editing.notes} rows={2}
                  onChange={(e) => setEditing({ ...editing, notes: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
              </div>
              <div className="flex gap-3 pt-2 border-t border-gray-100">
                <button onClick={() => setEditing(null)}
                  className="flex-1 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-600 hover:bg-gray-50">
                  Abbrechen
                </button>
                <button onClick={save} disabled={saving}
                  className="flex-1 py-2 rounded-lg text-sm font-medium bg-[#2563eb] text-white hover:bg-[#2563eb]/80 disabled:opacity-50">
                  {saving ? "Speichere…" : "Speichern"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
