import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/suppliers",    label: "Lieferanten" },
  { to: "/customers",    label: "Kunden" },
  { to: "/transactions", label: "Transaktionen" },
  { to: "/commission",   label: "Provisionsabrechnungen" },
];

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-[#1a3a5c] text-white shadow">
        <div className="max-w-7xl mx-auto flex items-center gap-8 px-6 py-3">
          <span className="font-bold text-lg tracking-wide">WinAgent</span>
          <nav className="flex gap-1">
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
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
