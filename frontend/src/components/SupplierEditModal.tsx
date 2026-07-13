import { useState } from "react";
import { api, type Supplier } from "../api";

interface Props {
  supplier: Supplier | null;  // null = Neuanlage
  onClose: () => void;
  onSaved: (s: Supplier) => void;
}

type Split = { rate: number; rep_code: string };

type Form = {
  code: string;
  name: string;
  address: string;
  default_currency: string;
  representative_code: string;
  contact_person: string;
  is_active: boolean;
  notes: string;
  splits: Split[];
  invoice_language: string;
};

function toForm(s: Supplier | null): Form {
  return {
    code:                s?.code ?? "",
    name:                s?.name ?? "",
    address:             s?.address ?? "",
    default_currency:    s?.default_currency ?? "",
    representative_code: s?.representative_code ?? "",
    contact_person:      s?.contact_person ?? "",
    is_active:           s?.is_active ?? true,
    notes:               "",
    splits:              s?.provision_splits ? [...s.provision_splits] : [],
    invoice_language:    s?.invoice_language ?? "de+en",
  };
}

export default function SupplierEditModal({ supplier, onClose, onSaved }: Props) {
  const isNew = supplier === null;
  const [form, setForm] = useState<Form>(toForm(supplier));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set(field: keyof Form, value: string | boolean) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const code = form.code.trim().toUpperCase();
    if (!code) { setError("Code ist Pflichtfeld"); return; }
    if (code.length > 2) { setError("Code darf maximal 2 Zeichen haben"); return; }
    if (!form.name.trim()) { setError("Name ist Pflichtfeld"); return; }

    setSaving(true);
    try {
      let saved: Supplier;
      const payload = {
        code,
        name: form.name.trim(),
        address: form.address || undefined,
        default_currency: form.default_currency.toUpperCase() || undefined,
        representative_code: form.representative_code.toUpperCase() || undefined,
        contact_person: form.contact_person || undefined,
        is_active: form.is_active,
        provision_splits: form.splits.length > 0 ? form.splits : undefined,
        invoice_language: form.invoice_language || "de+en",
      };
      if (isNew) {
        saved = await api.suppliers.create(payload);
      } else {
        const { code: _code, ...updatePayload } = payload;
        saved = await api.suppliers.update(supplier!.code, updatePayload);
      }
      onSaved(saved);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setSaving(false);
    }
  }

  function handleBackdrop(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-2 sm:p-4"
      onClick={handleBackdrop}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[95vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">
            {isNew ? "Neuer Lieferant" : `Lieferant bearbeiten – ${supplier!.code}`}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl px-2">✕</button>
        </div>

        <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Code — nur bei Neuanlage editierbar */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Code <span className="text-red-400">*</span>
                <span className="ml-1 text-gray-400 font-normal">(max. 2 Zeichen)</span>
              </label>
              {isNew ? (
                <input
                  type="text"
                  maxLength={2}
                  required
                  value={form.code}
                  onChange={(e) => set("code", e.target.value.toUpperCase())}
                  className={inputCls + " uppercase font-mono"}
                  placeholder="z.B. AM"
                />
              ) : (
                <div className="px-3 py-2 bg-gray-100 rounded-lg text-sm font-mono font-semibold text-[#2563eb]">
                  {supplier!.code}
                  <span className="ml-2 text-xs text-gray-400 font-normal font-sans">(nicht änderbar)</span>
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Währung <span className="text-gray-400 font-normal">(3 Zeichen)</span>
              </label>
              <input type="text" maxLength={3} value={form.default_currency}
                onChange={(e) => set("default_currency", e.target.value.toUpperCase())}
                className={inputCls + " uppercase"} placeholder="EUR" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Name <span className="text-red-400">*</span>
            </label>
            <input type="text" required value={form.name}
              onChange={(e) => set("name", e.target.value)}
              className={inputCls} placeholder="Firmenname" />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Adresse</label>
            <input type="text" value={form.address}
              onChange={(e) => set("address", e.target.value)}
              className={inputCls} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Vertreter-Code</label>
              <input type="text" maxLength={2} value={form.representative_code}
                onChange={(e) => set("representative_code", e.target.value.toUpperCase())}
                className={inputCls + " uppercase"} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Kontaktperson</label>
              <input type="text" value={form.contact_person}
                onChange={(e) => set("contact_person", e.target.value)}
                className={inputCls} />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Rechnungssprache</label>
            <select value={form.invoice_language}
              onChange={(e) => set("invoice_language", e.target.value)}
              className={inputCls}>
              <option value="de+en">Deutsch / English (zweisprachig)</option>
              <option value="de">Deutsch</option>
              <option value="en">English</option>
            </select>
          </div>

          {/* Provisions-Splits */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-gray-500">
                Provisions-Splits
                {form.splits.length > 0 && (
                  <span className={`ml-2 font-normal ${
                    form.splits.reduce((s, p) => s + p.rate, 0) === 100
                      ? "text-green-600" : "text-amber-500"
                  }`}>
                    ({form.splits.reduce((s, p) => s + p.rate, 0)}% gesamt)
                  </span>
                )}
              </label>
              <button
                type="button"
                onClick={() => setForm(f => ({ ...f, splits: [...f.splits, { rate: 0, rep_code: "" }] }))}
                className="text-xs text-[#2563eb] hover:underline"
              >
                + Split hinzufügen
              </button>
            </div>
            {form.splits.length === 0 ? (
              <p className="text-xs text-gray-400 italic">Kein Split konfiguriert</p>
            ) : (
              <div className="space-y-2">
                {form.splits.map((sp, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={sp.rate}
                      onChange={(e) => {
                        const next = [...form.splits];
                        next[i] = { ...next[i], rate: Number(e.target.value) };
                        setForm(f => ({ ...f, splits: next }));
                      }}
                      className={inputCls + " w-24 text-right"}
                      placeholder="Rate %"
                    />
                    <span className="text-gray-400 text-sm">%</span>
                    <input
                      type="text"
                      maxLength={4}
                      value={sp.rep_code}
                      onChange={(e) => {
                        const next = [...form.splits];
                        next[i] = { ...next[i], rep_code: e.target.value.toUpperCase() };
                        setForm(f => ({ ...f, splits: next }));
                      }}
                      className={inputCls + " uppercase font-mono"}
                      placeholder="Kürzel"
                    />
                    <button
                      type="button"
                      onClick={() => setForm(f => ({ ...f, splits: f.splits.filter((_, j) => j !== i) }))}
                      className="text-gray-400 hover:text-red-500 px-1 text-lg leading-none"
                      title="Entfernen"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <input type="checkbox" id="is_active" checked={form.is_active}
              onChange={(e) => set("is_active", e.target.checked)}
              className="w-4 h-4 accent-[#2563eb]" />
            <label htmlFor="is_active" className="text-sm text-gray-700">Aktiv</label>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">
              Abbrechen
            </button>
            <button type="submit" disabled={saving}
              className="px-5 py-2 rounded-lg text-sm font-medium bg-[#2563eb] text-white hover:bg-[#2563eb]/80 disabled:opacity-50">
              {saving ? "Speichert…" : isNew ? "Anlegen" : "Speichern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30";
