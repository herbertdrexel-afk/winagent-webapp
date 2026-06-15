import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to: "/suppliers",            label: "Lieferanten" },
  { to: "/customers",            label: "Kunden" },
  { to: "/transactions",         label: "Rechnungen" },
  { to: "/commission-invoices",  label: "Provisionsrechnungen" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-[#1a3a5c] text-white shadow">
        <div className="max-w-7xl mx-auto flex items-center gap-8 px-6 py-3">
          <span className="font-bold text-lg tracking-wide">WinAgent</span>
          <nav className="flex gap-1 flex-1">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium transition-colors ` +
                  (isActive
                    ? "bg-white/20 text-white"
                    : "text-white/70 hover:text-white hover:bg-white/10")
                }
              >
                {label}
              </NavLink>
            ))}
            {user?.role === "admin" && (
              <NavLink
                to="/users"
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium transition-colors ` +
                  (isActive
                    ? "bg-white/20 text-white"
                    : "text-white/70 hover:text-white hover:bg-white/10")
                }
              >
                Benutzer
              </NavLink>
            )}
          </nav>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-white/60">{user?.username}</span>
            <button
              onClick={handleLogout}
              className="text-white/70 hover:text-white px-2 py-1 rounded hover:bg-white/10 transition-colors"
            >
              Abmelden
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
