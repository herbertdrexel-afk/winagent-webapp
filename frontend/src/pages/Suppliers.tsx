import { useEffect, useState } from "react";
import { api, type Supplier } from "../api";

export default function Suppliers() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.suppliers.list()
      .then(setSuppliers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-500">Lade Lieferanten…</div>;
  if (error)   return <div className="text-red-600">Fehler: {error}</div>;

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-800 mb-4">Lieferanten</h1>
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#1a3a5c] text-white">
            <tr>
              {["Code", "Name", "Währung", "Vertreter", "Kontakt", "Provisions-Splits", "Aktiv"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s, i) => (
              <tr key={s.id} className={i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40"}>
                <td className="px-4 py-2 font-mono font-semibold text-[#1a3a5c]">{s.code}</td>
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
  );
}
