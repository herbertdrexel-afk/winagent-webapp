import { useEffect, useState } from "react";
import { api, type IngestLogEntry } from "../api";
import { useT } from "../context/LocaleContext";
import { RefreshCw } from "lucide-react";

export default function ImportLog() {
  const t = useT();
  const [log, setLog] = useState<IngestLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  function load() {
    setLoading(true);
    api.ingest.log().then(setLog).catch(() => {}).finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, []);

  const rows = q.trim()
    ? log.filter(r => {
        const s = q.toLowerCase();
        return (r.filename ?? "").toLowerCase().includes(s)
          || (r.source ?? "").toLowerCase().includes(s)
          || (r.detail ?? "").toLowerCase().includes(s)
          || (r.status ?? "").toLowerCase().includes(s);
      })
    : log;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
        <h1 className="text-2xl font-semibold text-gray-800">{t.log.title}</h1>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-1.5 border border-[#2563eb] text-[#2563eb] px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/10 disabled:opacity-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> {t.common.refresh}
        </button>
      </div>
      <p className="text-sm text-gray-500 mb-4 max-w-3xl">{t.log.intro}</p>

      <div className="mb-3">
        <input type="search" value={q} onChange={e => setQ(e.target.value)}
          placeholder={t.log.search}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-72 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: 820 }}>
          <thead className="bg-[#2563eb] text-white">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">{t.log.time}</th>
              <th className="px-4 py-2.5 text-left font-medium">{t.log.source}</th>
              <th className="px-4 py-2.5 text-left font-medium">{t.log.file}</th>
              <th className="px-4 py-2.5 text-left font-medium">{t.log.type}</th>
              <th className="px-4 py-2.5 text-left font-medium">{t.log.status}</th>
              <th className="px-4 py-2.5 text-right font-medium">{t.log.imported}</th>
              <th className="px-4 py-2.5 text-right font-medium">{t.log.skipped}</th>
              <th className="px-4 py-2.5 text-left font-medium">{t.log.detail}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">{t.common.loading}</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">{t.common.noData}</td></tr>
            ) : rows.map((r, i) => (
              <tr key={r.id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                <td className="px-4 py-2 text-xs text-gray-500 whitespace-nowrap">
                  {r.created_at ? new Date(r.created_at).toLocaleString("de-DE") : ""}
                </td>
                <td className="px-4 py-2 text-xs text-gray-600 whitespace-nowrap">{r.source}</td>
                <td className="px-4 py-2 text-xs font-mono text-gray-700">{r.filename}</td>
                <td className="px-4 py-2 text-xs text-gray-500 uppercase">{r.file_type}</td>
                <td className="px-4 py-2">
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                    r.status === "ok" ? "bg-emerald-100 text-emerald-700"
                    : r.status === "staged" ? "bg-amber-100 text-amber-700"
                    : "bg-red-100 text-red-700"}`}>{r.status}</span>
                </td>
                <td className="px-4 py-2 text-right tabular-nums">{r.imported}</td>
                <td className="px-4 py-2 text-right tabular-nums text-gray-500">{r.skipped}</td>
                <td className="px-4 py-2 text-xs text-gray-600">{r.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!loading && (
        <p className="text-[11px] text-gray-400 mt-2">{t.log.count(rows.length)}</p>
      )}
    </div>
  );
}
