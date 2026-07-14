import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useT } from "../context/LocaleContext";
import { api } from "../api";

export default function Login() {
  const { login } = useAuth();
  const t = useT();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await api.auth.register(username, password);
        setSuccess(t.login.registerSuccess);
        setMode("login");
        setUsername("");
        setPassword("");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t.common.error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f0f5fb] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-sm p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[#2563eb]">WinAgent</h1>
          <p className="text-sm text-gray-500 mt-1">{t.login.subtitle}</p>
        </div>

        <div className="flex rounded-lg border border-gray-200 mb-6 overflow-hidden">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(null); setSuccess(null); }}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                mode === m ? "bg-[#2563eb] text-white" : "text-gray-500 hover:bg-gray-50"
              }`}
            >
              {m === "login" ? t.login.login : t.login.register}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t.login.username}</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t.login.password}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
            />
          </div>

          {error && <p className="text-red-600 text-sm bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          {success && <p className="text-emerald-700 text-sm bg-emerald-50 rounded-lg px-3 py-2">{success}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#2563eb] text-white py-2.5 rounded-lg font-medium hover:bg-[#2563eb]/80 disabled:opacity-50 transition-colors"
          >
            {loading ? "…" : mode === "login" ? t.login.login : t.login.register}
          </button>
        </form>
      </div>
    </div>
  );
}
