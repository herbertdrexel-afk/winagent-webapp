import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  LayoutDashboard, Building2, Users, FileText, Receipt, UserCog, LogOut,
} from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: React.ElementType;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/",                    label: "Dashboard",           icon: LayoutDashboard },
  { to: "/suppliers",           label: "Lieferanten",         icon: Building2 },
  { to: "/customers",           label: "Kunden",              icon: Users },
  { to: "/transactions",        label: "Rechnungen",          icon: FileText },
  { to: "/commission-invoices", label: "Provisionsrechnungen",icon: Receipt },
  { to: "/users",               label: "Benutzer",            icon: UserCog, adminOnly: true },
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
    <div className="min-h-screen flex bg-[#f0f5fb]">
      {/* Sidebar */}
      <aside className="w-[72px] bg-[#1a3a5c] flex flex-col items-center py-4 gap-1 shrink-0 shadow-lg z-10">
        {/* Logo */}
        <div className="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center mb-3">
          <span className="text-white font-bold text-xs leading-tight text-center">W<br/>A</span>
        </div>

        {/* Nav items */}
        <nav className="flex flex-col items-center gap-1 flex-1 w-full px-2">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `w-full flex flex-col items-center gap-1 py-2.5 px-1 rounded-xl text-center transition-all cursor-pointer ` +
                (isActive
                  ? "bg-white/20 text-white"
                  : "text-white/55 hover:text-white hover:bg-white/10")
              }
            >
              <Icon size={20} strokeWidth={1.75} />
              <span className="text-[9px] font-medium leading-tight">{label.split(" ")[0]}</span>
            </NavLink>
          ))}
        </nav>

        {/* User + logout at bottom */}
        <div className="flex flex-col items-center gap-2 mt-2 w-full px-2">
          <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-white text-xs font-bold uppercase">
            {user?.username?.slice(0, 2)}
          </div>
          <button
            onClick={handleLogout}
            title="Abmelden"
            className="w-full flex flex-col items-center gap-1 py-2 px-1 rounded-xl text-white/50 hover:text-white hover:bg-white/10 transition-all"
          >
            <LogOut size={18} strokeWidth={1.75} />
            <span className="text-[9px] font-medium">Logout</span>
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4 shrink-0">
          <div className="flex-1" />
          <span className="text-sm text-gray-400">{user?.username}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            user?.role === "admin" ? "bg-[#1a3a5c]/10 text-[#1a3a5c]" : "bg-gray-100 text-gray-500"
          }`}>
            {user?.role === "admin" ? "Admin" : "Benutzer"}
          </span>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
