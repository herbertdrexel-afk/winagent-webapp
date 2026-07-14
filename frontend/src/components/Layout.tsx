import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { SearchProvider, useSearch } from "../context/SearchContext";
import { LogOut, Search, X } from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  short: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/",                    label: "Dashboard",     short: "D" },
  { to: "/commission-invoices", label: "Provisionen",   short: "%" },
  { to: "/suppliers",           label: "Lieferanten",   short: "L" },
  { to: "/customers",           label: "Kunden",        short: "K" },
  { to: "/transactions",        label: "Rechnungen",    short: "R" },
  { to: "/stats",               label: "Statistik",     short: "S" },
  { to: "/reports",             label: "Berichte",      short: "B" },
  { to: "/bank-accounts",       label: "Einstellungen", short: "⚙", adminOnly: true },
  { to: "/users",               label: "Benutzer",      short: "U",  adminOnly: true },
];

function LetterBox({ short, active }: { short: string; active?: boolean }) {
  return (
    <div
      className="flex items-center justify-center shrink-0 text-white font-bold text-[11px]"
      style={{ width: 22, height: 22, borderRadius: 5, background: active ? "#1d4ed8" : "#2563eb" }}
    >
      {short}
    </div>
  );
}

// Inner component so it can use SearchContext
function LayoutInner() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { setQuery } = useSearch();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [localSearch, setLocalSearch] = useState("");
  // open tabs: array of route paths in visit order
  const [openTabs, setOpenTabs] = useState<string[]>([location.pathname]);
  const searchRef = useRef<HTMLInputElement>(null);

  const items = NAV_ITEMS.filter(n => !n.adminOnly || user?.role === "admin");

  function labelFor(path: string) {
    const item = items.find(n =>
      n.to === "/" ? path === "/" : path === n.to || path.startsWith(n.to + "/")
    );
    return item?.label ?? path;
  }

  // Track visited tabs; clear search on navigation
  useEffect(() => {
    const path = location.pathname;
    setOpenTabs(prev => prev.includes(path) ? prev : [...prev, path]);
    setLocalSearch("");
    setQuery("");
  }, [location.pathname]);

  function closeTab(path: string) {
    setOpenTabs(prev => {
      const next = prev.filter(t => t !== path);
      if (location.pathname === path) {
        navigate(next[next.length - 1] ?? "/");
      }
      return next.length > 0 ? next : ["/"];
    });
  }

  function handleSearchChange(val: string) {
    setLocalSearch(val);
    setQuery(val);
  }

  function handleLogout() {
    logout();
    navigate("/");
  }

  const currentItem = items.find(item =>
    item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)
  );

  const initials = (user?.username ?? "NA").slice(0, 2).toUpperCase();

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ height: "100dvh", minHeight: "-webkit-fill-available", background: "#f7f8fa" }}
    >
      {/* ══ TOP BAR ══ */}
      <header
        className="flex items-center gap-3 shrink-0 z-30 px-4"
        style={{ height: 52, background: "#f7f8fa", borderBottom: "1px solid #e2e5eb" }}
      >
        {/* Hamburger — mobile only */}
        <button
          className="md:hidden p-1 -ml-1"
          onClick={() => setDrawerOpen(true)}
          style={{ background: "none", border: "none", cursor: "pointer" }}
          aria-label="Menü öffnen"
        >
          <div className="flex flex-col gap-[5px]">
            {[0, 1, 2].map(i => (
              <span key={i} style={{ display: "block", height: 2, width: 18, background: "#4b5563", borderRadius: 1 }} />
            ))}
          </div>
        </button>

        {/* Logo */}
        <div className="flex items-center gap-2 shrink-0" style={{ fontWeight: 700, fontSize: 17, color: "#111827" }}>
          <div
            className="flex items-center justify-center text-white font-extrabold text-xs shrink-0"
            style={{ width: 22, height: 22, borderRadius: 5, background: "#2563eb" }}
          >W</div>
          <span className="hidden sm:block">WinAgent</span>
        </div>

        {/* Search — tablet/desktop */}
        <div className="hidden md:flex flex-1 max-w-lg ml-2">
          <input
            ref={searchRef}
            value={localSearch}
            onChange={e => handleSearchChange(e.target.value)}
            placeholder={`${currentItem?.label ?? "Inhalt"} durchsuchen …`}
            className="flex-1 bg-white text-[13px] px-3 focus:outline-none"
            style={{ height: 32, border: "1px solid #d1d5db", borderRight: "none", borderRadius: "4px 0 0 4px" }}
            onFocus={e => (e.currentTarget.style.borderColor = "#2563eb")}
            onBlur={e => (e.currentTarget.style.borderColor = "#d1d5db")}
          />
          {localSearch ? (
            <button
              onClick={() => handleSearchChange("")}
              className="flex items-center justify-center bg-white px-2"
              style={{ height: 32, border: "1px solid #d1d5db", borderLeft: "none", borderRight: "none", cursor: "pointer" }}
            >
              <X size={13} style={{ color: "#6b7280" }} />
            </button>
          ) : null}
          <button
            onClick={() => searchRef.current?.focus()}
            className="flex items-center gap-1.5 text-white text-[13px] font-semibold px-4 shrink-0"
            style={{ height: 32, background: "#2563eb", border: "none", borderRadius: "0 4px 4px 0", cursor: "pointer" }}
          >
            <Search size={13} /> Suchen
          </button>
        </div>

        <div className="flex-1" />

        <span className="hidden sm:block text-[13px]" style={{ color: "#374151" }}>{user?.username}</span>

        <div
          className="flex items-center justify-center shrink-0 text-white text-[12px] font-bold"
          style={{ width: 30, height: 30, borderRadius: "50%", background: "#2563eb" }}
        >
          {initials}
        </div>

        <button
          onClick={handleLogout}
          className="flex items-center p-1"
          style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280" }}
          title="Abmelden"
        >
          <LogOut size={15} />
        </button>
      </header>

      {/* ══ TAB BAR — desktop only (lg+) ══ */}
      <div
        className="hidden lg:flex items-stretch shrink-0 overflow-x-auto"
        style={{ height: 36, background: "#f0f2f5", borderBottom: "1px solid #d1d5db", flexShrink: 0 }}
      >
        {openTabs.map(path => {
          const isActive = location.pathname === path || (path !== "/" && location.pathname.startsWith(path));
          return (
            <div
              key={path}
              className="flex items-center shrink-0"
              style={{
                background: isActive ? "#111827" : "transparent",
                borderRight: "1px solid #d1d5db",
              }}
            >
              <button
                onClick={() => navigate(path)}
                className="flex items-center gap-1.5 px-3 text-[12px] h-full"
                style={{ background: "none", border: "none", cursor: "pointer", color: isActive ? "#fff" : "#6b7280", whiteSpace: "nowrap" }}
              >
                {labelFor(path)}
              </button>
              <button
                onClick={e => { e.stopPropagation(); closeTab(path); }}
                className="flex items-center justify-center pr-2"
                style={{ background: "none", border: "none", cursor: "pointer", color: isActive ? "#9ca3af" : "#9ca3af", opacity: isActive ? 1 : 0.6 }}
                aria-label="Tab schließen"
              >
                <X size={11} />
              </button>
            </div>
          );
        })}
      </div>

      {/* ══ BODY ══ */}
      <div className="flex flex-1 overflow-hidden">

        {/* Mobile drawer overlay */}
        {drawerOpen && (
          <div
            className="md:hidden fixed inset-0 z-40"
            style={{ background: "rgba(0,0,0,0.4)" }}
            onClick={() => setDrawerOpen(false)}
          />
        )}

        {/* Mobile drawer */}
        <aside
          className={`md:hidden fixed top-0 left-0 h-full z-50 flex flex-col transition-transform duration-200 ease-in-out ${
            drawerOpen ? "translate-x-0" : "-translate-x-full"
          }`}
          style={{ width: 200, background: "#fff", borderRight: "1px solid #e2e5eb" }}
        >
          <div
            className="flex items-center justify-between px-4 py-4 shrink-0"
            style={{ borderBottom: "1px solid #e2e5eb" }}
          >
            <div className="flex items-center gap-2" style={{ fontWeight: 700, fontSize: 17, color: "#111827" }}>
              <div
                className="flex items-center justify-center text-white font-extrabold text-xs"
                style={{ width: 22, height: 22, borderRadius: 5, background: "#2563eb" }}
              >W</div>
              WinAgent
            </div>
            <button
              onClick={() => setDrawerOpen(false)}
              style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280" }}
              aria-label="Menü schließen"
            >
              <X size={18} />
            </button>
          </div>

          {/* Mobile search */}
          <div className="px-3 pt-3 pb-2" style={{ borderBottom: "1px solid #e2e5eb" }}>
            <input
              value={localSearch}
              onChange={e => handleSearchChange(e.target.value)}
              placeholder="Suchen …"
              className="w-full bg-white text-[13px] px-3 focus:outline-none"
              style={{ height: 32, border: "1px solid #d1d5db", borderRadius: 4 }}
            />
          </div>

          <nav className="flex-1 flex flex-col gap-0.5 p-3 overflow-y-auto">
            {items.map(({ to, label, short }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                onClick={() => setDrawerOpen(false)}
                style={{ textDecoration: "none" }}
              >
                {({ isActive }) => (
                  <div
                    className="flex items-center gap-3 px-3 py-2 transition-colors"
                    style={{ borderRadius: 6, background: isActive ? "#dbeafe" : "transparent", cursor: "pointer" }}
                  >
                    <LetterBox short={short} />
                    <span style={{ fontSize: 13, color: isActive ? "#1d4ed8" : "#374151", fontWeight: isActive ? 600 : 400 }}>
                      {label}
                    </span>
                  </div>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="shrink-0 p-3" style={{ borderTop: "1px solid #e2e5eb" }}>
            <button
              onClick={() => { handleLogout(); setDrawerOpen(false); }}
              className="flex items-center gap-2.5 w-full px-3 py-2 text-[13px] rounded-[6px] transition-colors hover:bg-red-50"
              style={{ background: "none", border: "none", cursor: "pointer", color: "#dc2626" }}
            >
              <LogOut size={15} /> Abmelden
            </button>
          </div>
        </aside>

        {/* Desktop / tablet sidebar (md+) */}
        <aside
          className="hidden md:flex flex-col items-center shrink-0 py-2"
          style={{ width: 74, background: "#f7f8fa", borderRight: "1px solid #e2e5eb", gap: 2 }}
        >
          {items.map(({ to, label, short }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              style={{ textDecoration: "none", width: 58 }}
            >
              {({ isActive }) => (
                <div
                  className={
                    "flex flex-col items-center py-2 transition-colors " +
                    (isActive ? "bg-[#dbeafe]" : "hover:bg-[#eff6ff]")
                  }
                  style={{ width: 58, borderRadius: 6, cursor: "pointer", gap: 4 }}
                >
                  <LetterBox short={short} active={isActive} />
                  <span className="text-center leading-tight" style={{ fontSize: 10, color: "#374151" }}>
                    {label}
                  </span>
                </div>
              )}
            </NavLink>
          ))}

          <div className="flex-1" />

          <button
            onClick={handleLogout}
            className="flex flex-col items-center py-2 rounded-[6px] transition-colors hover:bg-red-50 w-[58px]"
            style={{ background: "none", border: "none", cursor: "pointer", gap: 4 }}
            title="Abmelden"
          >
            <LogOut size={15} style={{ color: "#9ca3af" }} />
            <span className="leading-tight" style={{ fontSize: 10, color: "#9ca3af" }}>Abmelden</span>
          </button>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto" style={{ padding: "16px 16px 80px" }}>
          <Outlet />
        </main>
      </div>

      {/* ══ MOBILE BOTTOM NAV ══ */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 flex overflow-x-auto"
        style={{ background: "#f7f8fa", borderTop: "1px solid #e2e5eb" }}
      >
        {items.map(({ to, label, short }) => (
          <NavLink key={to} to={to} end={to === "/"} style={{ textDecoration: "none" }}>
            {({ isActive }) => (
              <div
                className="flex flex-col items-center justify-center"
                style={{ minWidth: 56, padding: "6px 8px", gap: 3, cursor: "pointer", flexShrink: 0 }}
              >
                <div
                  className="flex items-center justify-center text-white font-bold text-[10px]"
                  style={{ width: 22, height: 22, borderRadius: 5, background: isActive ? "#2563eb" : "#9ca3af" }}
                >
                  {short}
                </div>
                <span style={{ fontSize: 9, color: isActive ? "#2563eb" : "#6b7280", fontWeight: 500, textAlign: "center", lineHeight: 1.2 }}>
                  {label}
                </span>
              </div>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

export default function Layout() {
  return (
    <SearchProvider>
      <LayoutInner />
    </SearchProvider>
  );
}
