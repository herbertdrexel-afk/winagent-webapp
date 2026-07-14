import { useEffect, useRef, useState } from "react";
import { api, type BankAccount } from "../api";
import { useT } from "../context/LocaleContext";
import { Upload, Trash2, Save, Plus } from "lucide-react";

const CURRENCIES = ["EUR", "USD", "CHF"];
const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30";

export default function BankAccountsPage() {
  const t = useT();
  const [accounts, setAccounts]   = useState<Record<string, BankAccount>>({});
  const [uidNr, setUidNr]         = useState("");
  const [registration, setReg]    = useState("");
  const [logoUrl, setLogoUrl]     = useState<string | null>(null);
  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg]             = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([api.settings.getBankAccounts(), api.settings.getLogo()])
      .then(([ba, logo]) => {
        const filled: Record<string, BankAccount> = {};
        for (const c of CURRENCIES) {
          filled[c] = (ba[c] as BankAccount | undefined) ?? { bank: "", iban: "", bic: "" };
        }
        setAccounts(filled);
        setUidNr((ba.uid_nr as string | undefined) ?? "");
        setReg((ba.registration as string | undefined) ?? "");
        setLogoUrl(logo.data_url);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function setField(currency: string, field: "bank" | "iban" | "bic", value: string) {
    setAccounts(prev => ({
      ...prev,
      [currency]: { ...(prev[currency] ?? { bank: "", iban: "", bic: "" }), [field]: value },
    }));
  }

  async function handleSave() {
    setSaving(true);
    setMsg(null);
    try {
      await api.settings.saveBankAccounts({ ...accounts, uid_nr: uidNr, registration });
      setMsg({ ok: true, text: t.settings.savedMsg });
    } catch (e: unknown) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : t.common.error });
    } finally { setSaving(false); }
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMsg(null);
    try {
      await api.settings.uploadLogo(file);
      const logo = await api.settings.getLogo();
      setLogoUrl(logo.data_url);
      setMsg({ ok: true, text: t.settings.logoUploaded });
    } catch (err: unknown) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : t.common.error });
    } finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function handleLogoDelete() {
    if (!confirm("Logo löschen?")) return;
    await api.settings.deleteLogo();
    setLogoUrl(null);
    setMsg({ ok: true, text: "Logo gelöscht." });
  }

  if (loading) return <div className="text-gray-400 p-8">{t.common.loading}</div>;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-800">{t.settings.title}</h1>
        <p className="text-sm text-gray-500 mt-0.5">{t.settings.subtitle}</p>
      </div>

      {msg && (
        <div className={`text-sm px-4 py-2 rounded-lg border ${msg.ok ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-red-50 border-red-200 text-red-700"}`}>
          {msg.text}
        </div>
      )}

      {/* ── Logo ───────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h2 className="font-semibold text-gray-800">{t.settings.logo}</h2>
        <p className="text-xs text-gray-500">{t.settings.logoHint}</p>

        {logoUrl ? (
          <div className="flex items-start gap-4">
            <img src={logoUrl} alt="AMV Logo" className="h-16 object-contain border border-gray-200 rounded-lg p-1 bg-gray-50" />
            <div className="flex flex-col gap-2">
              <button onClick={() => fileRef.current?.click()} disabled={uploading}
                className="flex items-center gap-1.5 text-xs border border-[#2563eb] text-[#2563eb] px-3 py-1.5 rounded-lg hover:bg-[#2563eb]/5 disabled:opacity-50">
                <Upload size={12} /> {uploading ? t.settings.uploading : t.settings.replaceLogo}
              </button>
              <button onClick={handleLogoDelete}
                className="flex items-center gap-1.5 text-xs border border-red-300 text-red-600 px-3 py-1.5 rounded-lg hover:bg-red-50">
                <Trash2 size={12} /> {t.settings.deleteLogo}
              </button>
            </div>
          </div>
        ) : (
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="flex items-center gap-2 border-2 border-dashed border-gray-300 rounded-xl px-6 py-4 text-sm text-gray-500 hover:border-[#2563eb]/50 hover:text-[#2563eb] transition-colors disabled:opacity-50">
            <Plus size={16} /> {uploading ? t.settings.uploading : t.settings.uploadLogo}
          </button>
        )}
        <input ref={fileRef} type="file" accept="image/png,image/jpeg" className="hidden" onChange={handleLogoUpload} />
      </div>

      {/* ── Company details ─────────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
        <h2 className="font-semibold text-gray-800">{t.settings.companyData}</h2>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t.settings.uid}</label>
          <input type="text" value={uidNr} onChange={e => setUidNr(e.target.value)}
            className={inputCls} placeholder="ATU12345678" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t.settings.registration}</label>
          <input type="text" value={registration} onChange={e => setReg(e.target.value)}
            className={inputCls} placeholder="C12345" />
        </div>
        <div className="flex justify-end pt-1">
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 bg-[#2563eb] text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 disabled:opacity-50 transition-colors">
            <Save size={14} />
            {saving ? t.settings.saving : t.common.save}
          </button>
        </div>
      </div>

      {/* ── Bank accounts ───────────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-5">
        <h2 className="font-semibold text-gray-800">{t.settings.bankAccounts}</h2>
        <p className="text-xs text-gray-500">{t.settings.bankHint}</p>

        {CURRENCIES.map(cur => (
          <div key={cur} className="space-y-2 pb-4 border-b border-gray-100 last:border-0 last:pb-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-mono font-semibold text-[#2563eb] text-sm bg-[#2563eb]/10 px-2 py-0.5 rounded">{cur}</span>
            </div>
            <div className="grid grid-cols-1 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t.settings.bank}</label>
                <input type="text" value={accounts[cur]?.bank ?? ""}
                  onChange={e => setField(cur, "bank", e.target.value)}
                  className={inputCls} placeholder="z.B. UBS Europe" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">IBAN</label>
                <input type="text" value={accounts[cur]?.iban ?? ""}
                  onChange={e => setField(cur, "iban", e.target.value)}
                  className={inputCls + " font-mono"} placeholder="DE02 5022 0085 ..." />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">BIC / SWIFT</label>
                <input type="text" value={accounts[cur]?.bic ?? ""}
                  onChange={e => setField(cur, "bic", e.target.value)}
                  className={inputCls + " font-mono uppercase"} placeholder="SMHBDEFFXXX" />
              </div>
            </div>
          </div>
        ))}

        <div className="flex justify-end pt-2">
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 bg-[#2563eb] text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 disabled:opacity-50 transition-colors">
            <Save size={14} />
            {saving ? t.settings.saving : t.settings.saveBanks}
          </button>
        </div>
      </div>
    </div>
  );
}
