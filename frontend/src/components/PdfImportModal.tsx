import { useRef, useState } from "react";
import { api, type PdfEntry, type Transaction } from "../api";
import { formatDate } from "../utils/format";

interface Props {
  supplierCode: string;
  onClose: () => void;
  onImported: (transactions: Transaction[]) => void;
}

export default function PdfImportModal({ supplierCode, onClose, onImported }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [entries, setEntries] = useState<PdfEntry[] | null>(null);
  const [customerMap, setCustomerMap] = useState<Record<number, number | null>>({});
  const [parsing, setParsing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>("");

  async function handleFile(file: File) {
    setFileName(file.name);
    setParsing(true);
    setError(null);
    setEntries(null);
    try {
      const result = await api.transactions.parseCsv(supplierCode, file);
      setEntries(result);
      const map: Record<number, number | null> = {};
      result.forEach((e, i) => {
        map[i] = e.customer_suggestions[0]?.id ?? null;
      });
      setCustomerMap(map);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler beim Lesen");
    } finally {
      setParsing(false);
    }
  }

  async function handleImport() {
    if (!entries) return;
    setImporting(true);
    setError(null);
    const created: Transaction[] = [];
    try {
      for (let i = 0; i < entries.length; i++) {
        const e = entries[i];
        const tx = await api.transactions.create(supplierCode, {
          customer_id: customerMap[i] ?? undefined,
          invoice_number: e.invoice_number,
          invoice_date: e.invoice_date,
          art_nr: e.art_nr,
          total_amount: String(e.total_amount),
          provision_rate: e.provision_rate != null ? String(e.provision_rate) : undefined,
          currency: e.currency,
        });
        created.push(tx);
      }
      onImported(created);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler beim Importieren");
      setImporting(false);
    }
  }

  const unmapped  = entries ? entries.filter((_, i) => customerMap[i] == null).length : 0;
  const notFound  = entries ? entries.filter((e) => e.customer_suggestions.length === 0).length : 0;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-2 sm:p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[95vh] flex flex-col">

        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">Provisionsabrechnung importieren</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl px-2">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">

          {!entries && (
            <div
              className="border-2 border-dashed border-gray-300 rounded-xl p-10 text-center cursor-pointer hover:border-[#2563eb] transition-colors"
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
            >
              <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
              <div className="text-4xl mb-3">📊</div>
              <p className="text-gray-600 font-medium">CSV oder Excel Datei hier ablegen oder klicken</p>
              <p className="text-xs text-gray-400 mt-1">
                Spalten: Währung · Kunde · Datum · Rechnungsnummer · Provisionsbasis · Provision % · Provision
              </p>
              {parsing && <p className="text-[#2563eb] mt-3 font-medium">Lese Datei…</p>}
            </div>
          )}

          {entries && (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">
                  <span className="font-semibold">{entries.length}</span> Positionen erkannt
                  {fileName && <span className="ml-2 text-gray-400">· {fileName}</span>}
                  {notFound > 0 && (
                    <span className="ml-2 text-amber-600">· {notFound} Adresse(n) nicht gefunden – bitte nacherfassen</span>
                  )}
                  {unmapped > notFound && (
                    <span className="ml-2 text-gray-400">· {unmapped - notFound} ohne Zuordnung</span>
                  )}
                </p>
                <button onClick={() => { setEntries(null); setCustomerMap({}); setFileName(""); }}
                  className="text-xs text-gray-500 hover:text-gray-700 underline">
                  Andere Datei laden
                </button>
              </div>

              <div className="overflow-x-auto border border-gray-200 rounded-xl">
                <table className="w-full text-xs">
                  <thead className="bg-[#2563eb] text-white">
                    <tr>
                      {["Datum", "Re-Nr", "Provisionsbasis", "Währ.", "Prov. %", "Provision", "Kunde (Datei)", "Kundenzuordnung"].map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((e, i) => {
                      const noMatch = e.customer_suggestions.length === 0;
                      return (
                      <tr key={i} className={noMatch ? "bg-amber-50" : i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                        <td className="px-3 py-2 whitespace-nowrap">{formatDate(e.invoice_date)}</td>
                        <td className="px-3 py-2 font-mono">{e.invoice_number}</td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          {e.total_amount.toLocaleString("de-DE", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-3 py-2">{e.currency}</td>
                        <td className="px-3 py-2 text-right">{e.provision_rate}</td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          {(e.provision_amount ?? 0).toLocaleString("de-DE", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-3 py-2 text-gray-500 max-w-[180px] truncate" title={e.customer_name_raw}>
                          {e.customer_name_clean || "–"}
                        </td>
                        <td className="px-3 py-2 min-w-[200px]">
                          {!noMatch ? (
                            <select
                              value={customerMap[i] ?? ""}
                              onChange={(ev) => setCustomerMap((m) => ({
                                ...m, [i]: ev.target.value ? parseInt(ev.target.value) : null,
                              }))}
                              className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-[#2563eb]/40"
                            >
                              <option value="">– nicht zuordnen –</option>
                              {e.customer_suggestions.map((c) => (
                                <option key={c.id} value={c.id}>
                                  {c.name} {c.city ? `· ${c.city}` : ""}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span className="text-amber-700 font-medium" title="Adresse nicht gefunden – bitte nacherfassen">
                              {e.customer_name_clean} ⚠
                            </span>
                          )}
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {error && <p className="text-red-600 text-sm">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">
            Abbrechen
          </button>
          {entries && (
            <button onClick={handleImport} disabled={importing}
              className="px-5 py-2 rounded-lg text-sm font-medium bg-[#2563eb] text-white hover:bg-[#2563eb]/80 disabled:opacity-50">
              {importing ? "Importiere…" : `${entries.length} Positionen importieren`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
