import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Suppliers from "./pages/Suppliers";
import Customers from "./pages/Customers";
import Transactions from "./pages/Transactions";
import CommissionInvoices from "./pages/CommissionInvoices";
import SupplierStats from "./pages/SupplierStats";
import UserManagement from "./pages/UserManagement";
import BankAccounts from "./pages/BankAccounts";
import Reports from "./pages/Reports";
import Login from "./pages/Login";
import { useAuth } from "./context/AuthContext";
import { LocaleProvider } from "./context/LocaleContext";

function ProtectedRoutes() {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen bg-[#f0f5fb] flex items-center justify-center text-gray-400">
      Lade…
    </div>
  );
  return (
    <LocaleProvider>
      {!user ? (
        <Login />
      ) : (
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="suppliers"           element={<Suppliers />} />
            <Route path="customers"           element={<Customers />} />
            <Route path="transactions"        element={<Transactions />} />
            <Route path="commission-invoices" element={<CommissionInvoices />} />
            <Route path="stats"               element={<SupplierStats />} />
            {user.role === "admin" && (
              <>
                <Route path="reports" element={<Reports />} />
                <Route path="users" element={<UserManagement />} />
                <Route path="bank-accounts" element={<BankAccounts />} />
              </>
            )}
          </Route>
        </Routes>
      )}
    </LocaleProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ProtectedRoutes />
    </BrowserRouter>
  );
}
