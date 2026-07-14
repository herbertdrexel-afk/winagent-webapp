import { useEffect, useState } from "react";
import { Pencil } from "lucide-react";
import { api, type AuthUser } from "../api";
import { useAuth } from "../context/AuthContext";
import { useT } from "../context/LocaleContext";

function EmailCell({ user, onSaved }: { user: AuthUser; onSaved: (u: AuthUser) => void }) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(user.email ?? "");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const updated = await api.auth.updateUser(user.id, { email: val || "" });
      onSaved(updated);
      setEditing(false);
    } finally { setSaving(false); }
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <input
          value={val}
          onChange={e => setVal(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
          autoFocus
          className="border border-blue-300 rounded px-2 py-0.5 text-xs w-44 focus:outline-none"
        />
        <button onClick={save} disabled={saving} className="text-xs text-blue-600 hover:text-blue-800 px-1">✓</button>
        <button onClick={() => setEditing(false)} className="text-xs text-gray-400 hover:text-gray-600 px-1">✕</button>
      </div>
    );
  }

  return (
    <button onClick={() => { setVal(user.email ?? ""); setEditing(true); }}
      className="text-xs text-gray-500 hover:text-blue-600 hover:underline text-left">
      {user.email || <span className="text-gray-300 italic">{t.users.noEmail}</span>}
    </button>
  );
}

export default function UserManagement() {
  const { user: me } = useAuth();
  const t = useT();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New user form
  const [newUser, setNewUser] = useState("");
  const [newPass, setNewPass] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [creating, setCreating] = useState(false);

  // Edit modal
  const [editUser, setEditUser] = useState<AuthUser | null>(null);
  const [editFirst, setEditFirst] = useState("");
  const [editLast, setEditLast] = useState("");
  const [editLang, setEditLang] = useState("de");
  const [editSaving, setEditSaving] = useState(false);

  function load() {
    setLoading(true);
    api.auth.users()
      .then(setUsers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openEdit(u: AuthUser) {
    setEditUser(u);
    setEditFirst(u.first_name ?? "");
    setEditLast(u.last_name ?? "");
    setEditLang(u.language ?? "de");
  }

  async function saveEdit() {
    if (!editUser) return;
    setEditSaving(true);
    try {
      const updated = await api.auth.updateUser(editUser.id, {
        first_name: editFirst,
        last_name: editLast,
        language: editLang,
      });
      setUsers(prev => prev.map(x => x.id === updated.id ? updated : x));
      setEditUser(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t.common.error);
    } finally { setEditSaving(false); }
  }

  async function toggleApproval(u: AuthUser) {
    try {
      const updated = await api.auth.updateUser(u.id, { is_approved: !u.is_approved });
      setUsers((prev) => prev.map((x) => x.id === u.id ? updated : x));
    } catch (e: unknown) { setError(e instanceof Error ? e.message : t.common.error); }
  }

  async function changeRole(u: AuthUser, role: string) {
    try {
      const updated = await api.auth.updateUser(u.id, { role });
      setUsers((prev) => prev.map((x) => x.id === u.id ? updated : x));
    } catch (e: unknown) { setError(e instanceof Error ? e.message : t.common.error); }
  }

  async function deleteUser(u: AuthUser) {
    if (!confirm(t.users.confirmDelete(u.username))) return;
    try {
      await api.auth.deleteUser(u.id);
      setUsers((prev) => prev.filter((x) => x.id !== u.id));
    } catch (e: unknown) { setError(e instanceof Error ? e.message : t.common.error); }
  }

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const created = await api.auth.register(newUser, newPass);
      const updated = await api.auth.updateUser(created.id, { is_approved: true, role: newRole });
      setUsers((prev) => [...prev, updated]);
      setNewUser(""); setNewPass(""); setNewRole("user");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : t.common.error); }
    finally { setCreating(false); }
  }

  const pending  = users.filter((u) => !u.is_approved);
  const approved = users.filter((u) => u.is_approved);

  const colCls = "px-4 py-3 text-left font-medium";

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-800 mb-6">{t.users.title}</h1>
      {error && <p className="text-red-600 mb-4 bg-red-50 rounded-lg px-4 py-2 text-sm">{error}</p>}

      {/* Pending approvals */}
      {pending.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6">
          <h2 className="text-sm font-semibold text-amber-800 mb-3">{t.users.pending(pending.length)}</h2>
          <div className="space-y-2">
            {pending.map((u) => (
              <div key={u.id} className="flex items-center justify-between bg-white rounded-lg px-4 py-2 border border-amber-100">
                <span className="font-medium text-gray-800">{u.username}</span>
                <div className="flex gap-2">
                  <button onClick={() => toggleApproval(u)}
                    className="bg-emerald-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-emerald-700">
                    {t.users.approve}
                  </button>
                  <button onClick={() => deleteUser(u)}
                    className="border border-red-300 text-red-600 text-xs px-3 py-1.5 rounded-lg hover:bg-red-50">
                    {t.users.reject}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* User table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto mb-6">
        <table className="w-full text-sm" style={{ minWidth: 680 }}>
          <thead className="bg-[#2563eb] text-white">
            <tr>
              <th className={colCls}>{t.users.username}</th>
              <th className={colCls}>{t.users.email}</th>
              <th className={colCls}>{t.users.nameFull}</th>
              <th className={colCls}>{t.users.language}</th>
              <th className={colCls}>{t.users.role}</th>
              <th className={colCls}>{t.users.status}</th>
              <th className={colCls}>{t.users.actions}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">{t.common.loading}</td></tr>
            ) : approved.map((u, i) => (
              <tr key={u.id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                <td className="px-4 py-3 font-medium">
                  {u.username}
                  {u.id === me?.id && <span className="ml-2 text-xs text-gray-400">{t.users.me}</span>}
                </td>
                <td className="px-4 py-3">
                  <EmailCell user={u} onSaved={(updated) =>
                    setUsers(prev => prev.map(x => x.id === updated.id ? updated : x))
                  } />
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs">
                  {(u.first_name || u.last_name)
                    ? [u.first_name, u.last_name].filter(Boolean).join(" ")
                    : <span className="text-gray-300 italic">—</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                    u.language === "en"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-100 text-gray-600"
                  }`}>
                    {u.language === "en" ? "EN" : "DE"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {u.id === me?.id ? (
                    <span className="text-xs bg-[#2563eb]/10 text-[#2563eb] px-2 py-0.5 rounded-full">
                      {u.role === "admin" ? t.users.roleAdmin : t.users.roleUser}
                    </span>
                  ) : (
                    <select value={u.role} onChange={(e) => changeRole(u, e.target.value)}
                      className="border border-gray-200 rounded px-2 py-0.5 text-xs">
                      <option value="user">{t.users.roleUser}</option>
                      <option value="admin">{t.users.roleAdmin}</option>
                    </select>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">{t.users.active}</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    <button onClick={() => openEdit(u)} title={t.users.editTitle}
                      className="text-blue-500 hover:bg-blue-50 border border-blue-200 p-1 rounded">
                      <Pencil size={12} />
                    </button>
                    {u.id !== me?.id && (
                      <button onClick={() => deleteUser(u)}
                        className="text-xs text-red-600 hover:text-red-800 border border-red-200 px-2 py-1 rounded">
                        {t.users.delete}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create new user */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">{t.users.newUser}</h2>
        <form onSubmit={createUser} className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.users.newUsername}</label>
            <input value={newUser} onChange={(e) => setNewUser(e.target.value)} required
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.users.newPassword}</label>
            <input type="password" value={newPass} onChange={(e) => setNewPass(e.target.value)} required
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.users.newRole}</label>
            <select value={newRole} onChange={(e) => setNewRole(e.target.value as "user" | "admin")}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30">
              <option value="user">{t.users.roleUser}</option>
              <option value="admin">{t.users.roleAdmin}</option>
            </select>
          </div>
          <button type="submit" disabled={creating}
            className="bg-[#2563eb] text-white px-4 py-1.5 rounded-lg text-sm hover:bg-[#2563eb]/80 disabled:opacity-50">
            {creating ? t.users.creating : t.users.create}
          </button>
        </form>
      </div>

      {/* Edit modal */}
      {editUser && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
          onClick={e => { if (e.target === e.currentTarget) setEditUser(null); }}>
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm p-6">
            <h2 className="text-base font-semibold text-gray-800 mb-4">
              {t.users.editTitle}: <span className="text-[#2563eb]">{editUser.username}</span>
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t.users.firstName}</label>
                <input value={editFirst} onChange={e => setEditFirst(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t.users.lastName}</label>
                <input value={editLast} onChange={e => setEditLast(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t.users.language}</label>
                <select value={editLang} onChange={e => setEditLang(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30">
                  <option value="de">{t.users.langDe}</option>
                  <option value="en">{t.users.langEn}</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={saveEdit} disabled={editSaving}
                className="flex-1 bg-[#2563eb] text-white py-2 rounded-lg text-sm font-medium hover:bg-[#2563eb]/80 disabled:opacity-50">
                {editSaving ? "…" : t.users.save}
              </button>
              <button onClick={() => setEditUser(null)}
                className="flex-1 border border-gray-200 text-gray-600 py-2 rounded-lg text-sm hover:bg-gray-50">
                {t.users.cancel}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
