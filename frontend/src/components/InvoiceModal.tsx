import { useEffect, useRef, useState } from "react";
import { api, type Customer, type Transaction, type TransactionUpdate } from "../api";
import type { Invoice } from "../pages/Transactions";

interface Props {
  invoice: Invoice | null;
  supplierCode: string;
  onClose: () => void;
  onSaved: (positions: Transaction[]) => void;
  onDeleted: (invoiceNumber: string) => void;
}

const emptyPosition = (): TransactionUpdate => ({
  art_nr: "", color: "", quantity: undefined, unit: "",
  discount: undefined, provision_rate: undefined, price: undefined,
  currency: "", total_amount: undefined, exchange_rate: undefined,
  customer_order_no: "", notes: "",
});

const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30";

function Field({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  );
}

export default function InvoiceModal({ invoice, supplierCode, onClose, onSaved, onDeleted }: Props) {
  const isNew = invoice === null;

  const [invoiceNumber, setInvoiceNumber] = useState(invoice?.invoice_number ?? "");
  const [invoiceDate, setInvoiceDate] = useState(invoice?.invoice_date ?? new Date().toISOString().slice(0, 10));

  // Kunde
  const [customerSearch, setCustomerSearch] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  // Positionen
  const [positions, setPositions] = useState<TransactionUpdate[]>(
    invoice ? invoice.positions.map((p) => ({ ...p })) : [emptyPosition()]
  );

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (invoice?.customer_id && invoice.customer_name) {
      setCustomerSearch(`${invoice.customer_ku_nr ?? invoice.customer_code ?? ""} – ${invoice.customer_name}`.replace(/^–\s*/, ""));
      setSelectedCustomer({
        id: invoice.customer_id,
        code: invoice.customer_code ?? "",
        ku_nr: invoice.customer_ku_nr,
        name: invoice.customer_name,
      });
    }
  }, []);

  useEffect(() => {
    if (!showDropdown) return;
    const t = setTimeout(() => {
      api.customers.list(customerSearch || undefined).then(setCustomers);
    }, 250);
    return () => clearTimeout(t);
  }, [customerSearch, showDropdown]);

  function selectCustomer(c: Customer) {
    setSelectedCustomer(c);
    setCustomerSearch(`${c.ku_nr ?? c.code} – ${c.name}`);
    setShowDropdown(false);
  }

  function setPos(idx: number, field: keyof TransactionUpdate, value: unknown) {
    setPositions((prev) => prev.map((p, i) => i === idx ? { ...p, [field]: value } : p));
  }

  function addPosition() {
    setPositions((prev) => [...prev, emptyPosition()]);
  }

  async function removePosition(idx: number) {
    const pos = positions[idx] as Transaction;
    if (pos.id) {
      try {
        await api.transactions.delete(pos.id);
      } catch {
        setError("Fehler beim Löschen der Position");
        return;
      }
    }
    setPositions((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!invoiceNumber.trim()) { setError("Rechnungs-Nr. ist erforderlich"); return; }
    if (positions.length === 0) { setError("Mindestens eine Position erforderlich"); return; }
    setSaving(true);
    setError(null);
    try {
      const results: Transaction[] = [];
      for (const pos of positions) {
        const payload: TransactionUpdate = {
          ...pos,
          invoice_number: invoiceNumber.trim(),
          invoice_date: invoiceDate,
          customer_id: selectedCustomer?.id,
        };
        const existing = pos as Transaction;
        if (existing.id) {
          const updated = await api.transactions.update(existing.id, payload);
          results.push(updated);
        } else {
          const created = await api.transactions.create(supplierCode, payload);
          results.push(created);
        }
      }
      onSaved(results);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteInvoice() {
    if (!invoice || !window.confirm(`Rechnung ${invoice.invoice_number} mit allen Positionen löschen?`)) return;
    setSaving(true);
    try {
      for (const pos of invoice.positions) {
        await api.transactions.delete(pos.id);
      }
      onDeleted(invoice.invoice_number);
    } catch {
      setError("Fehler beim Löschen");
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 sticky top-0 bg-white rounded-t-2xl">
          <h2 className="text-lg font-semibold text-gray-800">
            {isNew ? "Neue Rechnung" : `Rechnung ${invoice.invoice_number}`}
          </h2>
          <div className="flex items-center gap-2">
            {!isNew && (
              <button type="button" onClick={handleDeleteInvoice}
                className="text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100">
                Löschen
              </button>
            )}
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl px-2">✕</button>
          </div>
        </div>

        <form onSubmit={handleSave} className="px-6 py-5 space-y-5">

          {/* Rechnungskopf */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Rechnungs-Nr.*">
              <input type="text" value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)}
                className={inputCls} required />
            </Field>
            <Field label="Datum*">
              <input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)}
                className={inputCls} required />
            </Field>
          </div>

          {/* Kunde */}
          <Field label="Kunde">
            <div className="relative">
              <div className="flex gap-2">
                <input ref={searchRef} type="text" value={customerSearch}
                  placeholder="Name, Code oder Kd-Nr suchen…"
                  onChange={(e) => { setCustomerSearch(e.target.value); setShowDropdown(true); }}
                  onFocus={() => setShowDropdown(true)}
                  className={inputCls} />
                {selectedCustomer && (
                  <button type="button" onClick={() => { setSelectedCustomer(null); setCustomerSearch(""); }}
                    className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-500 hover:bg-gray-200">
                    Löschen
                  </button>
                )}
              </div>
              {showDropdown && customers.length > 0 && (
                <div className="absolute z-10 top-full mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                  {customers.map((c) => (
                    <button key={c.id} type="button" onClick={() => selectCustomer(c)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-[#dce8f5] flex justify-between items-center">
                      <span className="font-medium">{c.name}</span>
                      <span className="text-xs text-gray-400 ml-2">{c.ku_nr ?? c.code}{c.city ? ` · ${c.city}` : ""}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </Field>

          {/* Positionen */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Positionen</span>
              <button type="button" onClick={addPosition}
                className="text-xs px-3 py-1 rounded-lg bg-[#1a3a5c]/10 text-[#1a3a5c] hover:bg-[#1a3a5c]/20 font-medium">
                + Position hinzufügen
              </button>
            </div>

            <div className="space-y-3">
              {positions.map((pos, idx) => (
                <div key={idx} className="border border-gray-200 rounded-xl p-4 bg-gray-50 relative">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-gray-500">Position {idx + 1}</span>
                    {positions.length > 1 && (
                      <button type="button" onClick={() => removePosition(idx)}
                        className="text-xs text-red-500 hover:text-red-700">
                        Entfernen
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <Field label="Artikel-Nr.">
                      <input type="text" value={pos.art_nr ?? ""} onChange={(e) => setPos(idx, "art_nr", e.target.value)} className={inputCls} />
                    </Field>
                    <Field label="Farbe">
                      <input type="text" value={pos.color ?? ""} onChange={(e) => setPos(idx, "color", e.target.value)} className={inputCls} />
                    </Field>
                    <Field label="Einheit">
                      <input type="text" maxLength={2} value={pos.unit ?? ""} onChange={(e) => setPos(idx, "unit", e.target.value)} className={inputCls} />
                    </Field>
                    <Field label="Menge">
                      <input type="number" step="0.01" value={pos.quantity ?? ""} onChange={(e) => setPos(idx, "quantity", e.target.value || undefined)} className={inputCls} />
                    </Field>
                    <Field label="Preis">
                      <input type="number" step="0.001" value={pos.price ?? ""} onChange={(e) => setPos(idx, "price", e.target.value || undefined)} className={inputCls} />
                    </Field>
                    <Field label="Betrag*">
                      <input type="number" step="0.01" required value={pos.total_amount ?? ""} onChange={(e) => setPos(idx, "total_amount", e.target.value || undefined)} className={inputCls} />
                    </Field>
                    <Field label="Währung">
                      <input type="text" maxLength={3} value={pos.currency ?? ""} onChange={(e) => setPos(idx, "currency", e.target.value)} className={inputCls} />
                    </Field>
                    <Field label="Provisions-Satz %">
                      <input type="number" step="0.01" value={pos.provision_rate ?? ""} onChange={(e) => setPos(idx, "provision_rate", e.target.value || undefined)} className={inputCls} />
                    </Field>
                    <Field label="Rabatt">
                      <input type="number" step="0.01" value={pos.discount ?? ""} onChange={(e) => setPos(idx, "discount", e.target.value || undefined)} className={inputCls} />
                    </Field>
                    <Field label="Kurs">
                      <input type="number" step="0.00001" value={pos.exchange_rate ?? ""} onChange={(e) => setPos(idx, "exchange_rate", e.target.value || undefined)} className={inputCls} />
                    </Field>
                    <Field label="Kundenbestellnr." className="col-span-2">
                      <input type="text" value={pos.customer_order_no ?? ""} onChange={(e) => setPos(idx, "customer_order_no", e.target.value)} className={inputCls} />
                    </Field>
                    <Field label="Notizen" className="col-span-3">
                      <input type="text" value={pos.notes ?? ""} onChange={(e) => setPos(idx, "notes", e.target.value)} className={inputCls} />
                    </Field>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">
              Abbrechen
            </button>
            <button type="submit" disabled={saving}
              className="px-5 py-2 rounded-lg text-sm font-medium bg-[#1a3a5c] text-white hover:bg-[#1a3a5c]/80 disabled:opacity-50">
              {saving ? "Speichert…" : "Speichern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
