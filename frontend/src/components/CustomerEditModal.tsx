import { useState } from "react";
import { api, type Customer } from "../api";

interface Props {
  customer: Customer | null;  // null = Neuanlage
  onClose: () => void;
  onSaved: (c: Customer) => void;
}

type Form = Omit<Customer, "id" | "ku_nr">;

function toForm(c: Customer | null): Form {
  return {
    code:             c?.code ?? "",
    name:             c?.name ?? "",
    country_code:     c?.country_code ?? "",
    zip:              c?.zip ?? "",
    city:             c?.city ?? "",
    phone:            c?.phone ?? "",
    fax:              c?.fax ?? "",
    email:            c?.email ?? "",
    url:              c?.url ?? "",
    language:         c?.language ?? "",
    contact_name:     c?.contact_name ?? "",
    contact_title:    c?.contact_title ?? "",
    contact_position: c?.contact_position ?? "",
    notes:            c?.notes ?? "",
  };
}

export default function CustomerEditModal({ customer, onClose, onSaved }: Props) {
  const isNew = customer === null;
  const [form, setForm] = useState<Form>(toForm(customer));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set(field: keyof Form, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const code = form.code.trim().toUpperCase();
    if (isNew && code.length < 4) { setError("Code muss mindestens 4 Zeichen haben"); return; }
    if (!form.name.trim()) { setError("Name ist Pflichtfeld"); return; }

    setSaving(true);
    try {
      const payload = {
        ...form,
        code,
        name: form.name.trim(),
        country_code:     form.country_code?.toUpperCase() || undefined,
        zip:              form.zip || undefined,
        city:             form.city || undefined,
        phone:            form.phone || undefined,
        fax:              form.fax || undefined,
        email:            form.email || undefined,
        url:              form.url || undefined,
        language:         form.language || undefined,
        contact_name:     form.contact_name || undefined,
        contact_title:    form.contact_title || undefined,
        contact_position: form.contact_position || undefined,
        notes:            form.notes || undefined,
      };
      const saved = isNew
        ? await api.customers.create(payload)
        : await api.customers.update(customer!.code, payload);
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
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[95vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 sticky top-0 bg-white rounded-t-2xl">
          <h2 className="text-lg font-semibold text-gray-800">
            {isNew
              ? "Neuer Kunde"
              : <span>Kunde bearbeiten – <span className="font-mono text-[#2563eb]">{customer!.code}</span>
                  {customer!.ku_nr && <span className="ml-2 text-sm text-gray-400 font-normal">Kd-Nr {customer!.ku_nr}</span>}
                </span>
            }
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl px-2">✕</button>
        </div>

        <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
          {/* Code + Name */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Code <span className="text-red-400">*</span>
                {isNew && <span className="ml-1 text-gray-400 font-normal">(min. 4 Zeichen)</span>}
              </label>
              {isNew ? (
                <input type="text" maxLength={6} required
                  value={form.code}
                  onChange={(e) => set("code", e.target.value.toUpperCase())}
                  className={inp + " uppercase font-mono"} placeholder="z.B. MUSTE" />
              ) : (
                <div className="px-3 py-2 bg-gray-100 rounded-lg text-sm font-mono font-semibold text-[#2563eb]">
                  {customer!.code}
                  <span className="ml-1 text-xs text-gray-400 font-normal font-sans">(nicht änderbar)</span>
                </div>
              )}
            </div>
            {isNew && (
              <div className="col-span-1 flex items-end">
                <p className="text-xs text-gray-400 pb-2">
                  Kunden-Nr. wird automatisch vergeben
                </p>
              </div>
            )}
            <div className={isNew ? "" : "col-span-2"}>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Name <span className="text-red-400">*</span>
              </label>
              <input type="text" required value={form.name}
                onChange={(e) => set("name", e.target.value)}
                className={inp} />
            </div>
          </div>

          {/* Adresse */}
          <fieldset className="border border-gray-200 rounded-xl p-4 space-y-3">
            <legend className="text-xs font-semibold text-gray-500 px-1">Adresse</legend>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Land (Code)</label>
                <input type="text" maxLength={3} value={form.country_code}
                  onChange={(e) => set("country_code", e.target.value.toUpperCase())}
                  className={inp + " uppercase"} placeholder="AT" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">PLZ</label>
                <input type="text" maxLength={8} value={form.zip}
                  onChange={(e) => set("zip", e.target.value)}
                  className={inp} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Ort</label>
                <input type="text" maxLength={50} value={form.city}
                  onChange={(e) => set("city", e.target.value)}
                  className={inp} />
              </div>
            </div>
          </fieldset>

          {/* Kontakt */}
          <fieldset className="border border-gray-200 rounded-xl p-4 space-y-3">
            <legend className="text-xs font-semibold text-gray-500 px-1">Kontakt</legend>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Telefon</label>
                <input type="text" maxLength={20} value={form.phone}
                  onChange={(e) => set("phone", e.target.value)} className={inp} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Fax</label>
                <input type="text" maxLength={20} value={form.fax}
                  onChange={(e) => set("fax", e.target.value)} className={inp} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">E-Mail</label>
                <input type="email" maxLength={40} value={form.email}
                  onChange={(e) => set("email", e.target.value)} className={inp} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Website</label>
                <input type="text" maxLength={40} value={form.url}
                  onChange={(e) => set("url", e.target.value)} className={inp} />
              </div>
            </div>
          </fieldset>

          {/* Ansprechpartner */}
          <fieldset className="border border-gray-200 rounded-xl p-4 space-y-3">
            <legend className="text-xs font-semibold text-gray-500 px-1">Ansprechpartner</legend>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Titel</label>
                <input type="text" maxLength={3} value={form.contact_title}
                  onChange={(e) => set("contact_title", e.target.value)} className={inp} />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Name</label>
                <input type="text" maxLength={24} value={form.contact_name}
                  onChange={(e) => set("contact_name", e.target.value)} className={inp} />
              </div>
              <div className="col-span-3">
                <label className="block text-xs text-gray-500 mb-1">Position</label>
                <input type="text" maxLength={15} value={form.contact_position}
                  onChange={(e) => set("contact_position", e.target.value)} className={inp} />
              </div>
            </div>
          </fieldset>

          {/* Notizen */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Notizen</label>
            <textarea rows={2} value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
              className={inp + " resize-none"} />
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

const inp = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30";
