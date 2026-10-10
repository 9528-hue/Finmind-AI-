/**
 * FINMIND AI — API Client
 * All requests go through Next.js at /api/* which proxies to FastAPI.
 * This keeps the app single-origin and avoids all CORS issues.
 */

// All API calls use the /api prefix which Next.js rewrites → FastAPI backend
const BASE = "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────
export async function login(email: string, password: string) {
  return request<{ access_token: string; token_type: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email: string, full_name: string, password: string) {
  return request<{ id: string; email: string; full_name: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, full_name, password }),
  });
}

export async function getCurrentUser(token: string) {
  return request<{ id: string; email: string; full_name: string }>("/auth/me", {}, token);
}

// ── Analytics ────────────────────────────────────────────────
export interface Analytics {
  total_balance: number;
  total_income: number;
  total_revenue: number | null;
  total_expenses: number;
  net_cash_flow: number;
  currency: string | null;
  transaction_count: number;
  flagged_count: number;
  avg_risk_score: number;
  savings_rate: number | null;
  average_transaction_amount: number;
  largest_transaction_amount: number;
  high_risk_count: number;
  medium_risk_count: number;
  category_breakdown: { category: string; amount: number; count: number; percentage: number }[];
  monthly_trends: { month: string; income: number; expenses: number; net: number }[];
  cash_flow_trends: { month: string; income: number; expenses: number; net: number }[];
  top_merchants: { merchant: string; amount: number; count: number }[];
  risk_distribution: { level: string; count: number; percentage: number }[];
}

export async function getAnalytics(
  token: string,
  currency?: string,
  dateFrom?: string,
  dateTo?: string,
  interval: "day" | "week" | "month" = "month"
): Promise<Analytics> {
  const params = new URLSearchParams({ interval });
  if (currency) params.set("currency", currency);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const qs = `?${params.toString()}`;
  return request<Analytics>(`/analytics/${qs}`, {}, token);
}

// ── Transactions ─────────────────────────────────────────────
export interface Transaction {
  id: string;
  user_id: string;
  account_id: string | null;
  amount: number;
  currency: string;
  merchant: string;
  category: string;
  transaction_type: string;
  payment_method: string | null;
  location: string | null;
  status: string;
  description: string | null;
  risk_score: number;
  risk_level: string;
  is_flagged: boolean;
  risk_signals: string | null;
  timestamp: string;
  created_at: string;
}

export interface TransactionFilters {
  search?: string;
  category?: string;
  transaction_type?: "credit" | "debit" | "";
  currency?: string;
  date_from?: string;
  date_to?: string;
  amount_min?: string;
  amount_max?: string;
  risk_score_min?: string;
  risk_score_max?: string;
  risk_level?: "low" | "medium" | "high" | "";
  transaction_status?: string;
  flagged_only?: boolean;
}

function transactionQuery(filters: TransactionFilters, skip: number, limit: number) {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (filters.search?.trim()) params.set("search", filters.search.trim());
  if (filters.category?.trim()) params.set("category", filters.category.trim());
  if (filters.transaction_type) params.set("transaction_type", filters.transaction_type);
  if (filters.currency) params.set("currency", filters.currency);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.amount_min) params.set("amount_min", filters.amount_min);
  if (filters.amount_max) params.set("amount_max", filters.amount_max);
  if (filters.risk_score_min) params.set("risk_score_min", filters.risk_score_min);
  if (filters.risk_score_max) params.set("risk_score_max", filters.risk_score_max);
  if (filters.risk_level) params.set("risk_level", filters.risk_level);
  if (filters.transaction_status) params.set("transaction_status", filters.transaction_status);
  if (filters.flagged_only) params.set("flagged_only", "true");
  return params;
}

export async function getTransactionsPage(
  token: string,
  filters: TransactionFilters = {},
  skip = 0,
  limit = 50
): Promise<{ items: Transaction[]; total: number }> {
  const params = transactionQuery(filters, skip, limit);
  return fetch(`${BASE}/transactions/?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then(async (res) => {
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail || body.error || detail;
      } catch {}
      throw new ApiError(res.status, detail);
    }
    return {
      items: (await res.json()) as Transaction[],
      total: Number(res.headers.get("X-Total-Count") || "0"),
    };
  });
}

export async function getTransactions(
  token: string,
  filters: TransactionFilters = {}
): Promise<Transaction[]> {
  const { items } = await getTransactionsPage(token, filters, 0, 200);
  return items;
}

export async function updateTransactionCategory(
  token: string,
  transactionId: string,
  category: string
): Promise<Transaction> {
  return request<Transaction>(`/transactions/${encodeURIComponent(transactionId)}`, {
    method: "PATCH",
    body: JSON.stringify({ category }),
  }, token);
}

export interface TransactionUploadResult {
  success: boolean;
  filename: string;
  total_rows: number;
  valid_rows: number;
  imported: number;
  duplicates: number;
  skipped: number;
  detected_currencies: string[];
  date_range: { start: string; end: string } | null;
  flagged: number;
  high_risk: number;
  alerts_created: number;
}

export interface TransactionUploadPreview {
  success: boolean;
  filename: string;
  total_rows: number;
  valid_rows: number;
  imported: number;
  duplicates: number;
  skipped: number;
  detected_currencies: string[];
  date_range: { start: string; end: string } | null;
  preview_rows: Array<{
    row: number;
    date: string;
    merchant: string;
    amount: number;
    currency: string;
    transaction_type: string;
    category: string;
  }>;
  skipped_details: Array<{ row: number; reason: string }>;
}

async function submitTransactionFile<T>(
  token: string,
  file: File,
  previewOnly: boolean
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);

  const query = previewOnly ? "?preview_only=true" : "";
  const res = await fetch(`${BASE}/transactions/upload${query}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

export async function previewTransactions(
  token: string,
  file: File
): Promise<TransactionUploadPreview> {
  return submitTransactionFile<TransactionUploadPreview>(token, file, true);
}

export async function uploadTransactions(
  token: string,
  file: File
): Promise<TransactionUploadResult> {
  return submitTransactionFile<TransactionUploadResult>(token, file, false);
}

export interface TransactionStats {
  currency: string | null;
  total_count: number;
  total_amount: number;
  total_income: number;
  total_expenses: number;
  flagged_count: number;
  high_risk_count: number;
  avg_risk_score: number;
}

export async function getTransactionStats(token: string): Promise<TransactionStats> {
  return request<TransactionStats>("/transactions/stats", {}, token);
}

// ── Alerts ───────────────────────────────────────────────────
export interface Alert {
  id: string;
  user_id: string;
  transaction_id: string | null;
  title: string;
  description: string;
  severity: string;
  is_read: boolean;
  created_at: string;
}

export async function getAlerts(token: string): Promise<Alert[]> {
  return request<Alert[]>("/alerts/", {}, token);
}

export async function markAlertRead(token: string, alertId: string): Promise<Alert> {
  return request<Alert>(`/alerts/${alertId}/read`, { method: "PATCH" }, token);
}

// ── AI ───────────────────────────────────────────────────────
export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export async function aiChat(
  token: string,
  message: string,
  history: ChatTurn[] = []
): Promise<{ reply: string; ai_unavailable: boolean }> {
  return request<{ reply: string; ai_unavailable: boolean }>("/ai/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  }, token);
}

// ── Reports ──────────────────────────────────────────────────
/**
 * Downloads a file from the API via the Next.js proxy.
 * Uses the auth token and triggers a browser download.
 */
async function downloadFile(path: string, token: string, filename: string) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, `Download failed: HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function reportQuery(flaggedOnly: boolean, filters: TransactionFilters) {
  const params = new URLSearchParams();
  if (flaggedOnly) params.set("flagged_only", "true");
  if (filters.search?.trim()) params.set("search", filters.search.trim());
  if (filters.category?.trim()) params.set("category", filters.category.trim());
  if (filters.transaction_type) params.set("transaction_type", filters.transaction_type);
  if (filters.currency) params.set("currency", filters.currency);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.amount_min) params.set("amount_min", filters.amount_min);
  if (filters.amount_max) params.set("amount_max", filters.amount_max);
  if (filters.risk_score_min) params.set("risk_score_min", filters.risk_score_min);
  if (filters.risk_score_max) params.set("risk_score_max", filters.risk_score_max);
  if (filters.risk_level) params.set("risk_level", filters.risk_level);
  if (filters.transaction_status) params.set("transaction_status", filters.transaction_status);
  if (filters.flagged_only) params.set("flagged_only", "true");
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function downloadTransactionsCsv(
  token: string,
  flaggedOnly = false,
  filters: TransactionFilters = {}
) {
  const qs = reportQuery(flaggedOnly, filters);
  const today = new Date().toISOString().slice(0, 10);
  const suffix = flaggedOnly ? "_flagged" : "";
  await downloadFile(`/reports/transactions/csv${qs}`, token, `finmind_transactions${suffix}_${today}.csv`);
}

export async function downloadSummaryPdf(
  token: string,
  flaggedOnly = false,
  filters: TransactionFilters = {}
) {
  const qs = reportQuery(flaggedOnly, filters);
  const today = new Date().toISOString().slice(0, 10);
  const suffix = flaggedOnly ? "_flagged" : "";
  await downloadFile(`/reports/summary/pdf${qs}`, token, `finmind_report${suffix}_${today}.pdf`);
}

export async function downloadAnalyticsCsv(
  token: string,
  reportType: "monthly" | "category" | "merchant" | "risk" | "fraud" | "alerts",
  filters: TransactionFilters = {}
) {
  const params = new URLSearchParams({ report_type: reportType });
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.currency) params.set("currency", filters.currency);
  if (filters.category) params.set("category", filters.category);
  if (filters.transaction_type) params.set("transaction_type", filters.transaction_type);
  if (filters.search) params.set("search", filters.search);
  if (filters.risk_level) params.set("risk_level", filters.risk_level);
  if (filters.amount_min) params.set("amount_min", filters.amount_min);
  if (filters.amount_max) params.set("amount_max", filters.amount_max);
  if (filters.risk_score_min) params.set("risk_score_min", filters.risk_score_min);
  if (filters.risk_score_max) params.set("risk_score_max", filters.risk_score_max);
  if (filters.transaction_status) params.set("transaction_status", filters.transaction_status);
  if (filters.flagged_only) params.set("flagged_only", "true");
  const today = new Date().toISOString().slice(0, 10);
  await downloadFile(
    `/reports/analytics/csv?${params.toString()}`,
    token,
    `finmind_${reportType}_${today}.csv`
  );
}

export async function downloadSecurityPdf(token: string, filters: TransactionFilters = {}) {
  const params = new URLSearchParams();
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.currency) params.set("currency", filters.currency);
  if (filters.category) params.set("category", filters.category);
  if (filters.search) params.set("search", filters.search);
  if (filters.risk_level) params.set("risk_level", filters.risk_level);
  if (filters.transaction_type) params.set("transaction_type", filters.transaction_type);
  if (filters.amount_min) params.set("amount_min", filters.amount_min);
  if (filters.amount_max) params.set("amount_max", filters.amount_max);
  if (filters.risk_score_min) params.set("risk_score_min", filters.risk_score_min);
  if (filters.risk_score_max) params.set("risk_score_max", filters.risk_score_max);
  if (filters.transaction_status) params.set("transaction_status", filters.transaction_status);
  if (filters.flagged_only) params.set("flagged_only", "true");
  const query = params.toString();
  const today = new Date().toISOString().slice(0, 10);
  await downloadFile(`/reports/security/pdf${query ? `?${query}` : ""}`, token, `finmind_security_${today}.pdf`);
}
