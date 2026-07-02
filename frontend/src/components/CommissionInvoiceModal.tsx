import { useEffect, useState } from "react";
import { api, token, type InvoiceSummary } from "../api";

interface Props {
  supplierCode: string;
  periodFrom: string;
  periodTo: string;
  onClose: () => void;
}

type Mode = "invoice_and_list" | "list_only";
type Output = "screen" | "download";

function fmt(n: number) {
  return n.toLocaleString("de-AT", { minimumFractionDigits: 2 });
}

export default function CommissionInvoiceModal({ supplierCode, periodFrom, periodTo, onClose }: Props) {
  const [summary, setSummary] = useState<InvoiceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().slice(0, 10));
  const [prSeq, setPrSeq] = useState(0);
  const [mode, setMode] = useState<Mode>("invoice_and_list");
  const [output, setOutput] = useState<Output>("download");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.commission.invoiceSummary(supplierCode, periodFrom, periodTo)
      .then((s) => { setSummary(s); setPrSeq(s.next_pr_seq); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function _fetchPdf(url: string, body: object, filename: string, openInTab = false) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token.get() ? { Authorization: `Bearer ${token.get()}` } : {}) },
      body: JSON.stringify(body),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail ?? res.statusText); }
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    if (openInTab) {
      window.open(blobUrl, "_blank");
    } else {
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      a.click();
    }
  }

  async function handleAction() {
    if (!summary) return;
    const year = new Date(invoiceDate).getFullYear() % 100;
    const yearStr = String(year).padStart(2, "0");
    const prLabel = `PR${yearStr}-${String(prSeq).padStart(4, "0")}`;

    if (mode === "invoice_and_list") {
      const prNrs = summary.totals.map((_, i) =>
        `PR${yearStr}-${String(prSeq + i).padStart(4, "0")}`
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

    setBusy(true);
    setError(null);
    try {
      if (mode === "invoice_and_list") {
        // 1. Invoice PDF (saves to DB)
        await _fetchPdf(
          api.commission.invoicePdfUrl(supplierCode),
          { invoice_date: invoiceDate, period_from: periodFrom, period_to: periodTo, pr_seq: prSeq, totals: summary.totals },
          `${prLabel}.pdf`,
        );
      }
      // Aufstellung PDF (always)
      await _fetchPdf(
        api.commission.aufstellungPdfUrl(supplierCode),
        { period_from: periodFrom, period_to: periodTo, print_date: invoiceDate, compact: mode === "list_only" },
        `Aufstellung_${supplierCode}_${periodFrom}_${periodTo}.pdf`,
        output === "screen",
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setBusy(false);
    }
  }

  const year = new Date(invoiceDate).getFullYear() % 100;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl">

        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">Provisionsabrechnung</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl px-2">✕</button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {loading && <p className="text-gray-400 text-center py-4">Berechne Totals…</p>}
          {error && <p className="text-red-600 text-sm">{error}</p>}

          {summary && (
            <>
              <div className="bg-[#f0f5fb] rounded-xl p-4 space-y-1">
                <p className="text-sm font-semibold text-[#2563eb]">{summary.supplier_name}</p>
                <p className="text-xs text-gray-500">
                  Zeitraum: {summary.period_from} bis {summary.period_to}
                </p>
              </div>

              {/* Totals per currency */}
              <table className="w-full text-sm border border-gray-200 rounded-xl overflow-hidden">
                <thead className="bg-[#2563eb] text-white">
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
                        {mode === "invoice_and_list"
                          ? `PR${String(year).padStart(2,"0")}-${String(prSeq + i).padStart(4,"0")}`
                          : "–"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Mode choice */}
              <div className="border border-gray-200 rounded-xl p-4 space-y-3">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Was soll erstellt werden?</p>
                <label className="flex items-start gap-3 cursor-pointer group">
                  <input
                    type="radio"
                    checked={mode === "invoice_and_list"}
                    onChange={() => setMode("invoice_and_list")}
                    className="mt-0.5 accent-[#2563eb]"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-800">Rechnung + Aufstellung</p>
                    <p className="text-xs text-gray-500">Erstellt PR-Rechnung (wird gespeichert) und lädt Aufstellungs-PDF herunter</p>
                  </div>
                </label>
                <label className="flex items-start gap-3 cursor-pointer group">
                  <input
                    type="radio"
                    checked={mode === "list_only"}
                    onChange={() => setMode("list_only")}
                    className="mt-0.5 accent-[#2563eb]"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-800">Nur Liste ausdrucken</p>
                    <p className="text-xs text-gray-500">Lädt nur die Aufstellung herunter – keine Rechnung wird erstellt</p>
                  </div>
                </label>
              </div>

              {/* Date + PR number — only relevant when creating invoice */}
              {mode === "invoice_and_list" && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Rechnungsdatum</label>
                    <input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">PR-Nummer ab</label>
                    <input type="number" value={prSeq} onChange={(e) => setPrSeq(parseInt(e.target.value) || 0)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
                  </div>
                </div>
              )}

              {/* Output choice */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-500 shrink-0">Aufstellung:</span>
                <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
                  <button
                    onClick={() => setOutput("screen")}
                    className={`px-3 py-1.5 font-medium transition-colors ${output === "screen" ? "bg-[#2563eb] text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                  >
                    Am Bildschirm
                  </button>
                  <button
                    onClick={() => setOutput("download")}
                    className={`px-3 py-1.5 font-medium border-l border-gray-200 transition-colors ${output === "download" ? "bg-[#2563eb] text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                  >
                    PDF herunterladen
                  </button>
                </div>
              </div>

              {/* Single action button */}
              <div className="pt-2 border-t border-gray-100">
                <button onClick={handleAction} disabled={busy}
                  className="w-full py-2.5 rounded-lg text-sm font-medium bg-[#2563eb] text-white hover:bg-[#2563eb]/80 disabled:opacity-50">
                  {busy
                    ? "Generiere…"
                    : mode === "invoice_and_list"
                      ? "📄 Rechnung + Aufstellung erstellen"
                      : output === "screen"
                        ? "🖥 Aufstellung am Bildschirm anzeigen"
                        : "📋 Aufstellung herunterladen"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
