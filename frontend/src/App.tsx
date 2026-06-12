import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Suppliers from "./pages/Suppliers";
import Customers from "./pages/Customers";
import Transactions from "./pages/Transactions";
import Commission from "./pages/Commission";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/suppliers" replace />} />
          <Route path="suppliers"    element={<Suppliers />} />
          <Route path="customers"    element={<Customers />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="commission"   element={<Commission />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
