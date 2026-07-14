import { useEffect, useMemo, useState } from "react";
import { api, token, type CommissionInvoiceRecord } from "../api";
import { useSearch } from "../context/SearchContext";
import { useT } from "../context/LocaleContext";
import { RotateCcw } from "lucide-react";

function fmt(n: number | string | undefined) {
  if (n == null) return "–";
  return parseFloat(n as string).toLocaleString("de-AT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type Status = "offen" | "bezahlt" | "in_pruefung";

const STATUS_STYLE: Record<Status, string> = {
  offen:       "background:#fef3c7;color:#92400e",
  bezahlt:     "background:#dcfce7;color:#166534",
  in_pruefung: "background:#dbeafe;color:#1e40af",
};

function StatusBadge({ status }: { status?: string }) {
  const t = useT();
  const key = (status ?? "offen") as Status;
  const labels: Record<string, string> = {
    offen:       t.provisions.statusOpen,
    bezahlt:     t.provisions.statusPaid,
    in_pruefung: t.provisions.statusReview,
  };
  const style = STATUS_STYLE[key] ?? STATUS_STYLE.offen;
  return (
    <span
      className="text-[11px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap"
      style={{ ...Object.fromEntries(style.split(";").map(s => s.split(":"))) } as React.CSSProperties}
    >
      {labels[key] ?? status ?? t.provisions.statusOpen}
    </span>
  );
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
  status: Status;
}

interface ColFilter {
  supplier: string;
  period: string;
  status: string;
}

function authHeaders(): Record<string, string> {
  const t = token.get();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function CommissionInvoices() {
  const { query } = useSearch();
  const t = useT();
  const [rows, setRows] = useState<CommissionInvoiceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [colFilter, setColFilter] = useState<ColFilter>({ supplier: "", period: "", status: "" });

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try { setRows(await api.commission.invoices()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : t.common.error); }
    finally { setLoading(false); }
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
      status: (r.status ?? "offen") as Status,
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
        status: editing.status,
      });
      setEditing(null);
      await load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : t.common.error);
    } finally { setSaving(false); }
  }

  async function del(id: number) {
    if (!confirm("Provisionsrechnung wirklich löschen?")) return;
    try { await api.commission.deleteInvoice(id); await load(); }
    catch (e: unknown) { alert(e instanceof Error ? e.message : t.common.error); }
  }

  async function reprintPdf(id: number, prNumber: string) {
    try {
      const res = await fetch(api.commission.reprintPdfUrl(id), { method: "POST", headers: authHeaders() });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${prNumber}.pdf`;
      a.click();
    } catch (e: unknown) { alert(e instanceof Error ? e.message : t.common.error); }
  }

  async function previewPdf(id: number) {
    try {
      const res = await fetch(api.commission.reprintPdfUrl(id), { method: "POST", headers: authHeaders() });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (e: unknown) { alert(e instanceof Error ? e.message : t.common.error); }
  }

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return rows.filter(r => {
      const matchSearch = !q ||
        (r.supplier_name ?? "").toLowerCase().includes(q) ||
        (r.pr_number ?? "").toLowerCase().includes(q) ||
        (r.description ?? "").toLowerCase().includes(q) ||
        (r.period_from ?? "").includes(q) ||
        (r.period_to ?? "").includes(q);

      const matchSupplier = !colFilter.supplier ||
        (r.supplier_name ?? "").toLowerCase().includes(colFilter.supplier.toLowerCase());
      const matchPeriod = !colFilter.period ||
        r.period_from.includes(colFilter.period) || r.period_to.includes(colFilter.period);
      const matchStatus = !colFilter.status ||
        (r.status ?? "offen") === colFilter.status;

      return matchSearch && matchSupplier && matchPeriod && matchStatus;
    });
  }, [rows, query, colFilter]);

  const hasColFilter = Object.values(colFilter).some(Boolean);
  const inputCls = "w-full px-2 py-1 text-[12px] focus:outline-none bg-white border border-[#d1d5db] rounded focus:border-[#2563eb]";

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <h1 className="text-lg font-semibold text-gray-800 mr-1">{t.provisions.title}</h1>
        <div className="flex-1" />
        {hasColFilter && (
          <button
            onClick={() => setColFilter({ supplier: "", period: "", status: "" })}
            className="flex items-center gap-1.5 text-[12px] px-3 py-1.5 rounded border border-gray-300 text-gray-500 hover:bg-gray-100 transition-colors"
          >
            <RotateCcw size={12} /> {t.provisions.filterReset}
          </button>
        )}
        <button onClick={load}
          className="flex items-center justify-center p-1.5 rounded border border-gray-300 text-gray-500 hover:bg-gray-100 transition-colors"
          title={t.common.refresh}>
          <RotateCcw size={14} />
        </button>
      </div>

      {error && <div className="text-red-600 text-sm">{t.common.error}: {error}</div>}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" style={{ minWidth: 640 }}>
            <thead>
              <tr style={{ background: "#2563eb" }}>
                <th className="px-4 py-2.5 text-left text-white font-medium text-[12px] whitespace-nowrap">{t.provisions.supplier}</th>
                <th className="px-4 py-2.5 text-left text-white font-medium text-[12px] whitespace-nowrap">{t.provisions.prNumber}</th>
                <th className="px-4 py-2.5 text-left text-white font-medium text-[12px] whitespace-nowrap">{t.provisions.period}</th>
                <th className="px-4 py-2.5 text-right text-white font-medium text-[12px] whitespace-nowrap">{t.provisions.amount}</th>
                <th className="px-4 py-2.5 text-left text-white font-medium text-[12px]">{t.provisions.status}</th>
                <th className="px-3 py-2.5 text-right text-white font-medium text-[12px]"></th>
              </tr>
              {/* Inline column filters */}
              <tr style={{ background: "#f7f8fa", borderBottom: "1px solid #e2e5eb" }}>
                <td className="px-2 py-1.5">
                  <input value={colFilter.supplier}
                    onChange={e => setColFilter(f => ({ ...f, supplier: e.target.value }))}
                    placeholder={t.provisions.filterSupplier}
                    className={inputCls} />
                </td>
                <td className="px-2 py-1.5" />
                <td className="px-2 py-1.5">
                  <input value={colFilter.period}
                    onChange={e => setColFilter(f => ({ ...f, period: e.target.value }))}
                    placeholder={t.provisions.filterPeriod}
                    className={inputCls} />
                </td>
                <td />
                <td className="px-2 py-1.5">
                  <select value={colFilter.status}
                    onChange={e => setColFilter(f => ({ ...f, status: e.target.value }))}
                    className={inputCls}>
                    <option value="">{t.provisions.statusAll}</option>
                    <option value="offen">{t.provisions.statusOpen}</option>
                    <option value="in_pruefung">{t.provisions.statusReview}</option>
                    <option value="bezahlt">{t.provisions.statusPaid}</option>
                  </select>
                </td>
                <td />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">{t.common.loading}</td></tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    {rows.length === 0 ? t.provisions.noEntries : t.provisions.noFilterEntries}
                  </td>
                </tr>
              ) : filtered.map((r, i) => (
                <tr key={r.id}
                  className="border-t border-gray-100 hover:bg-[#eff6ff] transition-colors"
                  style={{ background: i % 2 === 0 ? "#fff" : "#f9fafb" }}>
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-gray-800 text-[13px]">{r.supplier_name ?? "–"}</div>
                    <div className="text-[11px] text-gray-400 font-mono">{r.supplier_code}</div>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[12px] text-[#2563eb] font-semibold whitespace-nowrap">{r.pr_number}</td>
                  <td className="px-4 py-2.5 text-[13px] text-gray-600 whitespace-nowrap">{r.period_from} – {r.period_to}</td>
                  <td className="px-4 py-2.5 text-right font-semibold text-[13px] text-gray-800 whitespace-nowrap font-mono">
                    {fmt(r.amount)} <span className="text-gray-400 font-normal text-[11px]">{r.currency}</span>
                  </td>
                  <td className="px-4 py-2.5"><StatusBadge status={r.status} /></td>
                  <td className="px-3 py-2.5">
                    <div className="flex gap-1 justify-end items-center">
                      <button onClick={() => reprintPdf(r.id, r.pr_number)} title="PDF"
                        className="text-[#2563eb] hover:bg-[#2563eb]/10 px-1.5 py-0.5 rounded text-xs border border-[#2563eb]/30 transition-colors">
                        {t.provisions.pdfPreview}
                      </button>
                      <button onClick={() => previewPdf(r.id)} title="Vorschau"
                        className="text-emerald-600 hover:bg-emerald-50 px-1.5 py-0.5 rounded text-xs border border-emerald-300 transition-colors">🖥</button>
                      <button onClick={() => openEdit(r)} title={t.common.edit}
                        className="text-gray-500 hover:bg-gray-100 px-1.5 py-0.5 rounded text-xs border border-gray-300 transition-colors">✏️</button>
                      <button onClick={() => del(r.id)} title={t.common.delete}
                        className="text-red-400 hover:bg-red-50 px-1.5 py-0.5 rounded text-xs border border-red-200 transition-colors">✕</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length > 0 && (
          <div className="px-4 py-2 text-[11px] text-gray-400 border-t border-gray-100">
            {t.provisions.entries(filtered.length)}
            {filtered.length < rows.length ? ` (${t.provisions.filtered} ${rows.length})` : ""}
          </div>
        )}
      </div>

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
          onClick={e => { if (e.target === e.currentTarget) setEditing(null); }}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-800">{t.provisions.editTitle}</h2>
              <button onClick={() => setEditing(null)} className="text-gray-400 hover:text-gray-600 text-xl px-2">✕</button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">{t.provisions.status}</label>
                <select value={editing.status}
                  onChange={e => setEditing({ ...editing, status: e.target.value as Status })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30">
                  <option value="offen">{t.provisions.statusOpen}</option>
                  <option value="in_pruefung">{t.provisions.statusReview}</option>
                  <option value="bezahlt">{t.provisions.statusPaid}</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{t.provisions.invoiceDate}</label>
                  <input type="date" value={editing.invoice_date}
                    onChange={e => setEditing({ ...editing, invoice_date: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{t.provisions.vCode}</label>
                  <input type="text" value={editing.v_code}
                    onChange={e => setEditing({ ...editing, v_code: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">{t.provisions.description}</label>
                <input type="text" value={editing.description}
                  onChange={e => setEditing({ ...editing, description: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">{t.provisions.amountNet}</label>
                <input type="number" step="0.01" value={editing.amount}
                  onChange={e => setEditing({ ...editing, amount: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{t.provisions.periodFrom}</label>
                  <input type="date" value={editing.period_from}
                    onChange={e => setEditing({ ...editing, period_from: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{t.provisions.periodTo}</label>
                  <input type="date" value={editing.period_to}
                    onChange={e => setEditing({ ...editing, period_to: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">{t.provisions.notes}</label>
                <textarea value={editing.notes} rows={2}
                  onChange={e => setEditing({ ...editing, notes: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
              </div>
              <div className="flex gap-3 pt-2 border-t border-gray-100">
                <button onClick={() => setEditing(null)}
                  className="flex-1 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-600 hover:bg-gray-50">
                  {t.common.cancel}
                </button>
                <button onClick={save} disabled={saving}
                  className="flex-1 py-2 rounded-lg text-sm font-medium bg-[#2563eb] text-white hover:bg-[#2563eb]/80 disabled:opacity-50">
                  {saving ? t.common.saving : t.common.save}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
