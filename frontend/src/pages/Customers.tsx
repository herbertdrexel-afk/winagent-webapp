import { useEffect, useState } from "react";
import { api, type Customer, type SyncResult } from "../api";
import CustomerEditModal from "../components/CustomerEditModal";
import { RefreshCw } from "lucide-react";

export default function Customers() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Customer | null | undefined>(undefined);
  const [syncing, setSyncing]       = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [lastSync, setLastSync]     = useState<string | null>(null);
  // undefined = geschlossen, null = Neuanlage, Customer = bearbeiten

  useEffect(() => {
    api.sync.status().then((s) => setLastSync(s.last_sync)).catch(() => {});
  }, []);

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

  async function runSync() {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await api.sync.customers();
      setSyncResult(result);
      const s = await api.sync.status();
      setLastSync(s.last_sync);
      // Kundenliste neu laden
      const fresh = await api.customers.list(search || undefined);
      setCustomers(fresh);
    } catch (e: unknown) {
      setSyncResult({ ok: false, total: 0, message: e instanceof Error ? e.message : "Fehler" });
    } finally { setSyncing(false); }
  }

  function handleSaved(saved: Customer) {
    setCustomers((prev) => {
      const idx = prev.findIndex((c) => c.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setEditing(undefined);
  }

  return (
    <>
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-gray-800">Kunden</h1>
        <div className="flex gap-3">
          <input
            type="search"
            placeholder="Name, Code, Kd-Nr, Ort…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
          />
          <button
            onClick={() => setEditing(null)}
            className="bg-[#2563eb] text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 transition-colors"
          >
            + Neuer Kunde
          </button>
        </div>
      </div>

      {error && <div className="text-red-600 mb-3">Fehler: {error}</div>}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead className="bg-[#2563eb] text-white">
            <tr>
              {["Kd-Nr", "Code", "Name", "PLZ / Ort", "Land", "E-Mail", "Kontakt"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Lade…</td></tr>
            ) : customers.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Keine Treffer</td></tr>
            ) : customers.map((c, i) => (
              <tr
                key={c.id}
                onClick={() => setEditing(c)}
                className={
                  (i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40") +
                  " cursor-pointer hover:bg-[#2563eb]/10 transition-colors"
                }
                title="Klicken zum Bearbeiten"
              >
                <td className="px-4 py-2 text-gray-500 text-xs">{c.ku_nr ?? "–"}</td>
                <td className="px-4 py-2 font-mono text-xs font-semibold text-[#2563eb]">{c.code}</td>
                <td className="px-4 py-2 font-medium">{c.name}</td>
                <td className="px-4 py-2 text-gray-600">{[c.zip, c.city].filter(Boolean).join(" ") || "–"}</td>
                <td className="px-4 py-2 text-gray-600">{c.country_code ?? "–"}</td>
                <td className="px-4 py-2 text-gray-500">{c.email ?? "–"}</td>
                <td className="px-4 py-2 text-gray-500 text-xs">{c.contact_name ?? "–"}</td>
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

    {/* Reybex Sync */}
    <div className="bg-white rounded-xl border border-gray-200 px-5 py-3 flex items-center gap-4 flex-wrap mt-4">
      <RefreshCw size={16} className="text-[#2563eb] shrink-0" />
      <span className="font-medium text-sm text-gray-700">Reybex Kunden-Sync</span>
      <button onClick={runSync} disabled={syncing}
        className="flex items-center gap-1.5 border border-[#2563eb] text-[#2563eb] px-3 py-1 rounded-lg text-xs font-medium hover:bg-[#2563eb]/5 disabled:opacity-50 transition-colors">
        <RefreshCw size={12} className={syncing ? "animate-spin" : ""} />
        {syncing ? "Synchronisiere…" : "Jetzt synchronisieren"}
      </button>
      {lastSync && <span className="text-xs text-gray-400">Zuletzt: {new Date(lastSync).toLocaleString("de-AT")}</span>}
      <span className="text-xs text-gray-300">· Automatisch stündlich</span>
      {syncResult && (
        <span className={`text-xs px-2 py-0.5 rounded-full ${syncResult.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"}`}>
          {syncResult.ok ? `✓ ${syncResult.total} Kunden` : `✗ ${syncResult.message}`}
        </span>
      )}
    </div>

    {editing !== undefined && (
      <CustomerEditModal
        customer={editing}
        onClose={() => setEditing(undefined)}
        onSaved={handleSaved}
      />
    )}
    </>
  );
}
