import { useEffect, useState } from "react";
import { api, token, type InvoiceSummary } from "../api";

interface Props {
  supplierCode: string;
  periodFrom: string;
  periodTo: string;
  onClose: () => void;
}

function fmt(n: number) {
  return n.toLocaleString("de-AT", { minimumFractionDigits: 2 });
}

export default function CommissionInvoiceModal({ supplierCode, periodFrom, periodTo, onClose }: Props) {
  const [summary, setSummary] = useState<InvoiceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().slice(0, 10));
  const [prSeq, setPrSeq] = useState(0);
  const [downloading, setDownloading] = useState<"pdf" | "dbf" | null>(null);

  useEffect(() => {
    api.commission.invoiceSummary(supplierCode, periodFrom, periodTo)
      .then((s) => { setSummary(s); setPrSeq(s.next_pr_seq); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function download(type: "pdf" | "dbf") {
    if (!summary) return;
    if (type === "pdf") {
      const year = new Date(invoiceDate).getFullYear() % 100;
      const prNrs = summary.totals.map((_, i) =>
        `PR${String(year).padStart(2, "0")}-${String(prSeq + i).padStart(4, "0")}`
      ).join(", ");
      const confirmed = confirm(
        `Provisionsrechnung erstellen und speichern?\n\n` +
        `Lieferant: ${summary.supplier_name}\n` +
        `Zeitraum: ${summary.period_from} bis ${summary.period_to}\n` +
        `PR-Nummer(n): ${prNrs}\n\n` +
        `Die Rechnung wird unter "Provisionsrechnungen" gespeichert.`
      );
      if (!confirmed) return;
    }
    setDownloading(type);
    setError(null);
    const year = new Date(invoiceDate).getFullYear() % 100;
    const payload = {
      invoice_date: invoiceDate,
      period_from: periodFrom,
      period_to: periodTo,
      pr_seq: prSeq,
      totals: summary.totals,
    };
    const url = type === "pdf"
      ? api.commission.invoicePdfUrl(supplierCode)
      : api.commission.ubwExportUrl(supplierCode);

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token.get() ? { Authorization: `Bearer ${token.get()}` } : {}) },
        body: JSON.stringify(payload),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail ?? res.statusText); }
      const blob = await res.blob();
      const prLabel = `PR${String(year).padStart(2, "0")}-${String(prSeq).padStart(4, "0")}`;
      const filename = type === "pdf" ? `${prLabel}.pdf` : "HDUBW_new.DBF";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setDownloading(null);
    }
  }

  const year = new Date(invoiceDate).getFullYear() % 100;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl">

        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">Provisionsrechnung erstellen</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl px-2">✕</button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {loading && <p className="text-gray-400 text-center py-4">Berechne Totals…</p>}
          {error && <p className="text-red-600 text-sm">{error}</p>}

          {summary && (
            <>
              <div className="bg-[#f0f5fb] rounded-xl p-4 space-y-1">
                <p className="text-sm font-semibold text-[#1a3a5c]">{summary.supplier_name}</p>
                <p className="text-xs text-gray-500">
                  Zeitraum: {summary.period_from} bis {summary.period_to}
                </p>
              </div>

              {/* Totals per currency */}
              <table className="w-full text-sm border border-gray-200 rounded-xl overflow-hidden">
                <thead className="bg-[#1a3a5c] text-white">
                  <tr>
                    <th className="px-4 py-2 text-left">Währung</th>
                    <th className="px-4 py-2 text-right">Umsatz</th>
                    <th className="px-4 py-2 text-right">Provision</th>
                    <th className="px-4 py-2 text-left font-normal text-white/70">PR-Nr.</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.totals.map((t, i) => (
                    <tr key={t.currency} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                      <td className="px-4 py-2 font-medium">{t.currency}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{fmt(t.total_amount)}</td>
                      <td className="px-4 py-2 text-right font-semibold text-emerald-700">{fmt(t.provision_amount)}</td>
                      <td className="px-4 py-2 text-gray-500 font-mono text-xs">
                        PR{String(year).padStart(2,"0")}-{String(prSeq + i).padStart(4,"0")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Date + PR number */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Rechnungsdatum</label>
                  <input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">PR-Nummer ab</label>
                  <input type="number" value={prSeq} onChange={(e) => setPrSeq(parseInt(e.target.value) || 0)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex gap-3 pt-2 border-t border-gray-100">
                <button onClick={() => download("pdf")} disabled={!!downloading}
                  className="flex-1 py-2.5 rounded-lg text-sm font-medium bg-[#1a3a5c] text-white hover:bg-[#1a3a5c]/80 disabled:opacity-50">
                  {downloading === "pdf" ? "Generiere…" : "📄 Rechnung PDF"}
                </button>
              </div>
              <p className="text-xs text-gray-400 text-center">
                HDUBW_new.DBF in dein HDAGENTA-Verzeichnis kopieren und mit bestehender HDUBW.DBF zusammenführen
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
