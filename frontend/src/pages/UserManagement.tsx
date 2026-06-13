import { useEffect, useState } from "react";
import { api, type AuthUser } from "../api";
import { useAuth } from "../context/AuthContext";

export default function UserManagement() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New user form
  const [newUser, setNewUser] = useState("");
  const [newPass, setNewPass] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [creating, setCreating] = useState(false);

  function load() {
    setLoading(true);
    api.auth.users()
      .then(setUsers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function toggleApproval(u: AuthUser) {
    try {
      const updated = await api.auth.updateUser(u.id, { is_approved: !u.is_approved });
      setUsers((prev) => prev.map((x) => x.id === u.id ? updated : x));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    }
  }

  async function changeRole(u: AuthUser, role: string) {
    try {
      const updated = await api.auth.updateUser(u.id, { role });
      setUsers((prev) => prev.map((x) => x.id === u.id ? updated : x));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    }
  }

  async function deleteUser(u: AuthUser) {
    if (!confirm(`Benutzer "${u.username}" wirklich löschen?`)) return;
    try {
      await api.auth.deleteUser(u.id);
      setUsers((prev) => prev.filter((x) => x.id !== u.id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    }
  }

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const created = await api.auth.register(newUser, newPass);
      // auto-approve + set role
      const updated = await api.auth.updateUser(created.id, { is_approved: true, role: newRole });
      setUsers((prev) => [...prev, updated]);
      setNewUser(""); setNewPass(""); setNewRole("user");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setCreating(false);
    }
  }

  const pending = users.filter((u) => !u.is_approved);
  const approved = users.filter((u) => u.is_approved);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-800 mb-6">Benutzerverwaltung</h1>
      {error && <p className="text-red-600 mb-4 bg-red-50 rounded-lg px-4 py-2 text-sm">{error}</p>}

      {/* Pending approvals */}
      {pending.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6">
          <h2 className="text-sm font-semibold text-amber-800 mb-3">
            Ausstehende Freigaben ({pending.length})
          </h2>
          <div className="space-y-2">
            {pending.map((u) => (
              <div key={u.id} className="flex items-center justify-between bg-white rounded-lg px-4 py-2 border border-amber-100">
                <span className="font-medium text-gray-800">{u.username}</span>
                <div className="flex gap-2">
                  <button
                    onClick={() => toggleApproval(u)}
                    className="bg-emerald-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-emerald-700"
                  >
                    Freigeben
                  </button>
                  <button
                    onClick={() => deleteUser(u)}
                    className="border border-red-300 text-red-600 text-xs px-3 py-1.5 rounded-lg hover:bg-red-50"
                  >
                    Ablehnen
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* User table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-6">
        <table className="w-full text-sm">
          <thead className="bg-[#1a3a5c] text-white">
            <tr>
              {["Benutzername", "Rolle", "Status", "Aktionen"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">Lade…</td></tr>
            ) : approved.map((u, i) => (
              <tr key={u.id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                <td className="px-4 py-3 font-medium">
                  {u.username}
                  {u.id === me?.id && <span className="ml-2 text-xs text-gray-400">(ich)</span>}
                </td>
                <td className="px-4 py-3">
                  {u.id === me?.id ? (
                    <span className="text-xs bg-[#1a3a5c]/10 text-[#1a3a5c] px-2 py-0.5 rounded-full">
                      {u.role === "admin" ? "Administrator" : "Benutzer"}
                    </span>
                  ) : (
                    <select
                      value={u.role}
                      onChange={(e) => changeRole(u, e.target.value)}
                      className="border border-gray-200 rounded px-2 py-0.5 text-xs"
                    >
                      <option value="user">Benutzer</option>
                      <option value="admin">Administrator</option>
                    </select>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">Aktiv</span>
                </td>
                <td className="px-4 py-3">
                  {u.id !== me?.id && (
                    <button
                      onClick={() => deleteUser(u)}
                      className="text-xs text-red-600 hover:text-red-800 border border-red-200 px-2 py-1 rounded"
                    >
                      Löschen
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create new user */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Neuen Benutzer anlegen</h2>
        <form onSubmit={createUser} className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Benutzername</label>
            <input value={newUser} onChange={(e) => setNewUser(e.target.value)} required
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Passwort</label>
            <input type="password" value={newPass} onChange={(e) => setNewPass(e.target.value)} required
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Rolle</label>
            <select value={newRole} onChange={(e) => setNewRole(e.target.value as "user" | "admin")}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/30">
              <option value="user">Benutzer</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          <button type="submit" disabled={creating}
            className="bg-[#1a3a5c] text-white px-4 py-1.5 rounded-lg text-sm hover:bg-[#1a3a5c]/80 disabled:opacity-50">
            {creating ? "…" : "Anlegen"}
          </button>
        </form>
      </div>
    </div>
  );
}
