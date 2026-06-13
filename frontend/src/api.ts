// Im Dev-Modus: Vite-Proxy auf localhost:8000
// In Produktion: VITE_API_URL=https://winagent-backend.up.railway.app
const BASE = import.meta.env.VITE_API_URL ?? "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────
export interface Supplier {
  id: number;
  code: string;
  name: string;
  address?: string;
  default_currency?: string;
  provision_splits?: { rate: number; rep_code: string }[];
  representative_code?: string;
  contact_person?: string;
  is_active: boolean;
}

export interface Customer {
  id: number;
  code: string;
  ku_nr?: string;
  name: string;
  country_code?: string;
  zip?: string;
  city?: string;
  phone?: string;
  fax?: string;
  email?: string;
  url?: string;
  language?: string;
  contact_name?: string;
  contact_title?: string;
  contact_position?: string;
  notes?: string;
}

export interface Transaction {
  id: number;
  customer_id?: number;
  customer_code?: string;
  customer_ku_nr?: string;
  customer_name?: string;
  invoice_number: string;
  invoice_date: string;
  art_nr?: string;
  color?: string;
  quantity?: string;
  unit?: string;
  discount?: string;
  provision_rate?: string;
  price?: string;
  currency?: string;
  total_amount: string;
  exchange_rate?: string;
  customer_order_no?: string;
  notes?: string;
}

export type TransactionUpdate = Partial<Omit<Transaction, "id">>;

export interface PdfEntry {
  customer_name_raw: string;
  customer_name_clean: string;
  invoice_date: string;
  invoice_number: string;
  art_nr: string;
  total_amount: number;
  provision_rate: number;
  provision_amount: number;
  currency: string;
  customer_suggestions: { id: number; code: string; ku_nr?: string; name: string; city?: string }[];
}

export interface CommissionStatement {
  id: number;
  supplier_id: number;
  statement_number?: string;
  period_from: string;
  period_to: string;
  statement_date?: string;
  status: "draft" | "issued";
  total_amount?: string;
  total_provision?: string;
  currency?: string;
}

// ── Endpoints ──────────────────────────────────────────────────────────────
export const api = {
  suppliers: {
    list: () => get<Supplier[]>("/suppliers"),
    create: (data: Omit<Supplier, "id">) =>
      post<Supplier>("/suppliers", data),
    update: (code: string, data: Partial<Omit<Supplier, "id" | "code">>) =>
      fetch(`${BASE}/suppliers/${code}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(async (r) => {
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? r.statusText); }
        return r.json() as Promise<Supplier>;
      }),
  },
  customers: {
    list: (search?: string) =>
      get<Customer[]>("/customers" + (search ? `?q=${encodeURIComponent(search)}` : "")),
    create: (data: Omit<Customer, "id" | "ku_nr">) =>
      post<Customer>("/customers", data),
    update: (code: string, data: Partial<Omit<Customer, "id" | "code" | "ku_nr">>) =>
      fetch(`${BASE}/customers/${code}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(async (r) => {
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? r.statusText); }
        return r.json() as Promise<Customer>;
      }),
  },
  transactions: {
    list: (supplierCode: string, from: string, to: string) =>
      get<Transaction[]>(`/suppliers/${supplierCode}/transactions?from=${from}&to=${to}`),
    create: (supplierCode: string, data: TransactionUpdate) =>
      post<Transaction>(`/suppliers/${supplierCode}/transactions`, data),
    update: (id: number, data: TransactionUpdate) =>
      fetch(`${BASE}/suppliers/transactions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(async (r) => { if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? r.statusText); } return r.json() as Promise<Transaction>; }),
    delete: (id: number) =>
      fetch(`${BASE}/suppliers/transactions/${id}`, { method: "DELETE" })
        .then((r) => { if (!r.ok) throw new Error(`${r.status}`); }),
    parsePdf: (supplierCode: string, file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return fetch(`${BASE}/suppliers/${supplierCode}/transactions/parse-pdf`, {
        method: "POST", body: fd,
      }).then(async (r) => {
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? r.statusText); }
        return r.json() as Promise<PdfEntry[]>;
      });
    },
  },
  commission: {
    statements: () => get<CommissionStatement[]>("/commission/statements"),
    create: (body: { supplier_code: string; period_from: string; period_to: string }) =>
      post<CommissionStatement>("/commission/statements", body),
    issue: (id: number) =>
      post<CommissionStatement>(`/commission/statements/${id}/issue`, {}),
    pdfUrl: (id: number) => `${BASE}/commission/statements/${id}/pdf`,
    invoiceSummary: (supplierCode: string, from: string, to: string) =>
      get<InvoiceSummary>(`/commission/${supplierCode}/invoice-summary?period_from=${from}&period_to=${to}`),
    invoicePdfUrl: (supplierCode: string) => `${BASE}/commission/${supplierCode}/invoice-pdf`,
    ubwExportUrl: (supplierCode: string) => `${BASE}/commission/${supplierCode}/ubw-export`,
  },
};

export interface InvoiceSummary {
  supplier_code: string;
  supplier_name: string;
  period_from: string;
  period_to: string;
  next_pr_seq: number;
  totals: { currency: string; total_amount: number; provision_amount: number }[];
}
