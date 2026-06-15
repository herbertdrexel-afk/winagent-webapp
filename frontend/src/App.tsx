import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Suppliers from "./pages/Suppliers";
import Customers from "./pages/Customers";
import Transactions from "./pages/Transactions";
import CommissionInvoices from "./pages/CommissionInvoices";
import UserManagement from "./pages/UserManagement";
import Login from "./pages/Login";
import { useAuth } from "./context/AuthContext";

function ProtectedRoutes() {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen bg-[#f0f5fb] flex items-center justify-center text-gray-400">
      Lade…
    </div>
  );
  if (!user) return <Login />;
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/suppliers" replace />} />
        <Route path="suppliers"    element={<Suppliers />} />
        <Route path="customers"    element={<Customers />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="commission-invoices" element={<CommissionInvoices />} />
        {user.role === "admin" && (
          <Route path="users" element={<UserManagement />} />
        )}
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ProtectedRoutes />
    </BrowserRouter>
  );
}
