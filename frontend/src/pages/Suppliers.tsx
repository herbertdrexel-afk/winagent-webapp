import { useEffect, useState } from "react";
import { api, type Supplier } from "../api";
import SupplierEditModal from "../components/SupplierEditModal";

export default function Suppliers() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Supplier | null | undefined>(undefined);
  // undefined = modal geschlossen, null = Neuanlage, Supplier = bearbeiten

  useEffect(() => {
    api.suppliers.list()
      .then(setSuppliers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function handleSaved(saved: Supplier) {
    setSuppliers((prev) => {
      const idx = prev.findIndex((s) => s.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next.sort((a, b) => a.code.localeCompare(b.code));
      }
      return [...prev, saved].sort((a, b) => a.code.localeCompare(b.code));
    });
    setEditing(undefined);
  }

  if (loading) return <div className="text-gray-500">Lade Lieferanten…</div>;
  if (error)   return <div className="text-red-600">Fehler: {error}</div>;

  return (
    <>
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-gray-800">Lieferanten</h1>
        <button
          onClick={() => setEditing(null)}
          className="bg-[#2563eb] text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 transition-colors"
        >
          + Neuer Lieferant
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm min-w-[600px]">
          <thead className="bg-[#2563eb] text-white">
            <tr>
              {["Code", "Name", "Währung", "Vertreter", "Kontakt", "Provisions-Splits", "Aktiv"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s, i) => (
              <tr
                key={s.id}
                onClick={() => setEditing(s)}
                className={
                  (i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40") +
                  " cursor-pointer hover:bg-[#2563eb]/10 transition-colors"
                }
                title="Klicken zum Bearbeiten"
              >
                <td className="px-4 py-2 font-mono font-semibold text-[#2563eb]">{s.code}</td>
                <td className="px-4 py-2 font-medium">{s.name}</td>
                <td className="px-4 py-2 text-gray-600">{s.default_currency ?? "–"}</td>
                <td className="px-4 py-2 text-gray-600">{s.representative_code ?? "–"}</td>
                <td className="px-4 py-2 text-gray-600">{s.contact_person ?? "–"}</td>
                <td className="px-4 py-2 text-gray-500 text-xs">
                  {s.provision_splits
                    ? s.provision_splits.map((p) => `${p.rate}% (${p.rep_code})`).join(", ")
                    : "–"}
                </td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    s.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                  }`}>
                    {s.is_active ? "Ja" : "Nein"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>

    {editing !== undefined && (
      <SupplierEditModal
        supplier={editing}
        onClose={() => setEditing(undefined)}
        onSaved={handleSaved}
      />
    )}
    </>
  );
}
