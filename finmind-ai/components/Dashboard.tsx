"use client";

import { useEffect, useState, useCallback, useRef, type ChangeEvent } from "react";
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Bell, Bot,
  BrainCircuit, ChevronDown, CircleDollarSign,
  FileCheck2, FileDown, Gauge, LogOut, Paperclip, RefreshCw, Upload,
  Send, ShieldAlert, Sparkles, TrendingUp, Download,
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getAnalytics, getTransactions, getTransactionsPage, getAlerts, aiChat, markAlertRead,
  downloadTransactionsCsv, downloadSummaryPdf, downloadAnalyticsCsv, downloadSecurityPdf, previewTransactions, uploadTransactions, updateTransactionCategory,
  type Analytics, type Transaction, type Alert, type TransactionFilters, type TransactionUploadPreview, type ChatTurn,
} from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  Technology: "#0f766e",
  "Food & Dining": "#14b8a6",
  Travel: "#f59e0b",
  Operations: "#6366f1",
  Marketing: "#ec4899",
  Finance: "#06b6d4",
  People: "#84cc16",
  Cryptocurrency: "#f97316",
  "Wire Transfer": "#ef4444",
  "Money Transfer": "#8b5cf6",
};

const CATEGORY_OPTIONS = [
  "Salary", "Revenue", "Business Income", "Freelance Income", "Investment",
  "Shopping", "Food", "Groceries", "Transportation", "Fuel", "Rent",
  "Utilities", "Bills", "Healthcare", "Education", "Entertainment", "Travel",
  "Insurance", "Loan", "EMI", "Subscription", "Transfer", "Cash Withdrawal",
  "ATM", "Cryptocurrency", "Gambling", "Other",
];

const chartTooltip = {
  contentStyle: {
    borderRadius: 12,
    border: "1px solid #e5e7eb",
    boxShadow: "0 8px 30px rgba(15,23,42,0.08)",
    fontSize: 12,
  },
};

type ChatMessage = { role: "user" | "assistant"; text: string; aiUnavailable?: boolean };
type NavSection = "Overview" | "Transactions" | "Risk Center" | "AI Assistant" | "Reports";
type DashboardPeriod = "today" | "last7" | "last30" | "thisMonth" | "lastMonth" | "thisYear" | "custom";
type TrendInterval = "day" | "week" | "month";

interface DateRange {
  dateFrom: string;
  dateTo: string;
}

function toDateInputValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function resolveDashboardPeriod(period: DashboardPeriod, customFrom = "", customTo = ""): DateRange {
  const today = new Date();
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  let start = new Date(end);
  if (period === "last7") start.setDate(start.getDate() - 6);
  else if (period === "last30") start.setDate(start.getDate() - 29);
  else if (period === "thisMonth") start = new Date(end.getFullYear(), end.getMonth(), 1);
  else if (period === "lastMonth") {
    start = new Date(end.getFullYear(), end.getMonth() - 1, 1);
    end.setDate(0);
  } else if (period === "thisYear") start = new Date(end.getFullYear(), 0, 1);
  else if (period === "custom") return { dateFrom: customFrom, dateTo: customTo };
  return { dateFrom: toDateInputValue(start), dateTo: toDateInputValue(end) };
}

function fmt(n: number, currency = "") {
  const prefix = currency === "INR" ? "₹" : currency === "USD" ? "$" : currency === "EUR" ? "€" : currency === "GBP" ? "£" : currency ? `${currency} ` : "";
  if (n >= 1_000_000) return `${prefix}${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${prefix}${(n / 1_000).toFixed(1)}k`;
  return `${prefix}${n.toFixed(2)}`;
}

function currencySymbol(currency: string) {
  return ({ INR: "₹", USD: "$", EUR: "€", GBP: "£" } as Record<string, string>)[currency] || `${currency} `;
}

/** Format an amount with its transaction currency. */
function formatAmount(amount: number, currency: string, type: string) {
  const SYMBOLS: Record<string, string> = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };
  const sym = SYMBOLS[currency] || currency + " ";
  const sign = type === "credit" ? "+" : "-";
  return `${sign}${sym}${amount.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function RiskBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    high: "bg-rose-100 text-rose-700 border-rose-200",
    medium: "bg-amber-100 text-amber-700 border-amber-200",
    low: "bg-teal-100 text-teal-700 border-teal-200",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${styles[level] || styles.low}`}>
      {level}
    </span>
  );
}

function MetricCard({ label, value, sub, icon: Icon, accent = "teal", positive = true }: {
  label: string; value: string; sub?: string; icon: typeof Activity;
  accent?: "teal" | "amber" | "rose" | "blue"; positive?: boolean;
}) {
  const accents = {
    teal: "bg-teal-50 text-teal-700",
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-rose-50 text-rose-700",
    blue: "bg-sky-50 text-sky-700",
  };
  return (
    <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-slate-500">{label}</p>
            <p className="mt-2 text-2xl font-bold tracking-tight text-slate-950">{value}</p>
          </div>
          <div className={`rounded-xl p-2.5 ${accents[accent]}`}><Icon className="size-4" /></div>
        </div>
        {sub && (
          <div className={`mt-3 flex items-center gap-1 text-xs font-medium ${positive ? "text-teal-700" : "text-rose-600"}`}>
            {positive ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
            {sub}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-slate-200 ${className}`} />;
}

interface Props {
  token: string;
  userName: string;
  onLogout: () => void;
}

export default function Dashboard({ token, userName, onLogout }: Props) {
  const [activeNav, setActiveNav] = useState<NavSection>("Overview");
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [dashboardPeriod, setDashboardPeriod] = useState<DashboardPeriod>("thisMonth");
  const [customDateFrom, setCustomDateFrom] = useState("");
  const [customDateTo, setCustomDateTo] = useState("");
  const [dashboardDateRange, setDashboardDateRange] = useState<DateRange>(() => resolveDashboardPeriod("thisMonth"));
  const [trendInterval, setTrendInterval] = useState<TrendInterval>("day");
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [visibleTransactions, setVisibleTransactions] = useState<Transaction[]>([]);
  const [transactionPage, setTransactionPage] = useState(0);
  const [transactionTotal, setTransactionTotal] = useState(0);
  const [filterDraft, setFilterDraft] = useState<TransactionFilters>({});
  const [activeFilters, setActiveFilters] = useState<TransactionFilters>({});
  const [filterLoading, setFilterLoading] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [activeCurrency, setActiveCurrency] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [pendingUploadFile, setPendingUploadFile] = useState<File | null>(null);
  const [uploadPreview, setUploadPreview] = useState<TransactionUploadPreview | null>(null);
  const [updatingCategoryId, setUpdatingCategoryId] = useState<string | null>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  // AI Chat
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    { role: "assistant", text: `Hi ${userName}! I can help you understand your transaction history, spending, income, and risk alerts. Ask a question in your own words, and you can follow up naturally.` },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatMessages, chatLoading]);

  const startNewChat = () => {
    setChatMessages([{
      role: "assistant",
      text: `Hi ${userName}! I can help you understand your transaction history, spending, income, and risk alerts. Ask a question in your own words, and you can follow up naturally.`,
    }]);
    setChatInput("");
  };

  // Reports
  const [reportLoading, setReportLoading] = useState<string | null>(null);
  const [reportError, setReportError] = useState("");

  const loadData = useCallback(async (
    requestedCurrency?: string,
    requestedDateRange: DateRange = dashboardDateRange,
    requestedFilters: TransactionFilters = activeFilters,
    requestedPage = transactionPage
  ) => {
    setLoading(true);
    setError("");
    try {
      const [t, al, transactionResult] = await Promise.all([
        getTransactions(token),
        getAlerts(token),
        getTransactionsPage(token, requestedFilters, requestedPage * 50, 50),
      ]);
      const currencies = Array.from(new Set(t.map((transaction) => transaction.currency.toUpperCase()))).sort();
      const selectedCurrency = requestedCurrency && currencies.includes(requestedCurrency)
        ? requestedCurrency
        : activeCurrency && currencies.includes(activeCurrency)
          ? activeCurrency
          : currencies.includes("INR")
            ? "INR"
            : currencies[0] || "";
      const a = await getAnalytics(
        token,
        selectedCurrency || undefined,
        requestedDateRange.dateFrom || undefined,
        requestedDateRange.dateTo || undefined,
        trendInterval
      );
      setAnalytics(a);
      setTransactions(t);
      setVisibleTransactions(transactionResult.items);
      setTransactionTotal(transactionResult.total);
      setTransactionPage(requestedPage);
      setAlerts(al);
      setActiveCurrency(a.currency || selectedCurrency);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, [token, activeCurrency, activeFilters, transactionPage, dashboardDateRange, trendInterval]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadData(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadMessage("");
    setUploadError("");
    setUploadPreview(null);
    setPendingUploadFile(null);
    try {
      const preview = await previewTransactions(token, file);
      setUploadPreview(preview);
      setPendingUploadFile(file);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Could not validate the uploaded statement.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const handleConfirmUpload = async () => {
    if (!pendingUploadFile) return;
    setUploading(true);
    setUploadMessage("");
    setUploadError("");
    try {
      const result = await uploadTransactions(token, pendingUploadFile);
      setUploadMessage(
        `${result.filename}: ${result.total_rows} rows, ${result.valid_rows} valid, ` +
        `${result.imported} imported, ` +
        `${result.duplicates} duplicates and ${result.skipped} skipped. ` +
        `Currency: ${result.detected_currencies.join(", ") || "unknown"}. ` +
        `Dates: ${result.date_range ? `${result.date_range.start} to ${result.date_range.end}` : "none"}.`
      );
      setUploadPreview(null);
      setPendingUploadFile(null);
      const importedDateRange = result.date_range
        ? { dateFrom: result.date_range.start, dateTo: result.date_range.end }
        : dashboardDateRange;
      if (result.date_range) {
        setDashboardPeriod("custom");
        setCustomDateFrom(result.date_range.start);
        setCustomDateTo(result.date_range.end);
        setDashboardDateRange(importedDateRange);
      }
      setFilterDraft({});
      setActiveFilters({});
      setTransactionPage(0);
      await loadData(
        result.detected_currencies[0],
        importedDateRange,
        {},
        0
      );
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Transaction upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const handleViewStatementPeriod = async (preview: TransactionUploadPreview) => {
    if (!preview.date_range) return;

    const dateRange = {
      dateFrom: preview.date_range.start,
      dateTo: preview.date_range.end,
    };
    const statementFilters: TransactionFilters = {
      date_from: dateRange.dateFrom,
      date_to: dateRange.dateTo,
    };

    setDashboardPeriod("custom");
    setCustomDateFrom(dateRange.dateFrom);
    setCustomDateTo(dateRange.dateTo);
    setDashboardDateRange(dateRange);
    setFilterDraft(statementFilters);
    setActiveFilters(statementFilters);
    setTransactionPage(0);
    setActiveNav("Overview");
    setUploadPreview(null);
    setPendingUploadFile(null);

    await loadData(
      preview.detected_currencies[0],
      dateRange,
      statementFilters,
      0
    );
  };

  const handleDashboardPeriodChange = (period: DashboardPeriod) => {
    setDashboardPeriod(period);
    if (period !== "custom") {
      setDashboardDateRange(resolveDashboardPeriod(period));
    }
  };

  const handleApplyCustomDashboardPeriod = () => {
    if (!customDateFrom || !customDateTo) {
      setError("Choose both a start and end date for the custom dashboard period.");
      return;
    }
    if (customDateFrom > customDateTo) {
      setError("Start date must be on or before end date.");
      return;
    }
    setError("");
    setDashboardDateRange(resolveDashboardPeriod("custom", customDateFrom, customDateTo));
  };

  const sendMessage = async () => {
    const msg = chatInput.trim();
    if (!msg || chatLoading) return;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", text: msg }]);
    setChatLoading(true);
    try {
      const history: ChatTurn[] = chatMessages
        .slice(-12)
        .map(({ role, text }) => ({ role, content: text }));
      const res = await aiChat(token, msg, history);
      setChatMessages((prev) => [...prev, {
        role: "assistant",
        text: res.reply,
        aiUnavailable: res.ai_unavailable,
      }]);
    } catch {
      setChatMessages((prev) => [...prev, {
        role: "assistant",
        text: "I'm having trouble connecting. Please try again.",
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleMarkRead = async (alertId: string) => {
    try {
      await markAlertRead(token, alertId);
      setAlerts((prev) => prev.map((a) => a.id === alertId ? { ...a, is_read: true } : a));
    } catch {}
  };

  const handleCategoryChange = async (transactionId: string, category: string) => {
    setUpdatingCategoryId(transactionId);
    setError("");
    try {
      await updateTransactionCategory(token, transactionId, category);
      await loadData(activeCurrency);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update transaction category.");
    } finally {
      setUpdatingCategoryId(null);
    }
  };

  const handleApplyFilters = async () => {
    if (filterDraft.date_from && filterDraft.date_to && filterDraft.date_from > filterDraft.date_to) {
      setError("Start date must be on or before end date.");
      return;
    }
    if (filterDraft.amount_min && filterDraft.amount_max && Number(filterDraft.amount_min) > Number(filterDraft.amount_max)) {
      setError("Minimum amount must not exceed maximum amount.");
      return;
    }
    if (filterDraft.risk_score_min && filterDraft.risk_score_max && Number(filterDraft.risk_score_min) > Number(filterDraft.risk_score_max)) {
      setError("Minimum risk score must not exceed maximum risk score.");
      return;
    }
    setFilterLoading(true);
    setError("");
    const filters = { ...filterDraft };
    setActiveFilters(filters);
    setTransactionPage(0);
    try {
      const result = await getTransactionsPage(token, filters, 0, 50);
      setVisibleTransactions(result.items);
      setTransactionTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not filter transactions.");
    } finally {
      setFilterLoading(false);
    }
  };

  const handleClearFilters = async () => {
    const cleared: TransactionFilters = {};
    setFilterDraft(cleared);
    setActiveFilters(cleared);
    setTransactionPage(0);
    setFilterLoading(true);
    setError("");
    try {
      const result = await getTransactionsPage(token, cleared, 0, 50);
      setVisibleTransactions(result.items);
      setTransactionTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear transaction filters.");
    } finally {
      setFilterLoading(false);
    }
  };

  const handleTransactionPageChange = async (page: number) => {
    if (page < 0 || page * 50 >= transactionTotal || filterLoading) return;
    setFilterLoading(true);
    setError("");
    try {
      const result = await getTransactionsPage(token, activeFilters, page * 50, 50);
      setVisibleTransactions(result.items);
      setTransactionTotal(result.total);
      setTransactionPage(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load transaction page.");
    } finally {
      setFilterLoading(false);
    }
  };

  const handleDownload = async (type: "csv" | "csv-flagged" | "pdf" | "pdf-flagged" | "monthly" | "category" | "merchant" | "risk" | "fraud" | "alerts" | "security-pdf") => {
    setReportLoading(type);
    setReportError("");
    const reportFilters: TransactionFilters = {
      ...activeFilters,
      date_from: activeFilters.date_from || dashboardDateRange.dateFrom,
      date_to: activeFilters.date_to || dashboardDateRange.dateTo,
      currency: activeFilters.currency || activeCurrency || undefined,
    };
    try {
      if (type === "csv") await downloadTransactionsCsv(token, false, reportFilters);
      else if (type === "csv-flagged") await downloadTransactionsCsv(token, true, reportFilters);
      else if (type === "pdf") await downloadSummaryPdf(token, false, reportFilters);
      else if (type === "pdf-flagged") await downloadSummaryPdf(token, true, reportFilters);
      else if (type === "security-pdf") await downloadSecurityPdf(token, reportFilters);
      else await downloadAnalyticsCsv(token, type, reportFilters);
    } catch {
      setReportError("Download failed. Make sure the backend is running.");
    } finally {
      setReportLoading(null);
    }
  };

  const flaggedTxns = transactions.filter((t) => t.is_flagged);
  const unreadAlerts = alerts.filter((a) => !a.is_read);

  const navItems: { label: NavSection; icon: typeof Gauge; count?: number }[] = [
    { label: "Overview", icon: Gauge },
    { label: "Transactions", icon: Activity, count: transactions.length },
    { label: "Risk Center", icon: ShieldAlert, count: flaggedTxns.length },
    { label: "AI Assistant", icon: BrainCircuit },
    { label: "Reports", icon: FileDown },
  ];

  return (
    <main className="min-h-screen bg-[#f7f9fb] text-slate-900">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[240px] border-r border-slate-200 bg-white px-4 py-5 lg:flex lg:flex-col">
        <div className="flex items-center gap-3 px-2">
          <div className="flex size-9 items-center justify-center rounded-xl bg-slate-950 text-white">
            <BrainCircuit className="size-5" />
          </div>
          <div>
            <p className="text-[15px] font-bold tracking-tight text-slate-950">
              FinMind <span className="text-teal-600">AI</span>
            </p>
            <p className="text-[10px] font-medium uppercase tracking-[0.15em] text-slate-400">Security Platform</p>
          </div>
        </div>

        <div className="mt-8 px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Navigation</div>
        <nav className="mt-2 space-y-1">
          {navItems.map(({ label, icon: Icon, count }) => (
            <button
              key={label}
              onClick={() => setActiveNav(label)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-all ${
                activeNav === label
                  ? "bg-teal-50 font-semibold text-teal-800"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <span className="flex items-center gap-3"><Icon className="size-4" />{label}</span>
              {count !== undefined && count > 0 && (
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  activeNav === label ? "bg-white text-teal-700" : "bg-slate-100 text-slate-500"
                }`}>{count}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="mt-auto">
          {/* AI promo box */}
          <div className="mb-4 rounded-xl bg-slate-950 p-4 text-white">
            <Sparkles className="mb-2 size-4 text-teal-300" />
            <p className="text-sm font-semibold">Ask FinGuard AI</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">Natural language questions about your finances.</p>
            <Button onClick={() => setActiveNav("AI Assistant")} size="sm" className="mt-3 w-full bg-teal-500 text-slate-950 hover:bg-teal-400">
              Open Assistant
            </Button>
          </div>
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-slate-500 hover:bg-slate-50 hover:text-slate-900"
          >
            <LogOut className="size-4" />Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-[240px]">
        {/* Header */}
        <header className="sticky top-0 z-10 flex h-[68px] items-center justify-between border-b border-slate-200 bg-[#f7f9fb]/90 px-5 backdrop-blur-md sm:px-8">
          <div>
            <p className="text-xs font-medium text-slate-400">{new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</p>
            <h1 className="mt-0.5 text-lg font-semibold tracking-tight text-slate-950">Good morning, {userName} 👋</h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-500 sm:flex">
              <span className="size-2 rounded-full bg-teal-500" />Account data secured
            </div>
            <input
              ref={uploadInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={handleUpload}
            />
            <Button
              variant="outline"
              onClick={() => uploadInputRef.current?.click()}
              disabled={uploading}
              className="bg-white"
            >
              <Upload className="size-4" />
              {uploading ? "Uploading…" : "Upload statement"}
            </Button>
            {Array.from(new Set(transactions.map((transaction) => transaction.currency.toUpperCase()))).length > 1 && (
              <select
                aria-label="Analytics currency"
                value={activeCurrency}
                onChange={(event) => { void loadData(event.target.value); }}
                className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700"
              >
                {Array.from(new Set(transactions.map((transaction) => transaction.currency.toUpperCase()))).sort().map((currency) => (
                  <option key={currency} value={currency}>{currency}</option>
                ))}
              </select>
            )}
            <div className="relative">
              <Button variant="outline" size="icon" onClick={() => setActiveNav("Risk Center")} className="bg-white">
                <Bell className="size-4" />
                {unreadAlerts.length > 0 && (
                  <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white">
                    {unreadAlerts.length}
                  </span>
                )}
              </Button>
            </div>
            <Button variant="outline" size="icon" onClick={() => { void loadData(); }} className="bg-white" title="Refresh data">
              <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </header>

        <div className="mx-auto max-w-[1450px] space-y-8 px-5 py-7 sm:px-8">
          {uploadMessage && (
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800" role="status">
              <span className="flex-1">Statement imported and dashboard updated: {uploadMessage} Reports are generated when you download them.</span>
              <Button variant="outline" size="sm" onClick={() => setActiveNav("Overview")}>View Dashboard</Button>
              <Button variant="outline" size="sm" onClick={() => setActiveNav("Risk Center")}>View Risk Center</Button>
              <Button
                variant="outline"
                size="sm"
                disabled={reportLoading !== null}
                onClick={() => { void handleDownload("pdf"); }}
              >
                {reportLoading === "pdf" ? "Generating PDF…" : "Download PDF report"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={reportLoading !== null}
                onClick={() => { void handleDownload("csv"); }}
              >
                {reportLoading === "csv" ? "Exporting CSV…" : "Export transactions CSV"}
              </Button>
            </div>
          )}
          {uploadPreview && (
            <Card className="border border-sky-200 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
              <CardHeader>
                <CardTitle>Review statement before importing</CardTitle>
                <CardDescription>{uploadPreview.filename} · Import begins only after you confirm.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {uploadPreview.imported === 0 &&
                  uploadPreview.duplicates === uploadPreview.valid_rows &&
                  uploadPreview.date_range && (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-sky-200 bg-sky-50 p-3">
                      <p className="text-sm text-sky-900">
                        These valid transactions are already in your account. No duplicate import is needed.
                      </p>
                      <Button
                        variant="outline"
                        onClick={() => { void handleViewStatementPeriod(uploadPreview); }}
                        className="border-sky-300 bg-white text-sky-900 hover:bg-sky-100"
                      >
                        View existing transactions and cash flow
                      </Button>
                    </div>
                  )}
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  {[
                    { label: "Rows", value: uploadPreview.total_rows },
                    { label: "Valid", value: uploadPreview.valid_rows },
                    { label: "Ready to import", value: uploadPreview.imported },
                    { label: "Duplicates", value: uploadPreview.duplicates },
                    { label: "Skipped", value: uploadPreview.skipped },
                  ].map(({ label, value }) => (
                    <div key={label} className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs text-slate-500">{label}</p>
                      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-slate-600">
                  Currency: {uploadPreview.detected_currencies.join(", ") || "none detected"} · Date range:{" "}
                  {uploadPreview.date_range
                    ? `${uploadPreview.date_range.start} to ${uploadPreview.date_range.end}`
                    : "no valid dates"}
                </p>
                {uploadPreview.preview_rows.length > 0 && (
                  <div className="max-h-64 overflow-auto rounded-lg border border-slate-200">
                    <table className="w-full min-w-[650px] text-left text-xs">
                      <thead className="sticky top-0 bg-slate-50 text-slate-500">
                        <tr>
                          <th className="px-3 py-2">Row</th>
                          <th className="px-3 py-2">Date</th>
                          <th className="px-3 py-2">Merchant</th>
                          <th className="px-3 py-2">Type</th>
                          <th className="px-3 py-2 text-right">Amount</th>
                          <th className="px-3 py-2">Category</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {uploadPreview.preview_rows.map((row) => (
                          <tr key={`${row.row}-${row.date}-${row.merchant}`}>
                            <td className="px-3 py-2 text-slate-500">{row.row}</td>
                            <td className="px-3 py-2">{new Date(row.date).toLocaleDateString()}</td>
                            <td className="px-3 py-2 font-medium">{row.merchant}</td>
                            <td className="px-3 py-2 capitalize">{row.transaction_type}</td>
                            <td className="px-3 py-2 text-right">{formatAmount(row.amount, row.currency, row.transaction_type)}</td>
                            <td className="px-3 py-2">{row.category}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {uploadPreview.skipped_details.length > 0 && (
                  <details className="text-sm text-slate-600">
                    <summary className="cursor-pointer font-medium">Skipped-row details (first {uploadPreview.skipped_details.length})</summary>
                    <ul className="mt-2 list-inside list-disc space-y-1">
                      {uploadPreview.skipped_details.map(({ row, reason }) => <li key={row}>Row {row}: {reason}</li>)}
                    </ul>
                  </details>
                )}
                <div className="flex flex-wrap justify-end gap-2">
                  <Button
                    variant="outline"
                    disabled={uploading}
                    onClick={() => { setUploadPreview(null); setPendingUploadFile(null); }}
                  >
                    Cancel
                  </Button>
                  <Button
                    disabled={uploading || uploadPreview.imported === 0}
                    onClick={() => { void handleConfirmUpload(); }}
                    className="bg-teal-700 text-white hover:bg-teal-800"
                  >
                    {uploading ? "Importing…" : `Import ${uploadPreview.imported} transactions`}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
          {uploadError && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
              Statement upload failed: {uploadError}
            </div>
          )}
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              ⚠️ {error} — <button onClick={() => { void loadData(); }} className="font-semibold underline">Retry</button>
            </div>
          )}

          {/* ── OVERVIEW ─────────────────────────────────────── */}
          {(activeNav === "Overview") && (
            <>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">Executive overview</p>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Your finances at a glance</h2>
                <p className="mt-1 text-sm text-slate-500">AI-powered insights across your financial activity — live data from your account.</p>
              </div>

              <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                <CardContent className="flex flex-wrap items-end gap-3 p-4">
                  <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
                    Dashboard period
                    <select
                      aria-label="Dashboard period"
                      value={dashboardPeriod}
                      onChange={(event) => handleDashboardPeriodChange(event.target.value as DashboardPeriod)}
                      className="h-10 min-w-44 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700"
                    >
                      <option value="today">Today</option>
                      <option value="last7">Last 7 days</option>
                      <option value="last30">Last 30 days</option>
                      <option value="thisMonth">This month</option>
                      <option value="lastMonth">Last month</option>
                      <option value="thisYear">This year</option>
                      <option value="custom">Custom range</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
                    Trend interval
                    <select
                      aria-label="Trend interval"
                      value={trendInterval}
                      onChange={(event) => setTrendInterval(event.target.value as TrendInterval)}
                      className="h-10 min-w-36 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700"
                    >
                      <option value="day">Daily</option>
                      <option value="week">Weekly</option>
                      <option value="month">Monthly</option>
                    </select>
                  </label>
                  {dashboardPeriod === "custom" && (
                    <>
                      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
                        From
                        <input
                          aria-label="Dashboard start date"
                          type="date"
                          value={customDateFrom}
                          onChange={(event) => setCustomDateFrom(event.target.value)}
                          className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700"
                        />
                      </label>
                      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
                        To
                        <input
                          aria-label="Dashboard end date"
                          type="date"
                          value={customDateTo}
                          onChange={(event) => setCustomDateTo(event.target.value)}
                          className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700"
                        />
                      </label>
                      <Button onClick={handleApplyCustomDashboardPeriod} className="bg-teal-700 text-white hover:bg-teal-800">
                        Apply range
                      </Button>
                    </>
                  )}
                  <span className="ml-auto text-xs text-slate-500">
                    {dashboardDateRange.dateFrom || dashboardDateRange.dateTo
                      ? `${dashboardDateRange.dateFrom || "…"} – ${dashboardDateRange.dateTo || "…"}`
                      : "All available dates"}
                  </span>
                </CardContent>
              </Card>

              {/* Metric cards */}
              <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {loading ? (
                  Array.from({ length: 9 }).map((_, i) => <Skeleton key={i} className="h-28" />)
                ) : analytics ? (
                  <>
                    <MetricCard label="Total Income" value={fmt(analytics.total_income, activeCurrency)} icon={TrendingUp} accent="blue" sub={activeCurrency ? `in ${activeCurrency}` : "selected currency"} />
                    {analytics.total_revenue !== null && (
                      <MetricCard label="Business Revenue" value={fmt(analytics.total_revenue, activeCurrency)} icon={TrendingUp} accent="teal" sub="explicit revenue categories only" />
                    )}
                    <MetricCard label="Total Expenses" value={fmt(analytics.total_expenses, activeCurrency)} icon={Activity} accent="amber" sub={activeCurrency ? `in ${activeCurrency}` : "selected currency"} positive={false} />
                    <MetricCard label="Net Cash Flow / Savings" value={fmt(analytics.net_cash_flow, activeCurrency)} icon={CircleDollarSign} accent={analytics.net_cash_flow >= 0 ? "teal" : "rose"} sub="income minus expenses" positive={analytics.net_cash_flow >= 0} />
                    <MetricCard label="Savings Rate" value={analytics.savings_rate === null ? "—" : `${analytics.savings_rate}%`} icon={TrendingUp} accent="teal" sub={analytics.savings_rate === null ? "no income in this period" : "of period income saved"} positive={analytics.savings_rate === null || analytics.savings_rate >= 0} />
                    <MetricCard label="Transactions" value={String(analytics.transaction_count)} icon={Activity} accent="blue" sub="in selected period" />
                    <MetricCard label="Average Transaction" value={fmt(analytics.average_transaction_amount, activeCurrency)} icon={CircleDollarSign} accent="blue" sub={analytics.transaction_count ? "across income and expenses" : "no transactions"} />
                    <MetricCard label="Largest Transaction" value={fmt(analytics.largest_transaction_amount, activeCurrency)} icon={TrendingUp} accent="amber" sub="in selected period" positive={false} />
                    <MetricCard label="Average Risk Score" value={`${analytics.avg_risk_score}/100`} icon={Gauge} accent="rose" sub={`${analytics.flagged_count} flagged transactions`} positive={analytics.avg_risk_score < 50} />
                    <MetricCard label="High Risk" value={String(analytics.high_risk_count)} icon={ShieldAlert} accent="rose" sub={`${analytics.medium_risk_count} medium risk`} positive={analytics.high_risk_count === 0} />
                  </>
                ) : null}
              </section>

              {/* Charts */}
              <section className="grid gap-5 xl:grid-cols-[1.6fr_1fr]">
                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <CardTitle>Cash Flow Trend</CardTitle>
                    <CardDescription>Income, expenses, and net in the selected period</CardDescription>
                  </CardHeader>
                  <CardContent className="h-[260px] px-2 pb-4 sm:px-4">
                    {loading ? <Skeleton className="h-full" /> : (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={analytics?.cash_flow_trends || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <defs>
                            <linearGradient id="inc" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.25} /><stop offset="100%" stopColor="#14b8a6" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="exp" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.2} /><stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid vertical={false} stroke="#eef2f6" />
                          <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#94a3b8" }} tickFormatter={(v: number | string) => `${currencySymbol(activeCurrency)}${(Number(v)/1000).toFixed(0)}k`} />
                          <Tooltip {...chartTooltip} formatter={(value) => {
                            const rawValue = Array.isArray(value) ? value[0] : value;
                            return [`${currencySymbol(activeCurrency)}${Number(rawValue ?? 0).toLocaleString()}`, ""];
                          }} />
                          <Legend iconType="circle" wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                          <Area type="monotone" dataKey="income" name="Income" stroke="#0f766e" strokeWidth={2.5} fill="url(#inc)" />
                          <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#f59e0b" strokeWidth={2} fill="url(#exp)" />
                          <Area type="monotone" dataKey="net" name="Net cash flow" stroke="#6366f1" strokeWidth={2} fill="none" />
                        </AreaChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>

                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <CardTitle>Spend by Category</CardTitle>
                    <CardDescription>Distribution of expenses</CardDescription>
                  </CardHeader>
                  <CardContent className="flex items-center gap-4 pb-5">
                    {loading ? <Skeleton className="h-40 w-full" /> : analytics && analytics.category_breakdown.length > 0 ? (
                      <>
                        <div className="h-[160px] w-[160px] shrink-0">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie data={analytics.category_breakdown.slice(0, 6)} dataKey="amount" innerRadius={48} outerRadius={72} paddingAngle={3} stroke="none">
                                {analytics.category_breakdown.slice(0, 6).map((item) => (
                                  <Cell key={item.category} fill={CATEGORY_COLORS[item.category] || "#94a3b8"} />
                                ))}
                              </Pie>
                              <Tooltip {...chartTooltip} formatter={(value) => {
                                const rawValue = Array.isArray(value) ? value[0] : value;
                                return [`${currencySymbol(activeCurrency)}${Number(rawValue ?? 0).toLocaleString()}`, ""];
                              }} />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="w-full space-y-2.5">
                          {analytics.category_breakdown.slice(0, 5).map((item) => (
                            <div key={item.category} className="flex items-center justify-between text-xs">
                              <span className="flex items-center gap-2 text-slate-600">
                                <span className="size-2 rounded-full" style={{ backgroundColor: CATEGORY_COLORS[item.category] || "#94a3b8" }} />
                                {item.category}
                              </span>
                              <span className="font-semibold text-slate-900">{item.percentage}%</span>
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <p className="text-sm text-slate-400">No spending data yet.</p>
                    )}
                  </CardContent>
                </Card>
              </section>

              <section className="grid gap-5 xl:grid-cols-2">
                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <CardTitle>Top Merchants</CardTitle>
                    <CardDescription>Expense totals in {activeCurrency || "the selected currency"} for this period</CardDescription>
                  </CardHeader>
                  <CardContent className="h-[240px] px-2 pb-4 sm:px-4">
                    {analytics?.top_merchants.length ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={analytics.top_merchants} layout="vertical" margin={{ top: 4, right: 18, left: 12, bottom: 4 }}>
                          <CartesianGrid horizontal={false} stroke="#eef2f6" />
                          <XAxis type="number" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#94a3b8" }} tickFormatter={(value: number | string) => `${currencySymbol(activeCurrency)}${Number(value).toLocaleString()}`} />
                          <YAxis type="category" dataKey="merchant" width={100} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} />
                          <Tooltip {...chartTooltip} formatter={(value) => {
                            const rawValue = Array.isArray(value) ? value[0] : value;
                            return [`${currencySymbol(activeCurrency)}${Number(rawValue ?? 0).toLocaleString()}`, "Expenses"];
                          }} />
                          <Bar dataKey="amount" name="Expenses" fill="#0f766e" radius={[0, 5, 5, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <p className="pt-10 text-center text-sm text-slate-400">No merchant spending data in this period.</p>
                    )}
                  </CardContent>
                </Card>

                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <CardTitle>Risk Distribution</CardTitle>
                    <CardDescription>Transaction risk levels in the selected period</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-5 pt-2">
                    <div className="flex h-4 overflow-hidden rounded-full bg-slate-100" aria-label="Risk distribution">
                      {analytics?.risk_distribution.map(({ level, percentage }) => (
                        <div
                          key={level}
                          title={`${level}: ${percentage}%`}
                          className={level === "high" ? "bg-rose-500" : level === "medium" ? "bg-amber-400" : "bg-teal-500"}
                          style={{ width: `${percentage}%` }}
                        />
                      ))}
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      {analytics?.risk_distribution.map(({ level, count, percentage }) => (
                        <div key={level} className="rounded-xl bg-slate-50 p-3">
                          <p className={`text-xs font-semibold capitalize ${level === "high" ? "text-rose-600" : level === "medium" ? "text-amber-600" : "text-teal-700"}`}>{level} risk</p>
                          <p className="mt-1 text-xl font-bold text-slate-900">{count}</p>
                          <p className="text-xs text-slate-500">{percentage}% of transactions</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </section>

              {/* Alerts */}
              {unreadAlerts.length > 0 && (
                <section>
                  <div className="mb-4">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-rose-600">Security Alerts</p>
                    <h2 className="text-lg font-semibold tracking-tight text-slate-950">Items requiring attention</h2>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {unreadAlerts.slice(0, 3).map((alert) => (
                      <Card key={alert.id} className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between">
                            <div className={`rounded-lg p-2 ${alert.severity === "high" ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-600"}`}>
                              <ShieldAlert className="size-4" />
                            </div>
                            <Badge variant={alert.severity === "high" ? "destructive" : "outline"}>
                              {alert.severity}
                            </Badge>
                          </div>
                          <p className="mt-3 text-sm font-semibold text-slate-900 line-clamp-1">{alert.title}</p>
                          <p className="mt-1 text-xs text-slate-500 line-clamp-2">{alert.description}</p>
                          <div className="mt-3 flex items-center justify-between">
                            <span className="text-[11px] text-slate-400">{new Date(alert.created_at).toLocaleDateString()}</span>
                            <button onClick={() => handleMarkRead(alert.id)} className="text-[11px] font-semibold text-teal-700 hover:text-teal-900">
                              Mark read →
                            </button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </section>
              )}

              {/* Recent Transactions */}
              <section>
                <div className="mb-4 flex items-end justify-between">
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">Recent Activity</p>
                    <h2 className="text-lg font-semibold tracking-tight text-slate-950">Latest transactions</h2>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setActiveNav("Transactions")} className="bg-white">
                    View all <ChevronDown className="size-3.5" />
                  </Button>
                </div>
                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardContent className="p-0">
                    {loading ? (
                      <div className="p-4 space-y-3">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
                    ) : transactions.length === 0 ? (
                      <div className="p-8 text-center">
                        <p className="text-sm font-medium text-slate-700">No transactions yet.</p>
                        <p className="text-xs text-slate-400 mt-1">Upload your bank statement using the upload button above to begin.</p>
                      </div>
                    ) : (
                      <div className="divide-y divide-slate-100">
                        {transactions.slice(0, 8).map((txn) => (
                          <div key={txn.id} className="flex items-center gap-4 px-4 py-3">
                            <div className={`size-9 rounded-full flex items-center justify-center text-xs font-bold ${txn.is_flagged ? "bg-rose-100 text-rose-600" : "bg-slate-100 text-slate-600"}`}>
                              {txn.merchant.charAt(0).toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-slate-900 truncate">{txn.merchant}</p>
                              <p className="text-xs text-slate-400">{txn.category} · {new Date(txn.timestamp).toLocaleDateString()}</p>
                            </div>
                            <div className="text-right">
                              <p className={`text-sm font-semibold ${txn.transaction_type === "credit" ? "text-teal-600" : "text-slate-900"}`}>
                                {formatAmount(txn.amount, txn.currency, txn.transaction_type)}
                              </p>
                              <RiskBadge level={txn.risk_level} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </section>
            </>
          )}

          {/* ── TRANSACTIONS ─────────────────────────────────── */}
          {activeNav === "Transactions" && (
            <section>
              <div className="mb-6">
                <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">Transaction History</p>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950">All Transactions</h2>
                <p className="mt-1 text-sm text-slate-500">
                  {transactionTotal === 0 ? "No transactions found" : `Showing ${transactionPage * 50 + 1}–${transactionPage * 50 + visibleTransactions.length} of ${transactionTotal} transactions`}
                </p>
              </div>
              <Card className="mb-5 border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                <CardContent className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                  <input
                    aria-label="Search transactions"
                    placeholder="Search merchant or details"
                    value={filterDraft.search || ""}
                    onChange={(event) => setFilterDraft((filters) => ({ ...filters, search: event.target.value }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  />
                  <select
                    aria-label="Filter by transaction type"
                    value={filterDraft.transaction_type || ""}
                    onChange={(event) => setFilterDraft((filters) => ({
                      ...filters,
                      transaction_type: event.target.value as TransactionFilters["transaction_type"],
                    }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  >
                    <option value="">All types</option>
                    <option value="credit">Income / credit</option>
                    <option value="debit">Expense / debit</option>
                  </select>
                  <select
                    aria-label="Filter by category"
                    value={filterDraft.category || ""}
                    onChange={(event) => setFilterDraft((filters) => ({ ...filters, category: event.target.value }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  >
                    <option value="">All categories</option>
                    {Array.from(new Set(transactions.map((transaction) => transaction.category))).sort().map((category) => (
                      <option key={category} value={category}>{category}</option>
                    ))}
                  </select>
                  <select
                    aria-label="Filter by currency"
                    value={filterDraft.currency || ""}
                    onChange={(event) => setFilterDraft((filters) => ({ ...filters, currency: event.target.value }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  >
                    <option value="">All currencies</option>
                    {Array.from(new Set(transactions.map((transaction) => transaction.currency.toUpperCase()))).sort().map((currency) => (
                      <option key={currency} value={currency}>{currency}</option>
                    ))}
                  </select>
                  <label className="flex items-center gap-2 text-xs text-slate-500">
                    From
                    <input
                      aria-label="Filter from date"
                      type="date"
                      value={filterDraft.date_from || ""}
                      onChange={(event) => setFilterDraft((filters) => ({ ...filters, date_from: event.target.value }))}
                      className="h-10 min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                    />
                  </label>
                  <label className="flex items-center gap-2 text-xs text-slate-500">
                    To
                    <input
                      aria-label="Filter to date"
                      type="date"
                      value={filterDraft.date_to || ""}
                      onChange={(event) => setFilterDraft((filters) => ({ ...filters, date_to: event.target.value }))}
                      className="h-10 min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                    />
                  </label>
                  <input
                    aria-label="Minimum transaction amount"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="Min amount"
                    value={filterDraft.amount_min || ""}
                    onChange={(event) => setFilterDraft((filters) => ({ ...filters, amount_min: event.target.value }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  />
                  <input
                    aria-label="Maximum transaction amount"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="Max amount"
                    value={filterDraft.amount_max || ""}
                    onChange={(event) => setFilterDraft((filters) => ({ ...filters, amount_max: event.target.value }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  />
                  <input
                    aria-label="Minimum risk score"
                    type="number"
                    min="0"
                    max="100"
                    placeholder="Min risk (0–100)"
                    value={filterDraft.risk_score_min || ""}
                    onChange={(event) => setFilterDraft((filters) => ({ ...filters, risk_score_min: event.target.value }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  />
                  <input
                    aria-label="Maximum risk score"
                    type="number"
                    min="0"
                    max="100"
                    placeholder="Max risk (0–100)"
                    value={filterDraft.risk_score_max || ""}
                    onChange={(event) => setFilterDraft((filters) => ({ ...filters, risk_score_max: event.target.value }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  />
                  <select
                    aria-label="Filter by risk level"
                    value={filterDraft.risk_level || ""}
                    onChange={(event) => setFilterDraft((filters) => ({
                      ...filters,
                      risk_level: event.target.value as TransactionFilters["risk_level"],
                    }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  >
                    <option value="">All risk levels</option>
                    <option value="low">Low risk</option>
                    <option value="medium">Medium risk</option>
                    <option value="high">High risk</option>
                  </select>
                  <select
                    aria-label="Filter by transaction status"
                    value={filterDraft.transaction_status || ""}
                    onChange={(event) => setFilterDraft((filters) => ({ ...filters, transaction_status: event.target.value }))}
                    className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  >
                    <option value="">All statuses</option>
                    <option value="completed">Completed</option>
                    <option value="flagged">Flagged</option>
                  </select>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      aria-label="Flagged transactions only"
                      type="checkbox"
                      checked={filterDraft.flagged_only || false}
                      onChange={(event) => setFilterDraft((filters) => ({ ...filters, flagged_only: event.target.checked }))}
                      className="size-4 rounded border-slate-300 text-teal-700"
                    />
                    Flagged only
                  </label>
                  <div className="flex gap-2">
                    <Button onClick={() => { void handleApplyFilters(); }} disabled={filterLoading} className="flex-1 bg-teal-700 text-white hover:bg-teal-800">
                      {filterLoading ? "Filtering…" : "Apply"}
                    </Button>
                    <Button variant="outline" onClick={() => { void handleClearFilters(); }} disabled={filterLoading}>
                      Clear
                    </Button>
                  </div>
                </CardContent>
              </Card>
              <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                <CardContent className="p-0">
                  {loading ? (
                    <div className="p-4 space-y-3">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-100 bg-slate-50/50">
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Merchant</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Category</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Date</th>
                            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Amount</th>
                            <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">Risk</th>
                            <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {visibleTransactions.map((txn) => (
                            <tr key={txn.id} className={`hover:bg-slate-50 transition-colors ${txn.is_flagged ? "bg-rose-50/30" : ""}`}>
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-2.5">
                                  <div className={`size-8 rounded-full flex items-center justify-center text-xs font-bold ${txn.is_flagged ? "bg-rose-100 text-rose-600" : "bg-slate-100 text-slate-600"}`}>
                                    {txn.merchant.charAt(0)}
                                  </div>
                                  <div>
                                    <p className="font-medium text-slate-900">{txn.merchant}</p>
                                    {txn.location && <p className="text-[11px] text-slate-400">{txn.location}</p>}
                                  </div>
                                </div>
                              </td>
                              <td className="px-4 py-3">
                                <select
                                  aria-label={`Category for ${txn.merchant}`}
                                  value={txn.category}
                                  disabled={updatingCategoryId === txn.id}
                                  onChange={(event) => { void handleCategoryChange(txn.id, event.target.value); }}
                                  className="max-w-40 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700 disabled:opacity-60"
                                >
                                  {Array.from(new Set([...CATEGORY_OPTIONS, txn.category])).map((category) => (
                                    <option key={category} value={category}>{category}</option>
                                  ))}
                                </select>
                              </td>
                              <td className="px-4 py-3 text-slate-500">{new Date(txn.timestamp).toLocaleDateString()}</td>
                              <td className={`px-4 py-3 text-right font-semibold ${txn.transaction_type === "credit" ? "text-teal-600" : "text-slate-900"}`}>
                                {formatAmount(txn.amount, txn.currency, txn.transaction_type)}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <div className="flex items-center justify-center gap-1.5">
                                  <span className="text-xs font-medium text-slate-600">{txn.risk_score}</span>
                                  <RiskBadge level={txn.risk_level} />
                                </div>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <Badge variant={txn.status === "flagged" ? "destructive" : txn.status === "completed" ? "secondary" : "outline"}>
                                  {txn.status}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                          {visibleTransactions.length === 0 && (
                            <tr>
                              <td colSpan={6} className="px-4 py-10 text-center text-sm text-slate-500">
                                No transactions match these filters.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
              <div className="mt-4 flex items-center justify-between">
                <Button
                  variant="outline"
                  disabled={transactionPage === 0 || filterLoading}
                  onClick={() => { void handleTransactionPageChange(transactionPage - 1); }}
                >
                  Previous
                </Button>
                <p className="text-sm text-slate-500">
                  Page {transactionTotal === 0 ? 0 : transactionPage + 1} of {Math.ceil(transactionTotal / 50)}
                </p>
                <Button
                  variant="outline"
                  disabled={(transactionPage + 1) * 50 >= transactionTotal || filterLoading}
                  onClick={() => { void handleTransactionPageChange(transactionPage + 1); }}
                >
                  Next
                </Button>
              </div>
            </section>
          )}

          {/* ── RISK CENTER ──────────────────────────────────── */}
          {activeNav === "Risk Center" && (
            <section className="space-y-6">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-rose-600">Risk Center</p>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Fraud & Risk Detection</h2>
                <p className="mt-1 text-sm text-slate-500">Rule-based engine analyzing transaction patterns for suspicious activity.</p>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <MetricCard label="High Risk" value={String(transactions.filter(t => t.risk_level === "high").length)} icon={ShieldAlert} accent="rose" sub="transactions flagged" positive={false} />
                <MetricCard label="Medium Risk" value={String(transactions.filter(t => t.risk_level === "medium").length)} icon={AlertTriangle} accent="amber" sub="transactions flagged" positive={false} />
                <MetricCard label="Avg Risk Score" value={`${analytics?.avg_risk_score ?? 0}/100`} icon={Gauge} accent="blue" sub="across all transactions" />
              </div>

              {flaggedTxns.length > 0 ? (
                <div className="space-y-4">
                  <h3 className="text-base font-semibold text-slate-900">Flagged Transactions with Risk Explanation</h3>
                  {flaggedTxns.map((txn) => {
                    const signals: string[] = txn.risk_signals ? JSON.parse(txn.risk_signals) : [];
                    return (
                      <Card key={txn.id} className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)] border-l-4 border-l-rose-400">
                        <CardContent className="p-5">
                          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <p className="font-semibold text-slate-900">{txn.merchant}</p>
                                <RiskBadge level={txn.risk_level} />
                              </div>
                              <p className="text-xs text-slate-400">{txn.category} · {new Date(txn.timestamp).toLocaleDateString()} · {txn.location || "Unknown location"}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-lg font-bold text-slate-900">{formatAmount(txn.amount, txn.currency, txn.transaction_type)}</p>
                              <p className="text-xs text-slate-400">Risk score: <span className="font-bold text-rose-600">{txn.risk_score}/100</span></p>
                            </div>
                          </div>
                          {signals.length > 0 && (
                            <div className="mt-4 rounded-xl bg-rose-50 border border-rose-100 p-3">
                              <p className="text-xs font-semibold text-rose-700 mb-2">⚡ Risk signals detected:</p>
                              <ul className="space-y-1">
                                {signals.map((s, i) => (
                                  <li key={i} className="text-xs text-rose-700 flex items-start gap-1.5">
                                    <span className="mt-0.5 shrink-0">•</span>{s}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              ) : (
                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardContent className="p-8 text-center">
                    <ShieldAlert className="size-10 mx-auto text-teal-400 mb-3" />
                    <p className="text-sm font-medium text-slate-700">No flagged transactions found.</p>
                    <p className="text-xs text-slate-400 mt-1">All recent transactions appear normal.</p>
                  </CardContent>
                </Card>
              )}

              {/* All alerts */}
              {alerts.length > 0 && (
                <div>
                  <h3 className="text-base font-semibold text-slate-900 mb-3">All Security Alerts</h3>
                  <div className="space-y-2">
                    {alerts.map((alert) => (
                      <Card key={alert.id} className={`border-0 shadow-sm transition-all ${alert.is_read ? "opacity-60" : ""}`}>
                        <CardContent className="flex items-center gap-4 p-4">
                          <div className={`rounded-lg p-2 shrink-0 ${alert.severity === "high" ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-600"}`}>
                            <FileCheck2 className="size-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-slate-900 truncate">{alert.title}</p>
                            <p className="text-xs text-slate-500 line-clamp-1">{alert.description}</p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <Badge variant={alert.severity === "high" ? "destructive" : "outline"}>{alert.severity}</Badge>
                            {!alert.is_read && (
                              <button onClick={() => handleMarkRead(alert.id)} className="text-xs font-medium text-teal-700 hover:text-teal-900 whitespace-nowrap">
                                Mark read
                              </button>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* ── AI ASSISTANT ─────────────────────────────────── */}
          {activeNav === "AI Assistant" && (
            <section className="space-y-6">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">AI Assistant</p>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950">FinGuard AI Financial Assistant</h2>
                <p className="mt-1 text-sm text-slate-500">Ask naturally, explore your transaction history, and ask follow-up questions. Replies use your account data.</p>
              </div>

              <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
                {/* Chat */}
                <Card className="overflow-hidden border-0 bg-slate-950 text-white shadow-[0_12px_40px_rgba(15,23,42,0.15)]">
                  <CardHeader className="border-b border-white/10">
                    <div className="flex items-center gap-3">
                      <div className="rounded-xl bg-teal-500/20 p-2 text-teal-300"><Bot className="size-5" /></div>
                      <div>
                        <CardTitle className="text-white">FINMIND AI</CardTitle>
                        <CardDescription className="text-slate-400">Answers common questions from your account data; an API key is optional for generative chat.</CardDescription>
                      </div>
                      <Badge className="ml-auto bg-teal-500/15 text-teal-300 hover:bg-teal-500/15">
                        <span className="mr-1.5 size-1.5 rounded-full bg-teal-400" />Account-scoped
                      </Badge>
                      <button
                        type="button"
                        onClick={startNewChat}
                        aria-label="Start a new chat"
                        title="Start a new chat"
                        className="rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white"
                      >
                        <RefreshCw className="size-4" />
                      </button>
                    </div>
                  </CardHeader>
                  <CardContent className="flex min-h-[400px] flex-col p-0">
                    <div className="flex-1 space-y-4 overflow-auto p-5">
                      {chatMessages.map((msg, i) => (
                        <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
                          {msg.role === "assistant" && (
                            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-teal-500/20 text-teal-300">
                              <Sparkles className="size-3.5" />
                            </div>
                          )}
                          <div className={`max-w-[78%] rounded-2xl px-3.5 py-2.5 text-sm leading-6 whitespace-pre-wrap ${
                            msg.role === "user" ? "bg-teal-600 text-white" : "bg-white/10 text-slate-200"
                          }`}>
                            {msg.text}
                            {msg.aiUnavailable && (
                              <p className="mt-1 text-[10px] text-slate-400 border-t border-white/10 pt-1">
                                Built-in account-grounded mode. Add OPENAI_API_KEY in backend .env for open-ended generative chat.
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                      {chatLoading && (
                        <div className="flex gap-3">
                          <div className="flex size-7 items-center justify-center rounded-lg bg-teal-500/20 text-teal-300">
                            <Sparkles className="size-3.5 animate-pulse" />
                          </div>
                          <div className="flex items-center gap-1.5 rounded-2xl bg-white/10 px-4 py-3">
                            <span className="size-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                            <span className="size-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                            <span className="size-1.5 rounded-full bg-teal-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                          </div>
                        </div>
                      )}
                      <div ref={chatEndRef} />
                    </div>
                    <div className="border-t border-white/10 p-4">
                      <div className="flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-3 py-1.5">
                        <Paperclip className="size-4 text-slate-500" />
                        <input
                          value={chatInput}
                          onChange={(e) => setChatInput(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                          placeholder="Ask anything about your transactions..."
                          className="h-8 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
                        />
                        <button onClick={sendMessage} disabled={chatLoading} className="rounded-lg bg-teal-500 p-2 text-slate-950 transition hover:bg-teal-400 disabled:opacity-50">
                          <Send className="size-3.5" />
                        </button>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {[
                          "Why did my risk score increase?",
                          "What are my biggest expenses?",
                          "Show me suspicious transactions",
                          "Summarize my financial activity",
                        ].map((prompt) => (
                          <button
                            key={prompt}
                            onClick={() => { setChatInput(prompt); }}
                            className="rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-slate-400 hover:border-teal-500/50 hover:text-teal-300 transition-all"
                          >
                            {prompt}
                          </button>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Stats sidebar */}
                <div className="space-y-4">
                  <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                    <CardHeader><CardTitle>Data Context</CardTitle><CardDescription>What the AI knows about you</CardDescription></CardHeader>
                    <CardContent className="space-y-3">
                      {[
                        { label: "Transactions analyzed", value: transactions.length },
                        { label: "Flagged transactions", value: flaggedTxns.length },
                        { label: "Active alerts", value: unreadAlerts.length },
                        { label: "Categories tracked", value: analytics?.category_breakdown.length ?? 0 },
                      ].map(({ label, value }) => (
                        <div key={label} className="flex justify-between text-sm">
                          <span className="text-slate-500">{label}</span>
                          <span className="font-semibold text-slate-900">{value}</span>
                        </div>
                      ))}
                    </CardContent>
                  </Card>

                  <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                    <CardHeader><CardTitle>Top Categories</CardTitle></CardHeader>
                    <CardContent className="space-y-2.5">
                      {(analytics?.category_breakdown.slice(0, 4) ?? []).map((cat) => (
                        <div key={cat.category}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-600">{cat.category}</span>
                            <span className="font-semibold text-slate-900">{cat.percentage}%</span>
                          </div>
                          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full rounded-full bg-teal-500 transition-all" style={{ width: `${cat.percentage}%`, backgroundColor: CATEGORY_COLORS[cat.category] || "#14b8a6" }} />
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </section>
          )}

          {/* ── REPORTS ──────────────────────────────────────── */}
          {activeNav === "Reports" && (
            <section className="space-y-6">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">Reports</p>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Download Reports</h2>
                <p className="mt-1 text-sm text-slate-500">Reports are generated on demand when you download them; importing a statement updates your dashboard but does not create report files automatically.</p>
              </div>

              {reportError && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                  ⚠️ {reportError}
                </div>
              )}

              <div className="grid gap-5 md:grid-cols-2">
                {/* PDF Summary Report */}
                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="rounded-xl bg-teal-50 p-2.5 text-teal-700"><FileDown className="size-5" /></div>
                      <div>
                        <CardTitle>Full Summary Report</CardTitle>
                        <CardDescription>PDF — filtered transactions, accounts &amp; alerts</CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-xs text-slate-500 leading-5">
                      A styled PDF containing your account balances, active security alerts, and transactions matching the filters currently applied in Transaction History.
                    </p>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => handleDownload("pdf")}
                        disabled={reportLoading !== null}
                        className="flex-1 bg-teal-600 hover:bg-teal-500 text-white"
                        size="sm"
                      >
                        {reportLoading === "pdf" ? (
                          <><span className="size-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />Generating…</>
                        ) : (
                          <><Download className="size-3.5" />Download PDF</>
                        )}
                      </Button>
                      <Button
                        onClick={() => handleDownload("pdf-flagged")}
                        disabled={reportLoading !== null}
                        variant="outline"
                        size="sm"
                        className="flex-1"
                      >
                        {reportLoading === "pdf-flagged" ? (
                          <><span className="size-3.5 rounded-full border-2 border-slate-300 border-t-slate-700 animate-spin" />Generating…</>
                        ) : (
                          <><ShieldAlert className="size-3.5" />Flagged Only</>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* CSV Transactions Export */}
                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="rounded-xl bg-blue-50 p-2.5 text-blue-700"><Activity className="size-5" /></div>
                      <div>
                        <CardTitle>Transaction Export</CardTitle>
                        <CardDescription>CSV — import into Excel or Google Sheets</CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-xs text-slate-500 leading-5">
                      Transactions matching the filters currently applied in Transaction History, including merchant, category, amount, risk score, risk level, and status.
                    </p>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => handleDownload("csv")}
                        disabled={reportLoading !== null}
                        className="flex-1 bg-blue-600 hover:bg-blue-500 text-white"
                        size="sm"
                      >
                        {reportLoading === "csv" ? (
                          <><span className="size-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />Exporting…</>
                        ) : (
                          <><Download className="size-3.5" />Export CSV</>
                        )}
                      </Button>
                      <Button
                        onClick={() => handleDownload("csv-flagged")}
                        disabled={reportLoading !== null}
                        variant="outline"
                        size="sm"
                        className="flex-1"
                      >
                        {reportLoading === "csv-flagged" ? (
                          <><span className="size-3.5 rounded-full border-2 border-slate-300 border-t-slate-700 animate-spin" />Exporting…</>
                        ) : (
                          <><ShieldAlert className="size-3.5" />Flagged Only</>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle>Detailed Data Reports</CardTitle>
                  <CardDescription>Detailed exports use the active date, category, transaction, risk, and currency filters where applicable; currencies are never combined.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {([
                    ["monthly", "Monthly cash flow"],
                    ["category", "Category spending"],
                    ["merchant", "Merchant spending"],
                    ["risk", "Risk review"],
                    ["fraud", "Flagged transactions"],
                    ["alerts", "Security alerts"],
                  ] as const).map(([type, label]) => (
                    <Button
                      key={type}
                      variant="outline"
                      disabled={reportLoading !== null}
                      onClick={() => handleDownload(type)}
                    >
                      {reportLoading === type
                        ? <><RefreshCw className="size-3.5 animate-spin" />Preparing…</>
                        : <><Download className="size-3.5" />{label}</>}
                    </Button>
                  ))}
                </CardContent>
              </Card>
              <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle>Financial Security Report</CardTitle>
                  <CardDescription>PDF with risk overview, flagged transactions, signals, alerts, and safety guidance.</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button
                    disabled={reportLoading !== null}
                    onClick={() => handleDownload("security-pdf")}
                    className="bg-rose-700 text-white hover:bg-rose-800"
                  >
                    {reportLoading === "security-pdf"
                      ? <><RefreshCw className="size-3.5 animate-spin" />Preparing…</>
                      : <><ShieldAlert className="size-3.5" />Download Security PDF</>}
                  </Button>
                </CardContent>
              </Card>

              {/* Stats at a glance */}
              {analytics && (
                <Card className="border-0 shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <CardTitle>What will be included</CardTitle>
                    <CardDescription>Summary of data available in your reports</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                      {[
                        { label: "Transactions", value: analytics.transaction_count, accent: "teal" },
                        { label: "Flagged", value: analytics.flagged_count, accent: "rose" },
                        { label: "Categories", value: analytics.category_breakdown.length, accent: "blue" },
                        { label: "Alerts", value: alerts.length, accent: "amber" },
                      ].map(({ label, value, accent }) => (
                        <div key={label} className={`rounded-xl p-4 ${
                          accent === "teal" ? "bg-teal-50" :
                          accent === "rose" ? "bg-rose-50" :
                          accent === "blue" ? "bg-sky-50" : "bg-amber-50"
                        }`}>
                          <p className={`text-2xl font-bold ${
                            accent === "teal" ? "text-teal-700" :
                            accent === "rose" ? "text-rose-700" :
                            accent === "blue" ? "text-sky-700" : "text-amber-700"
                          }`}>{value}</p>
                          <p className="mt-1 text-xs text-slate-500">{label}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </section>
          )}
        </div>
      </div>
    </main>

  );
}
