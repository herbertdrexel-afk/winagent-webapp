import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Check, X } from "lucide-react";
import { api } from "../api";

interface SupplierShort { id: number; code: string; name: string; }
interface Mandant {
  id: number;
  name: string;
  mandant_id: string | null;
  is_active: boolean;
  notes: string | null;
  suppliers: SupplierShort[];
}

const EMPTY: Omit<Mandant, "id"> = { name: "", mandant_id: "", is_active: true, notes: "", suppliers: [] };

export default function ReybexMandants() {
  const [mandants, setMandants] = useState<Mandant[]>([]);
  const [suppliers, setSuppliers] = useState<SupplierShort[]>([]);
  const [editing, setEditing] = useState<Mandant | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { load(); }, []);

  async function load() {
    const [ms, ss] = await Promise.all([
      api.mandants.list(),
      api.suppliers.list(),
    ]);
    setMandants(ms);
    setSuppliers(ss);
  }

  function openNew() {
    setForm({ ...EMPTY });
    setEditing(null);
    setIsNew(true);
    setError(null);
  }

  function openEdit(m: Mandant) {
    setForm({ name: m.name, mandant_id: m.mandant_id ?? "", is_active: m.is_active, notes: m.notes ?? "", suppliers: m.suppliers });
    setEditing(m);
    setIsNew(false);
    setError(null);
  }

  function cancel() { setEditing(null); setIsNew(false); }

  function toggleSupplier(s: SupplierShort) {
    const exists = form.suppliers.some((x) => x.id === s.id);
    setForm((f) => ({
      ...f,
      suppliers: exists ? f.suppliers.filter((x) => x.id !== s.id) : [...f.suppliers, s],
    }));
  }

  async function save() {
    if (!form.name.trim()) { setError("Name ist erforderlich"); return; }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        mandant_id: form.mandant_id?.trim() || null,
        is_active: form.is_active,
        notes: form.notes?.trim() || null,
        supplier_ids: form.suppliers.map((s) => s.id),
      };
      if (isNew) {
        await api.mandants.create(payload);
      } else if (editing) {
        await api.mandants.update(editing.id, payload);
      }
      await load();
      cancel();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally { setSaving(false); }
  }

  async function deleteMandant(m: Mandant) {
    if (!confirm(`Mandant "${m.name}" wirklich löschen?`)) return;
    await api.mandants.delete(m.id);
    await load();
  }

  const showForm = isNew || editing !== null;

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Reybex Mandanten</h1>
          <p className="text-sm text-gray-500 mt-0.5">Mandanten konfigurieren und Lieferanten zuordnen</p>
        </div>
        {!showForm && (
          <button onClick={openNew}
            className="flex items-center gap-1.5 bg-[#1a3a5c] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#1a3a5c]/80 transition-colors">
            <Plus size={16} /> Mandant hinzufügen
          </button>
        )}
      </div>

      {/* Form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <h2 className="font-semibold text-gray-800">{isNew ? "Neuer Mandant" : `Bearbeiten: ${editing?.name}`}</h2>
          {error && <div className="text-red-600 text-sm">{error}</div>}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Name *</label>
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="z.B. Gewohnheit GmbH"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Reybex mandantId</label>
              <input value={form.mandant_id ?? ""} onChange={(e) => setForm((f) => ({ ...f, mandant_id: e.target.value }))}
                placeholder="z.B. 1670968868187006 (später eintragen)"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-2 block">Zugeordnete Lieferanten</label>
            <div className="flex flex-wrap gap-2">
              {suppliers.map((s) => {
                const selected = form.suppliers.some((x) => x.id === s.id);
                return (
                  <button key={s.id} onClick={() => toggleSupplier(s)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                      selected
                        ? "bg-[#1a3a5c] text-white border-[#1a3a5c]"
                        : "bg-white text-gray-600 border-gray-300 hover:border-[#1a3a5c]"
                    }`}>
                    {s.code} – {s.name}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Notizen</label>
              <input value={form.notes ?? ""} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                  className="w-4 h-4 rounded" />
                <span className="text-sm text-gray-700">Aktiv</span>
              </label>
            </div>
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={save} disabled={saving}
              className="flex items-center gap-1.5 bg-[#1a3a5c] text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-[#1a3a5c]/80 disabled:opacity-50 transition-colors">
              <Check size={14} /> {saving ? "Speichere…" : "Speichern"}
            </button>
            <button onClick={cancel}
              className="flex items-center gap-1.5 border border-gray-300 text-gray-600 px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors">
              <X size={14} /> Abbrechen
            </button>
          </div>
        </div>
      )}

      {/* List */}
      <div className="space-y-3">
        {mandants.length === 0 && !showForm && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 text-sm">
            Noch keine Mandanten angelegt. Klicke auf „Mandant hinzufügen".
          </div>
        )}
        {mandants.map((m) => (
          <div key={m.id} className={`bg-white rounded-xl border px-5 py-4 flex items-start gap-4 ${m.is_active ? "border-gray-200" : "border-gray-100 opacity-60"}`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-gray-800">{m.name}</span>
                {!m.is_active && <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">Inaktiv</span>}
              </div>
              <div className="mt-1 text-xs text-gray-500 space-y-0.5">
                <div>
                  <span className="font-medium">mandantId: </span>
                  {m.mandant_id
                    ? <span className="font-mono text-[#1a3a5c]">{m.mandant_id}</span>
                    : <span className="text-amber-600 italic">noch nicht eingetragen</span>}
                </div>
                {m.suppliers.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {m.suppliers.map((s) => (
                      <span key={s.id} className="bg-[#1a3a5c]/10 text-[#1a3a5c] px-2 py-0.5 rounded-full text-xs">{s.code} – {s.name}</span>
                    ))}
                  </div>
                )}
                {m.notes && <div className="text-gray-400 mt-0.5">{m.notes}</div>}
              </div>
            </div>
            <div className="flex gap-1 shrink-0">
              <button onClick={() => openEdit(m)}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-[#1a3a5c] transition-colors">
                <Pencil size={15} />
              </button>
              <button onClick={() => deleteMandant(m)}
                className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors">
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
