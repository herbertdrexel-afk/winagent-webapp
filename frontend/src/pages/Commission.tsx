import { useEffect, useState } from "react";
import { api, type CommissionStatement, type Supplier } from "../api";

function today() { return new Date().toISOString().slice(0, 10); }
function yearStart() { return new Date().getFullYear() + "-01-01"; }

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
      status === "issued" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
    }`}>
      {status === "issued" ? "Ausgestellt" : "Entwurf"}
    </span>
  );
}

export default function Commission() {
  const [statements, setStatements] = useState<CommissionStatement[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);

  // Formular
  const [supplierCode, setSupplierCode] = useState("");
  const [from, setFrom] = useState(yearStart());
  const [to, setTo] = useState(today());
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function reload() {
    return api.commission.statements().then(setStatements);
  }

  useEffect(() => {
    Promise.all([
      reload(),
      api.suppliers.list().then((s) => { setSuppliers(s); if (s.length) setSupplierCode(s[0].code); }),
    ]).finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setFormError(null);
    try {
      await api.commission.create({ supplier_code: supplierCode, period_from: from, period_to: to });
      await reload();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setCreating(false);
    }
  }

  async function handleIssue(id: number) {
    await api.commission.issue(id);
    await reload();
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-800 mb-4">Provisionsabrechnungen</h1>

      {/* Neue Abrechnung anlegen */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Neue Abrechnung erstellen</h2>
        <form onSubmit={handleCreate} className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Lieferant</label>
            <select value={supplierCode} onChange={(e) => setSupplierCode(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30">
              {suppliers.map((s) => (
                <option key={s.id} value={s.code}>{s.code} – {s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Von</label>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Bis</label>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
          </div>
          <button type="submit" disabled={creating}
            className="bg-[#2563eb] text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 transition-colors disabled:opacity-50">
            {creating ? "Erstelle…" : "Erstellen"}
          </button>
          {formError && <span className="text-red-600 text-sm">{formError}</span>}
        </form>
      </div>

      {/* Tabelle */}
      {loading ? (
        <div className="text-gray-400">Lade…</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead className="bg-[#2563eb] text-white">
              <tr>
                {["Nr.", "Rg.-Nummer", "Zeitraum", "Datum", "Umsatz", "Provision", "Währg.", "Status", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {statements.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">Keine Abrechnungen</td></tr>
              ) : statements.map((s, i) => (
                <tr key={s.id} className={i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40"}>
                  <td className="px-4 py-2 text-gray-400 text-xs">{s.id}</td>
                  <td className="px-4 py-2 font-mono font-semibold text-[#2563eb]">
                    {s.statement_number ?? "–"}
                  </td>
                  <td className="px-4 py-2 text-gray-600 text-xs">
                    {s.period_from} – {s.period_to}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{s.statement_date ?? "–"}</td>
                  <td className="px-4 py-2 text-right">
                    {s.total_amount
                      ? parseFloat(s.total_amount).toLocaleString("de-AT", { minimumFractionDigits: 2 })
                      : "–"}
                  </td>
                  <td className="px-4 py-2 text-right font-medium text-[#2563eb]">
                    {s.total_provision
                      ? parseFloat(s.total_provision).toLocaleString("de-AT", { minimumFractionDigits: 2 })
                      : "–"}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{s.currency ?? "–"}</td>
                  <td className="px-4 py-2"><StatusBadge status={s.status} /></td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2">
                      {s.status === "draft" && (
                        <button onClick={() => handleIssue(s.id)}
                          className="text-xs px-2 py-1 rounded bg-[#2563eb] text-white hover:bg-[#2563eb]/80">
                          Ausstellen
                        </button>
                      )}
                      <a href={api.commission.pdfUrl(s.id)} target="_blank" rel="noreferrer"
                        className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700 hover:bg-gray-200">
                        PDF
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
