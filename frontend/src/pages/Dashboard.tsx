import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Supplier, type SyncResult } from "../api";
import {
  Building2, Users, FileText, Receipt, TrendingUp, ArrowRight, RefreshCw,
} from "lucide-react";

export default function Dashboard() {
  const navigate = useNavigate();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [lastSync, setLastSync] = useState<string | null>(null);

  useEffect(() => {
    api.suppliers.list().then(setSuppliers).catch(() => {});
    api.sync.status().then((s) => setLastSync(s.last_sync)).catch(() => {});
  }, []);

  async function runSync() {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await api.sync.customers();
      setSyncResult(result);
      const s = await api.sync.status();
      setLastSync(s.last_sync);
    } catch (e: unknown) {
      setSyncResult({ ok: false, total: 0, message: e instanceof Error ? e.message : "Fehler" });
    } finally {
      setSyncing(false);
    }
  }

  const tiles = [
    {
      label: "Lieferanten",
      icon: Building2,
      color: "bg-blue-50 text-blue-700 border-blue-200",
      iconBg: "bg-blue-100",
      value: suppliers.length,
      sub: "aktive Lieferanten",
      to: "/suppliers",
    },
    {
      label: "Rechnungen",
      icon: FileText,
      color: "bg-emerald-50 text-emerald-700 border-emerald-200",
      iconBg: "bg-emerald-100",
      value: null,
      sub: "Transaktionen verwalten",
      to: "/transactions",
    },
    {
      label: "Provisionsrechnungen",
      icon: Receipt,
      color: "bg-violet-50 text-violet-700 border-violet-200",
      iconBg: "bg-violet-100",
      value: null,
      sub: "PR-Liste & Nachdruck",
      to: "/commission-invoices",
    },
    {
      label: "Kunden",
      icon: Users,
      color: "bg-amber-50 text-amber-700 border-amber-200",
      iconBg: "bg-amber-100",
      value: null,
      sub: "Kundenstamm",
      to: "/customers",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-800">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Willkommen bei WinAgent</p>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {tiles.map(({ label, icon: Icon, color, iconBg, value, sub, to }) => (
          <button
            key={to}
            onClick={() => navigate(to)}
            className={`flex items-start gap-4 p-5 rounded-xl border text-left hover:shadow-md transition-all ${color}`}
          >
            <div className={`p-2.5 rounded-lg ${iconBg}`}>
              <Icon size={22} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-base leading-tight">{label}</div>
              {value != null
                ? <div className="text-2xl font-bold mt-1">{value}</div>
                : <div className="text-xs mt-1 opacity-70">{sub}</div>
              }
              {value != null && <div className="text-xs mt-0.5 opacity-70">{sub}</div>}
            </div>
            <ArrowRight size={16} className="opacity-40 mt-1 shrink-0" />
          </button>
        ))}
      </div>

      {/* Reybex Sync */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center gap-2 mb-4">
          <RefreshCw size={18} className="text-[#1a3a5c]" />
          <h2 className="font-semibold text-gray-800">Reybex Synchronisation</h2>
          <span className="ml-auto text-xs text-gray-400">Reybex → WinAgent</span>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <button onClick={runSync} disabled={syncing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#1a3a5c] text-[#1a3a5c] text-sm font-medium hover:bg-[#1a3a5c]/5 disabled:opacity-50 transition-colors">
            <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
            {syncing ? "Synchronisiere…" : "Kunden jetzt synchronisieren"}
          </button>
          {lastSync && (
            <span className="text-xs text-gray-400">
              Zuletzt: {new Date(lastSync).toLocaleString("de-AT")}
            </span>
          )}
          <span className="text-xs text-gray-300">· Automatisch stündlich</span>
        </div>
        {syncResult && (
          <div className={`mt-3 px-4 py-2.5 rounded-lg text-sm ${syncResult.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
            {syncResult.ok
              ? `✓ Kunden: ${syncResult.total} gesamt — ${syncResult.created} neu, ${syncResult.updated} aktualisiert, ${syncResult.skipped} übersprungen`
              : `✗ Fehler: ${syncResult.message}`
            }
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={18} className="text-[#1a3a5c]" />
            <h2 className="font-semibold text-gray-800">Lieferanten</h2>
          </div>
          {suppliers.length === 0
            ? <p className="text-sm text-gray-400">Lade…</p>
            : (
              <div className="space-y-2">
                {suppliers.slice(0, 8).map((s) => (
                  <div key={s.id}
                    onClick={() => navigate(`/transactions?supplier=${s.code}`)}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-[#1a3a5c]/5 cursor-pointer transition-colors"
                  >
                    <span className="w-8 h-8 rounded-full bg-[#1a3a5c]/10 text-[#1a3a5c] text-xs font-bold flex items-center justify-center shrink-0">
                      {s.code}
                    </span>
                    <span className="text-sm font-medium text-gray-700 truncate">{s.name}</span>
                    <span className="ml-auto text-xs text-gray-400">{s.default_currency ?? ""}</span>
                    <ArrowRight size={14} className="text-gray-300 shrink-0" />
                  </div>
                ))}
                {suppliers.length > 8 && (
                  <button onClick={() => navigate("/suppliers")}
                    className="text-xs text-[#1a3a5c] hover:underline mt-1">
                    Alle {suppliers.length} Lieferanten anzeigen →
                  </button>
                )}
              </div>
            )
          }
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Receipt size={18} className="text-[#1a3a5c]" />
            <h2 className="font-semibold text-gray-800">Schnellzugriff</h2>
          </div>
          <div className="space-y-2">
            {[
              { label: "Neue Rechnung erfassen", to: "/transactions", icon: FileText },
              { label: "PDF importieren", to: "/transactions", icon: FileText },
              { label: "Provisionsrechnung erstellen", to: "/transactions", icon: Receipt },
              { label: "Provisionsrechnungen ansehen", to: "/commission-invoices", icon: Receipt },
              { label: "Kundenstamm verwalten", to: "/customers", icon: Users },
            ].map(({ label, to, icon: Icon }) => (
              <button key={label} onClick={() => navigate(to)}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-[#1a3a5c]/5 text-left transition-colors group">
                <Icon size={15} className="text-[#1a3a5c]/50 shrink-0" />
                <span className="text-sm text-gray-700 group-hover:text-[#1a3a5c]">{label}</span>
                <ArrowRight size={13} className="ml-auto text-gray-300 group-hover:text-[#1a3a5c]/50" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
