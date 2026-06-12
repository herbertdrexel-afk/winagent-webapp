import { useEffect, useState } from "react";
import { api, type Customer } from "../api";

export default function Customers() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      api.customers.list(search || undefined)
        .then(setCustomers)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-gray-800">Kunden</h1>
        <input
          type="search"
          placeholder="Suche Name, Code, Ort…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30"
        />
      </div>

      {error && <div className="text-red-600 mb-3">Fehler: {error}</div>}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#1a3a5c] text-white">
            <tr>
              {["Kd-Nr", "Code", "Name", "PLZ / Ort", "Land", "E-Mail"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Lade…</td></tr>
            ) : customers.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Keine Treffer</td></tr>
            ) : customers.map((c, i) => (
              <tr key={c.id} className={i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40"}>
                <td className="px-4 py-2 text-gray-500">{c.ku_nr ?? "–"}</td>
                <td className="px-4 py-2 font-mono text-xs font-semibold text-[#1a3a5c]">{c.code}</td>
                <td className="px-4 py-2 font-medium">{c.name}</td>
                <td className="px-4 py-2 text-gray-600">{c.city ?? "–"}</td>
                <td className="px-4 py-2 text-gray-600">{c.country_code ?? "–"}</td>
                <td className="px-4 py-2 text-gray-500">{c.email ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && customers.length > 0 && (
          <div className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100">
            {customers.length} Kunden
          </div>
        )}
      </div>
    </div>
  );
}
