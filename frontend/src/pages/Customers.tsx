import { useEffect, useState } from "react";
import { api, type Customer, type DupGroup } from "../api";
import { useT } from "../context/LocaleContext";
import CustomerEditModal from "../components/CustomerEditModal";

export default function Customers() {
  const t = useT();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Customer | null | undefined>(undefined);
  const [selected, setSelected] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [dups, setDups] = useState<DupGroup[] | null>(null);
  const [dupBusy, setDupBusy] = useState(false);

  async function loadDuplicates() {
    setDupBusy(true);
    try {
      const res = await api.customers.duplicates();
      setDups(res.groups);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally { setDupBusy(false); }
  }
  // undefined = geschlossen, null = Neuanlage, Customer = bearbeiten

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      api.customers.list(search || undefined, 100000)
        .then(setCustomers)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  function handleDeleted(code: string) {
    setCustomers((prev) => prev.filter((c) => c.code !== code));
    setSelected((s) => (s?.code === code ? null : s));
    setEditing(undefined);
  }

  async function handleDeleteSelected() {
    if (!selected) return;
    if (!window.confirm(`Kunde „${selected.name}" (${selected.code}) wirklich löschen?`)) return;
    setError(null);
    setDeleting(true);
    try {
      await api.customers.delete(selected.code);
      handleDeleted(selected.code);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Fehler beim Löschen");
    } finally {
      setDeleting(false);
    }
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
        <h1 className="text-2xl font-semibold text-gray-800">{t.customers.title}</h1>
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
            {t.customers.newCustomer}
          </button>
          <button
            onClick={handleDeleteSelected}
            disabled={!selected || deleting}
            title={selected ? `„${selected.name}" löschen` : "Zeile markieren zum Löschen"}
            className="border border-red-300 text-red-600 px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {deleting ? "Löscht…" : t.common.delete}
          </button>
          <button
            onClick={() => { if (dups) setDups(null); else loadDuplicates(); }}
            disabled={dupBusy}
            className="border border-[#2563eb] text-[#2563eb] px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#2563eb]/5 disabled:opacity-50 transition-colors"
          >
            {dupBusy ? "Prüfe…" : dups ? "Duplikate ausblenden" : "Duplikate prüfen"}
          </button>
        </div>
      </div>

      {error && <div className="text-red-600 mb-3">{t.common.error}: {error}</div>}

      {dups && (
        <div className="bg-white rounded-xl shadow-sm border border-amber-200 mb-4 overflow-hidden">
          <div className="px-4 py-2.5 bg-amber-50 border-b border-amber-100 text-sm font-semibold text-amber-800">
            Doppelte Kunden (gleicher Name, mehrere Adressnummern): {dups.length}
            <span className="font-normal text-amber-700"> · „vor 2026" = in Rechnungen vor 2026 verwendete Adressnummer</span>
          </div>
          {dups.length === 0 ? (
            <div className="px-4 py-6 text-center text-gray-400 text-sm">Keine Duplikate mit Rechnungen gefunden.</div>
          ) : (
            <div className="overflow-x-auto max-h-[60vh] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 text-xs sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Name</th>
                    <th className="px-3 py-2 text-left font-medium">Kd-Nr</th>
                    <th className="px-3 py-2 text-left font-medium">Code</th>
                    <th className="px-3 py-2 text-left font-medium">Ort</th>
                    <th className="px-3 py-2 text-right font-medium">Rg. gesamt</th>
                    <th className="px-3 py-2 text-right font-medium">vor 2026</th>
                    <th className="px-3 py-2 text-right font-medium">ab 2026</th>
                    <th className="px-3 py-2 text-left font-medium">Zeitraum</th>
                  </tr>
                </thead>
                <tbody>
                  {dups.map((g, gi) => (
                    g.customers.map((c, ci) => (
                      <tr key={`${gi}-${c.id}`} className={`${ci === 0 ? "border-t-2 border-amber-200" : "border-t border-gray-100"} ${c.used_before_cutover ? "bg-amber-50/40" : ""}`}>
                        <td className="px-3 py-1.5">{ci === 0 ? <span className="font-medium">{g.name}</span> : <span className="text-gray-300">↳</span>}</td>
                        <td className="px-3 py-1.5 font-mono text-xs font-semibold text-[#2563eb]">{c.ku_nr ?? "–"}</td>
                        <td className="px-3 py-1.5 font-mono text-xs">{c.code}</td>
                        <td className="px-3 py-1.5 text-gray-600">{[c.zip, c.city].filter(Boolean).join(" ") || "–"}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{c.tx_total}</td>
                        <td className={`px-3 py-1.5 text-right tabular-nums ${c.tx_before ? "font-semibold text-amber-700" : "text-gray-300"}`}>{c.tx_before || "–"}</td>
                        <td className={`px-3 py-1.5 text-right tabular-nums ${c.tx_from_cutover ? "text-emerald-700" : "text-gray-300"}`}>{c.tx_from_cutover || "–"}</td>
                        <td className="px-3 py-1.5 text-xs text-gray-500">
                          {c.first_invoice ? `${c.first_invoice.slice(0,7)} – ${c.last_invoice?.slice(0,7)}` : "–"}
                        </td>
                      </tr>
                    ))
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead className="bg-[#2563eb] text-white">
            <tr>
              <th className="px-3 py-3 w-8"></th>
              {["Kd-Nr", "Code", "Name", "PLZ / Ort", "Land", "E-Mail", "Kontakt"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">{t.common.loading}</td></tr>
            ) : customers.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">{t.customers.noData}</td></tr>
            ) : customers.map((c, i) => (
              <tr
                key={c.id}
                onClick={() => setEditing(c)}
                className={
                  (selected?.id === c.id
                    ? "bg-[#2563eb]/15"
                    : i % 2 === 0 ? "bg-white" : "bg-[#dce8f5]/40") +
                  " cursor-pointer hover:bg-[#2563eb]/10 transition-colors"
                }
                title="Klicken zum Bearbeiten"
              >
                <td className="px-3 py-2 text-center" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="radio"
                    name="customer-select"
                    checked={selected?.id === c.id}
                    onChange={() => setSelected(c)}
                    className="accent-[#2563eb] cursor-pointer"
                    title="Zeile markieren"
                  />
                </td>
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
