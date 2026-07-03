import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  LayoutDashboard, Building2, Users, FileText, Receipt, UserCog, LogOut, BarChart2, Globe, Mail,
} from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: React.ElementType;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/",                    label: "Dashboard",       icon: LayoutDashboard },
  { to: "/suppliers",           label: "Lieferanten",     icon: Building2 },
  { to: "/customers",           label: "Kunden",          icon: Users },
  { to: "/transactions",        label: "Rechnungen",      icon: FileText },
  { to: "/commission-invoices", label: "Prov.-Rechn.",    icon: Receipt },
  { to: "/stats",               label: "Statistik",       icon: BarChart2 },
  { to: "/reports",             label: "Berichte",        icon: Mail },
  { to: "/mandants",            label: "Reybex",          icon: Globe,    adminOnly: true },
  { to: "/users",               label: "Benutzer",        icon: UserCog,  adminOnly: true },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/");
  }

  const items = NAV_ITEMS.filter((n) => !n.adminOnly || user?.role === "admin");

  return (
    <div className="min-h-screen flex bg-gray-50">

      {/* ── Desktop sidebar ── */}
      <aside className="hidden md:flex w-52 bg-white border-r border-gray-200 flex-col shrink-0 shadow-sm">
        <div className="flex items-center gap-3 px-5 py-5 border-b border-gray-100">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
            <span className="text-white font-bold text-xs leading-tight">WA</span>
          </div>
          <span className="font-semibold text-gray-800 text-sm">WinAgent</span>
        </div>

        <nav className="flex flex-col gap-0.5 flex-1 px-3 py-4">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ` +
                (isActive
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-500 hover:text-gray-800 hover:bg-gray-100")
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={17} strokeWidth={isActive ? 2 : 1.75} />
                  <span>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-gray-100 px-3 py-3 flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-bold uppercase shrink-0">
            {user?.username?.slice(0, 2)}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium text-gray-700 truncate">{user?.username}</div>
            <div className="text-[10px] text-gray-400">{user?.role === "admin" ? "Admin" : "Benutzer"}</div>
          </div>
          <button onClick={handleLogout} title="Abmelden"
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all">
            <LogOut size={15} />
          </button>
        </div>
      </aside>

      {/* ── Main column ── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-4 md:px-6 py-3 flex items-center gap-3 shrink-0">
          {/* Logo — mobile only */}
          <div className="flex items-center gap-2 md:hidden">
            <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
              <span className="text-white font-bold text-[10px] leading-tight">WA</span>
            </div>
            <span className="font-semibold text-gray-800 text-sm">WinAgent</span>
          </div>

          <div className="flex-1" />

          <span className="text-sm text-gray-500 hidden sm:inline">{user?.username}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium hidden sm:inline ${
            user?.role === "admin" ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-500"
          }`}>
            {user?.role === "admin" ? "Admin" : "Benutzer"}
          </span>

          {/* Mobile logout button in top bar */}
          <button onClick={handleLogout} title="Abmelden"
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all md:hidden">
            <LogOut size={16} />
          </button>
        </header>

        {/* Page content — pb-16 on mobile to clear bottom nav */}
        <main className="flex-1 p-3 md:p-6 overflow-auto pb-20 md:pb-6">
          <Outlet />
        </main>
      </div>

      {/* ── Mobile bottom nav ── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-40 shadow-lg">
        <div className="flex overflow-x-auto scrollbar-none">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center gap-0.5 px-3 py-2 min-w-[64px] shrink-0 transition-colors ` +
                (isActive ? "text-blue-600" : "text-gray-400")
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={20} strokeWidth={isActive ? 2.5 : 1.75} />
                  <span className="text-[10px] font-medium leading-tight text-center">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
