import { useEffect, useRef, useState } from "react";
import { api, type Customer, type Transaction, type TransactionUpdate } from "../api";

interface Props {
  transaction: Transaction;
  onClose: () => void;
  onSaved: (updated: Transaction) => void;
}

export default function TransactionEditModal({ transaction: tx, onClose, onSaved }: Props) {
  const [form, setForm] = useState<TransactionUpdate>({
    customer_id:      tx.customer_id,
    invoice_number:   tx.invoice_number,
    invoice_date:     tx.invoice_date,
    art_nr:           tx.art_nr ?? "",
    color:            tx.color ?? "",
    quantity:         tx.quantity ?? "",
    unit:             tx.unit ?? "",
    discount:         tx.discount ?? "",
    provision_rate:   tx.provision_rate ?? "",
    price:            tx.price ?? "",
    currency:         tx.currency ?? "",
    total_amount:     tx.total_amount,
    exchange_rate:    tx.exchange_rate ?? "",
    customer_order_no: tx.customer_order_no ?? "",
    notes:            tx.notes ?? "",
  });

  // Kunden-Suche
  const [customerSearch, setCustomerSearch] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Kunden direkt aus den mitgelieferten Feldern vorladen
  useEffect(() => {
    if (tx.customer_id && tx.customer_name) {
      const label = `${tx.customer_ku_nr ?? tx.customer_code ?? ""} – ${tx.customer_name}`.replace(/^–\s*/, "");
      setCustomerSearch(label);
      setSelectedCustomer({
        id: tx.customer_id,
        code: tx.customer_code ?? "",
        ku_nr: tx.customer_ku_nr,
        name: tx.customer_name,
      });
    }
  }, [tx.customer_id, tx.customer_name, tx.customer_code, tx.customer_ku_nr]);

  // Debounce-Suche
  useEffect(() => {
    if (!showDropdown) return;
    const t = setTimeout(() => {
      api.customers.list(customerSearch || undefined).then(setCustomers);
    }, 250);
    return () => clearTimeout(t);
  }, [customerSearch, showDropdown]);

  function set(field: keyof TransactionUpdate, value: unknown) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function selectCustomer(c: Customer) {
    setSelectedCustomer(c);
    setForm((f) => ({ ...f, customer_id: c.id }));
    setCustomerSearch(`${c.ku_nr ?? c.code} – ${c.name}`);
    setShowDropdown(false);
  }

  function clearCustomer() {
    setSelectedCustomer(null);
    setForm((f) => ({ ...f, customer_id: undefined }));
    setCustomerSearch("");
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.transactions.update(tx.id, form);
      onSaved(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setSaving(false);
    }
  }

  // Backdrop-Klick schließt Modal
  function handleBackdrop(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={handleBackdrop}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 sticky top-0 bg-white rounded-t-2xl">
          <h2 className="text-lg font-semibold text-gray-800">
            Rechnung bearbeiten
            <span className="ml-2 font-mono text-sm text-[#2563eb] font-normal">
              {tx.invoice_number}
            </span>
          </h2>
          <button onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none px-2">✕</button>
        </div>

        <form onSubmit={handleSave} className="px-6 py-5 space-y-5">
          {/* Kunde */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Kunde</label>
            <div className="relative">
              <div className="flex gap-2">
                <input
                  ref={searchRef}
                  type="text"
                  value={customerSearch}
                  placeholder="Name, Code oder Kd-Nr suchen…"
                  onChange={(e) => { setCustomerSearch(e.target.value); setShowDropdown(true); }}
                  onFocus={() => setShowDropdown(true)}
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
                />
                {selectedCustomer && (
                  <button type="button" onClick={clearCustomer}
                    className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-500 hover:bg-gray-200">
                    Löschen
                  </button>
                )}
              </div>
              {showDropdown && customers.length > 0 && (
                <div className="absolute z-10 top-full mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                  {customers.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => selectCustomer(c)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-[#dce8f5] flex justify-between items-center"
                    >
                      <span className="font-medium">{c.name}</span>
                      <span className="text-xs text-gray-400 ml-2">
                        {c.ku_nr ?? c.code} {c.city ? `· ${c.city}` : ""}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Rechnungsdaten */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Rechnungs-Nr." required>
              <input type="text" required value={form.invoice_number ?? ""}
                onChange={(e) => set("invoice_number", e.target.value)}
                className={inputCls} />
            </Field>
            <Field label="Datum" required>
              <input type="date" required value={form.invoice_date ?? ""}
                onChange={(e) => set("invoice_date", e.target.value)}
                className={inputCls} />
            </Field>
            <Field label="Artikel-Nr.">
              <input type="text" value={form.art_nr ?? ""}
                onChange={(e) => set("art_nr", e.target.value)}
                className={inputCls} />
            </Field>
            <Field label="Farbe">
              <input type="text" value={form.color ?? ""}
                onChange={(e) => set("color", e.target.value)}
                className={inputCls} />
            </Field>
            <Field label="Menge">
              <input type="number" step="0.01" value={form.quantity ?? ""}
                onChange={(e) => set("quantity", e.target.value || undefined)}
                className={inputCls} />
            </Field>
            <Field label="Einheit">
              <input type="text" maxLength={2} value={form.unit ?? ""}
                onChange={(e) => set("unit", e.target.value)}
                className={inputCls} />
            </Field>
            <Field label="Preis">
              <input type="number" step="0.001" value={form.price ?? ""}
                onChange={(e) => set("price", e.target.value || undefined)}
                className={inputCls} />
            </Field>
            <Field label="Währung">
              <input type="text" maxLength={3} value={form.currency ?? ""}
                onChange={(e) => set("currency", e.target.value)}
                className={inputCls} />
            </Field>
            <Field label="Betrag (Gesamt)" required>
              <input type="number" step="0.01" required value={form.total_amount ?? ""}
                onChange={(e) => set("total_amount", e.target.value)}
                className={inputCls} />
            </Field>
            <Field label="Provisions-Satz %">
              <input type="number" step="0.01" value={form.provision_rate ?? ""}
                onChange={(e) => set("provision_rate", e.target.value || undefined)}
                className={inputCls} />
            </Field>
            <Field label="Rabatt">
              <input type="number" step="0.01" value={form.discount ?? ""}
                onChange={(e) => set("discount", e.target.value || undefined)}
                className={inputCls} />
            </Field>
            <Field label="Kurs">
              <input type="number" step="0.00001" value={form.exchange_rate ?? ""}
                onChange={(e) => set("exchange_rate", e.target.value || undefined)}
                className={inputCls} />
            </Field>
            <Field label="Kundenbestellnr." className="col-span-2">
              <input type="text" value={form.customer_order_no ?? ""}
                onChange={(e) => set("customer_order_no", e.target.value)}
                className={inputCls} />
            </Field>
          </div>

          <Field label="Notizen">
            <textarea rows={2} value={form.notes ?? ""}
              onChange={(e) => set("notes", e.target.value)}
              className={inputCls + " resize-none"} />
          </Field>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          {/* Footer */}
          <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">
              Abbrechen
            </button>
            <button type="submit" disabled={saving}
              className="px-5 py-2 rounded-lg text-sm font-medium bg-[#2563eb] text-white hover:bg-[#2563eb]/80 disabled:opacity-50">
              {saving ? "Speichert…" : "Speichern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30";

function Field({ label, children, required, className }: {
  label: string; children: React.ReactNode; required?: boolean; className?: string;
}) {
  return (
    <div className={className}>
      <label className="block text-xs font-medium text-gray-500 mb-1">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}
