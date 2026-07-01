import { useEffect, useState } from "react";
import { api, type ReportSchedule, type ReportScheduleCreate, type AuthUser, type Supplier } from "../api";
import { Plus, Send, Pencil, Trash2, CheckCircle2, XCircle } from "lucide-react";

const DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];

const PERIODS: { value: string; label: string }[] = [
  { value: "last_week",     label: "Letzte Woche (Mo–So)" },
  { value: "last_month",    label: "Letzter Monat" },
  { value: "current_month", label: "Aktueller Monat" },
  { value: "last_30_days",  label: "Letzte 30 Tage" },
  { value: "last_90_days",  label: "Letzte 90 Tage" },
  { value: "last_quarter",  label: "Letztes Quartal" },
  { value: "current_year",  label: "Aktuelles Jahr" },
  { value: "last_year",     label: "Letztes Jahr" },
];

const REPORT_TYPES: { value: string; label: string }[] = [
  { value: "supplier_summary",   label: "Lieferant Statistik" },
  { value: "customer_provision", label: "AdrUms nach Provision" },
  { value: "customer_turnover",  label: "AdrUms nach Umsatz" },
  { value: "supplier_detail",    label: "Lieferant Detail (Quartale)" },
  { value: "transactions",       label: "Rechnungsübersicht" },
];

const EMPTY_FORM: ReportScheduleCreate = {
  name: "",
  enabled: true,
  day_of_week: 0,
  send_hour: 7,
  report_period: "last_week",
  supplier_codes: null,
  report_types: null,
  recipient_user_ids: [],
};

export default function Reports() {
  const [schedules, setSchedules] = useState<ReportSchedule[]>([]);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<ReportScheduleCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState<number | null>(null);

  function load() {
    setLoading(true);
    Promise.all([api.reports.list(), api.auth.users(), api.suppliers.list()])
      .then(([s, u, sup]) => {
        setSchedules(s);
        setUsers(u.filter(x => x.is_approved));
        setSuppliers(sup);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openCreate() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setShowModal(true);
  }

  function openEdit(s: ReportSchedule) {
    setEditId(s.id);
    setForm({
      name: s.name,
      enabled: s.enabled,
      day_of_week: s.day_of_week,
      send_hour: s.send_hour,
      report_period: s.report_period,
      supplier_codes: s.supplier_codes ?? null,
      report_types: s.report_types ?? null,
      recipient_user_ids: s.recipients.map(r => r.user_id),
    });
    setShowModal(true);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      if (editId != null) {
        const updated = await api.reports.update(editId, form);
        setSchedules(prev => prev.map(s => s.id === editId ? updated : s));
      } else {
        const created = await api.reports.create(form);
        setSchedules(prev => [...prev, created]);
      }
      setShowModal(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler beim Speichern");
    } finally {
      setSaving(false);
    }
  }

  async function toggleEnabled(s: ReportSchedule) {
    try {
      const updated = await api.reports.update(s.id, { enabled: !s.enabled });
      setSchedules(prev => prev.map(x => x.id === s.id ? updated : x));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    }
  }

  async function deleteSchedule(s: ReportSchedule) {
    if (!confirm(`Zeitplan "${s.name}" wirklich löschen?`)) return;
    try {
      await api.reports.delete(s.id);
      setSchedules(prev => prev.filter(x => x.id !== s.id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    }
  }

  async function sendNow(s: ReportSchedule) {
    setSending(s.id);
    setError(null);
    setSuccess(null);
    try {
      const res = await api.reports.sendNow(s.id);
      setSchedules(prev => prev.map(x => x.id === s.id
        ? { ...x, last_sent_at: new Date().toISOString() } : x));
      setSuccess(`Bericht "${s.name}" wird generiert und an ${res.sent_to.join(", ")} gesendet (${res.period}).`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler beim Senden");
    } finally {
      setSending(null);
    }
  }

  function toggleSupplier(code: string) {
    const current = form.supplier_codes ?? [];
    if (current.includes(code)) {
      const next = current.filter(c => c !== code);
      setForm(f => ({ ...f, supplier_codes: next.length ? next : null }));
    } else {
      setForm(f => ({ ...f, supplier_codes: [...current, code] }));
    }
  }

  function toggleReportType(value: string) {
    const current = form.report_types ?? [];
    if (current.includes(value)) {
      const next = current.filter(t => t !== value);
      setForm(f => ({ ...f, report_types: next.length ? next : null }));
    } else {
      setForm(f => ({ ...f, report_types: [...current, value] }));
    }
  }

  function toggleRecipient(userId: number) {
    setForm(f => ({
      ...f,
      recipient_user_ids: f.recipient_user_ids.includes(userId)
        ? f.recipient_user_ids.filter(id => id !== userId)
        : [...f.recipient_user_ids, userId],
    }));
  }

  const usersWithEmail = users.filter(u => u.email);

  function periodLabel(value: string) {
    return PERIODS.find(p => p.value === value)?.label ?? value;
  }

  function reportTypeLabels(types: string[] | null | undefined) {
    if (!types?.length) return "Alle Berichte";
    return types.map(t => REPORT_TYPES.find(r => r.value === t)?.label ?? t).join(", ");
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-800">Berichte</h1>
        <button onClick={openCreate}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">
          <Plus size={16} /> Neuer Bericht
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg px-4 py-3 text-sm mb-4">
          {success}
        </div>
      )}

      {usersWithEmail.length === 0 && !loading && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-4 py-3 text-sm mb-4">
          Hinweis: Kein Benutzer hat eine E-Mail-Adresse hinterlegt. Bitte zuerst unter{" "}
          <strong>Benutzer</strong> die E-Mail-Adressen eintragen.
        </div>
      )}

      {loading ? (
        <div className="text-gray-400 text-sm py-8 text-center">Lade…</div>
      ) : schedules.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400 text-sm">
          Noch keine Berichte konfiguriert. Klicke auf „Neuer Bericht".
        </div>
      ) : (
        <div className="space-y-3">
          {schedules.map(s => (
            <div key={s.id}
              className={`bg-white rounded-xl border shadow-sm px-5 py-4 flex items-center gap-4 ${
                s.enabled ? "border-gray-200" : "border-gray-100 opacity-60"
              }`}>
              <button onClick={() => toggleEnabled(s)} title={s.enabled ? "Deaktivieren" : "Aktivieren"}>
                {s.enabled
                  ? <CheckCircle2 size={20} className="text-emerald-500" />
                  : <XCircle size={20} className="text-gray-300" />}
              </button>

              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-800 text-sm">{s.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {DAYS[s.day_of_week]}, {String(s.send_hour).padStart(2, "0")}:00 Uhr
                  {" · "}
                  {periodLabel(s.report_period)}
                  {s.supplier_codes?.length
                    ? ` · Lieferanten: ${s.supplier_codes.join(", ")}`
                    : " · Alle Lieferanten"}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {reportTypeLabels(s.report_types)}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  Empfänger:{" "}
                  {s.recipients.length
                    ? s.recipients.map(r => r.username + (r.email ? ` <${r.email}>` : " (keine E-Mail)")).join(", ")
                    : "—"}
                </div>
                {s.last_sent_at && (
                  <div className="text-[11px] text-gray-400 mt-0.5">
                    Zuletzt gesendet: {new Date(s.last_sent_at).toLocaleString("de-DE")}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => sendNow(s)}
                  disabled={sending === s.id}
                  title="Jetzt senden"
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-blue-200 text-blue-600 hover:bg-blue-50 disabled:opacity-40"
                >
                  <Send size={13} />
                  {sending === s.id ? "Sende…" : "Jetzt senden"}
                </button>
                <button onClick={() => openEdit(s)} title="Bearbeiten"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100">
                  <Pencil size={15} />
                </button>
                <button onClick={() => deleteSchedule(s)} title="Löschen"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50">
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-800">
                {editId != null ? "Bericht bearbeiten" : "Neuer Bericht"}
              </h2>
            </div>
            <div className="px-6 py-5 space-y-4">

              {/* Name */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Name</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="z.B. Wochenbericht alle Lieferanten"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>

              {/* Day + Hour */}
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 mb-1">Wochentag</label>
                  <select
                    value={form.day_of_week}
                    onChange={e => setForm(f => ({ ...f, day_of_week: Number(e.target.value) }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                  >
                    {DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
                  </select>
                </div>
                <div className="w-28">
                  <label className="block text-xs font-medium text-gray-600 mb-1">Uhrzeit</label>
                  <select
                    value={form.send_hour}
                    onChange={e => setForm(f => ({ ...f, send_hour: Number(e.target.value) }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <option key={i} value={i}>{String(i).padStart(2, "0")}:00</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Period */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Berichtszeitraum</label>
                <select
                  value={form.report_period}
                  onChange={e => setForm(f => ({ ...f, report_period: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  {PERIODS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>

              {/* Report types */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Berichtsarten{" "}
                  <span className="font-normal text-gray-400">(leer = alle)</span>
                </label>
                <div className="space-y-1.5">
                  {REPORT_TYPES.map(rt => {
                    const selected = (form.report_types ?? []).includes(rt.value);
                    return (
                      <label key={rt.value}
                        className="flex items-center gap-2.5 text-sm cursor-pointer hover:bg-gray-50 rounded px-2 py-1">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleReportType(rt.value)}
                          className="w-4 h-4 accent-blue-600"
                        />
                        <span className="text-gray-700">{rt.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Suppliers */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Lieferanten{" "}
                  <span className="font-normal text-gray-400">(leer = alle)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {suppliers.filter(s => s.is_active).map(s => {
                    const selected = (form.supplier_codes ?? []).includes(s.code);
                    return (
                      <button
                        key={s.code}
                        type="button"
                        onClick={() => toggleSupplier(s.code)}
                        className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                          selected
                            ? "bg-blue-600 text-white border-blue-600"
                            : "border-gray-300 text-gray-600 hover:border-blue-400"
                        }`}
                      >
                        {s.code} – {s.name}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Recipients */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Empfänger</label>
                {users.length === 0 ? (
                  <p className="text-xs text-gray-400">Keine Benutzer vorhanden</p>
                ) : (
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {users.map(u => {
                      const selected = form.recipient_user_ids.includes(u.id);
                      return (
                        <label key={u.id}
                          className="flex items-center gap-2.5 text-sm cursor-pointer hover:bg-gray-50 rounded px-2 py-1">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleRecipient(u.id)}
                            className="w-4 h-4 accent-blue-600"
                          />
                          <span className="font-medium text-gray-700">{u.username}</span>
                          {u.email
                            ? <span className="text-gray-400 text-xs">{u.email}</span>
                            : <span className="text-amber-500 text-xs">keine E-Mail</span>}
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Enabled */}
              <label className="flex items-center gap-2.5 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))}
                  className="w-4 h-4 accent-blue-600"
                />
                <span className="text-gray-700">Zeitplan aktiv</span>
              </label>

              {error && (
                <p className="text-red-600 text-sm bg-red-50 rounded px-3 py-2">{error}</p>
              )}
            </div>

            <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-2">
              <button
                onClick={() => { setShowModal(false); setError(null); }}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                Abbrechen
              </button>
              <button
                onClick={save}
                disabled={saving || !form.name}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40"
              >
                {saving ? "Speichere…" : "Speichern"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
