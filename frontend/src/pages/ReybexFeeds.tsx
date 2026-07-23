import { useEffect, useState } from "react";
import { api, type Supplier, type IngestLogEntry } from "../api";
import { useT } from "../context/LocaleContext";
import { RefreshCw, Download, Save, CheckCircle2 } from "lucide-react";

export default function ReybexFeeds() {
  const t = useT();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [feeds, setFeeds] = useState<Record<string, { url: string }>>({});
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [log, setLog] = useState<IngestLogEntry[]>([]);
  const [saving, setSaving] = useState(false);
  const [pulling, setPulling] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  function loadAll() {
    api.suppliers.list().then(setSuppliers).catch(() => {});
    api.ingest.feeds().then(setFeeds).catch(() => {});
    api.ingest.log().then(setLog).catch(() => {});
  }
  useEffect(() => { loadAll(); }, []);

  function flash(text: string, ok = true) {
    setMsg({ text, ok });
    setTimeout(() => setMsg(null), 6000);
  }

  async function save() {
    const changed = Object.fromEntries(
      Object.entries(inputs).filter(([, v]) => v.trim() !== "")
    );
    if (Object.keys(changed).length === 0) { flash(t.feeds.nothingToSave, false); return; }
    setSaving(true);
    try {
      await api.ingest.setFeeds(changed);
      setInputs({});
      const f = await api.ingest.feeds();
      setFeeds(f);
      flash(t.feeds.saved);
    } catch (e) {
      flash(e instanceof Error ? e.message : t.common.error, false);
    } finally { setSaving(false); }
  }

  async function pull(code: string) {
    setPulling(code);
    try {
      const r = await api.ingest.pull(code);
      flash(t.feeds.pullDone(code, r.new ?? 0, r.updated ?? 0, r.unchanged ?? 0), r.status === "ok");
      api.ingest.log().then(setLog);
    } catch (e) {
      flash(e instanceof Error ? e.message : t.common.error, false);
    } finally { setPulling(null); }
  }

  async function pullAll() {
    setPulling("*");
    try {
      await api.ingest.pullAll();
      flash(t.feeds.pullAllDone);
      api.ingest.log().then(setLog);
    } catch (e) {
      flash(e instanceof Error ? e.message : t.common.error, false);
    } finally { setPulling(null); }
  }

  const configuredCount = Object.keys(feeds).length;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
        <h1 className="text-2xl font-semibold text-gray-800">{t.feeds.title}</h1>
        <div className="flex gap-2">
          <button onClick={save} disabled={saving}
            className="flex items-center gap-1.5 bg-[#2563eb] text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 disabled:opacity-50">
            <Save size={15} /> {saving ? t.common.saving : t.common.save}
          </button>
          <button onClick={pullAll} disabled={pulling !== null || configuredCount === 0}
            className="flex items-center gap-1.5 border border-[#2563eb] text-[#2563eb] px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/10 disabled:opacity-40">
            <RefreshCw size={15} className={pulling === "*" ? "animate-spin" : ""} /> {t.feeds.pullAll}
          </button>
        </div>
      </div>
      <p className="text-sm text-gray-500 mb-4 max-w-3xl">{t.feeds.intro}</p>

      {msg && (
        <div className={`mb-4 rounded-lg px-4 py-2 text-sm ${msg.ok ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
          {msg.text}
        </div>
      )}

      {/* Feeds pro Lieferant */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto mb-6">
        <table className="w-full text-sm" style={{ minWidth: 760 }}>
          <thead className="bg-[#2563eb] text-white">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t.feeds.supplier}</th>
              <th className="px-4 py-3 text-left font-medium">{t.feeds.status}</th>
              <th className="px-4 py-3 text-left font-medium">{t.feeds.feedUrl}</th>
              <th className="px-4 py-3 text-left font-medium">{t.feeds.action}</th>
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s, i) => {
              const cfg = feeds[s.code];
              return (
                <tr key={s.id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <span className="font-mono text-xs text-gray-500 mr-2">{s.code}</span>
                    <span className="font-medium text-gray-800">{s.name}</span>
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    {cfg ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                        <CheckCircle2 size={13} /> {t.feeds.configured}
                        <span className="font-mono text-gray-400 ml-1">{cfg.url}</span>
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">{t.feeds.notConfigured}</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <input
                      type="url"
                      value={inputs[s.code] ?? ""}
                      onChange={e => setInputs(p => ({ ...p, [s.code]: e.target.value }))}
                      placeholder={cfg ? t.feeds.replacePlaceholder : "https://core-backend.reybex.com/api/dataExportFeed?feedToken=…"}
                      className="w-full min-w-[22rem] border border-gray-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
                    />
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap">
                    <button onClick={() => pull(s.code)} disabled={!cfg || pulling !== null}
                      className="flex items-center gap-1.5 text-xs border border-[#2563eb] text-[#2563eb] px-2.5 py-1.5 rounded-lg hover:bg-[#2563eb]/10 disabled:opacity-40">
                      <Download size={13} className={pulling === s.code ? "animate-pulse" : ""} /> {t.feeds.pullNow}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Protokoll */}
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-700">{t.feeds.logTitle}</h2>
        <button onClick={() => api.ingest.log().then(setLog)}
          className="text-xs text-gray-400 hover:text-[#2563eb] flex items-center gap-1">
          <RefreshCw size={12} /> {t.common.refresh}
        </button>
      </div>
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: 720 }}>
          <thead className="bg-gray-100 text-gray-600 text-xs">
            <tr>
              <th className="px-4 py-2 text-left font-medium">{t.feeds.time}</th>
              <th className="px-4 py-2 text-left font-medium">{t.feeds.file}</th>
              <th className="px-4 py-2 text-left font-medium">{t.feeds.status}</th>
              <th className="px-4 py-2 text-right font-medium">{t.feeds.imported}</th>
              <th className="px-4 py-2 text-left font-medium">{t.feeds.detail}</th>
            </tr>
          </thead>
          <tbody>
            {log.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-gray-400">{t.common.noData}</td></tr>
            ) : log.map(r => (
              <tr key={r.id} className="border-t border-gray-100">
                <td className="px-4 py-1.5 text-xs text-gray-500 whitespace-nowrap">
                  {r.created_at ? new Date(r.created_at).toLocaleString("de-DE") : ""}
                </td>
                <td className="px-4 py-1.5 text-xs font-mono text-gray-600">{r.filename}</td>
                <td className="px-4 py-1.5">
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                    r.status === "ok" ? "bg-emerald-100 text-emerald-700"
                    : r.status === "staged" ? "bg-amber-100 text-amber-700"
                    : "bg-red-100 text-red-700"}`}>{r.status}</span>
                </td>
                <td className="px-4 py-1.5 text-right tabular-nums">{r.imported}</td>
                <td className="px-4 py-1.5 text-xs text-gray-500">{r.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
