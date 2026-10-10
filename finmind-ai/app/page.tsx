"use client";

import { useState, useEffect } from "react";
import {
  BrainCircuit, ShieldCheck, TrendingUp, Activity, ArrowRight,
  Zap, Lock, BarChart3, Bot, FileDown, ChevronRight,
  Star, CheckCircle2,
} from "lucide-react";
import LoginPage from "@/components/LoginPage";
import Dashboard from "@/components/Dashboard";

/* ── tiny hook: detect scroll for nav glass effect ────────── */
function useScrolled(threshold = 20) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > threshold);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, [threshold]);
  return scrolled;
}

/* ── feature card ──────────────────────────────────────────── */
function FeatureCard({
  icon: Icon, title, description, accent,
}: {
  icon: typeof ShieldCheck; title: string; description: string; accent: string;
}) {
  return (
    <div className="group relative rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm
                    hover:border-teal-500/30 hover:bg-white/10 transition-all duration-300">
      <div className={`mb-4 inline-flex size-11 items-center justify-center rounded-xl ${accent}`}>
        <Icon className="size-5" />
      </div>
      <h3 className="mb-2 text-base font-semibold text-white">{title}</h3>
      <p className="text-sm leading-6 text-slate-400">{description}</p>
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-teal-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  );
}

/* ── main page ─────────────────────────────────────────────── */
export default function Home() {
  const [view, setView] = useState<"landing" | "login" | "app">("landing");
  const [token, setToken] = useState<string | null>(null);
  const [userName, setUserName] = useState("");
  const scrolled = useScrolled();

  const handleLogin = (accessToken: string, name: string) => {
    setToken(accessToken);
    setUserName(name);
    setView("app");
  };

  const handleLogout = () => {
    setToken(null);
    setUserName("");
    setView("landing");
  };

  /* ── App view ── */
  if (view === "app" && token) {
    return <Dashboard token={token} userName={userName} onLogout={handleLogout} />;
  }

  /* ── Login view ── */
  if (view === "login") {
    return (
      <div>
        <LoginPage onLogin={handleLogin} />
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2">
          <button
            onClick={() => setView("landing")}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            ← Back to home
          </button>
        </div>
      </div>
    );
  }

  /* ── Landing view ── */
  return (
    <div className="min-h-screen bg-[#030712] text-white overflow-x-hidden">

      {/* ── Background gradients ── */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-1/4 left-1/2 -translate-x-1/2 w-[900px] h-[700px]
                        rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-1/2 -left-40 w-[500px] h-[500px]
                        rounded-full bg-blue-600/8 blur-[100px]" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px]
                        rounded-full bg-indigo-600/8 blur-[90px]" />
      </div>

      {/* ── Navbar ── */}
      <nav className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
        scrolled ? "border-b border-white/10 bg-[#030712]/80 backdrop-blur-xl" : ""
      }`}>
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-lg bg-teal-500/20 border border-teal-500/30">
                <BrainCircuit className="size-4 text-teal-400" />
              </div>
              <span className="text-[15px] font-bold tracking-tight">
                FinGuard <span className="text-teal-400">AI</span>
              </span>
            </div>

            {/* Nav links */}
            <div className="hidden md:flex items-center gap-7">
              {["Features", "Analytics", "Security", "Reports"].map((item) => (
                <a key={item} href={`#${item.toLowerCase()}`}
                   className="text-sm text-slate-400 hover:text-white transition-colors">
                  {item}
                </a>
              ))}
            </div>

            {/* CTA */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setView("login")}
                className="text-sm text-slate-400 hover:text-white transition-colors"
              >
                Sign in
              </button>
              <button
                onClick={() => setView("login")}
                className="flex items-center gap-1.5 rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold
                           text-slate-950 hover:bg-teal-400 transition-colors"
              >
                Get started <ChevronRight className="size-3.5" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative pt-36 pb-24 px-5 sm:px-8 text-center">
        <div className="mx-auto max-w-4xl">

          {/* Badge */}
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-teal-500/20
                          bg-teal-500/10 px-4 py-1.5 text-xs font-medium text-teal-300">
            <span className="size-1.5 rounded-full bg-teal-400 animate-pulse" />
            AI-Powered Financial Security Platform
          </div>

          <h1 className="mb-6 text-5xl sm:text-6xl lg:text-7xl font-bold leading-[1.1] tracking-tight">
            Guard your finances
            <span className="block mt-1 bg-gradient-to-r from-teal-400 via-cyan-300 to-teal-400
                             bg-clip-text text-transparent">
              with AI intelligence
            </span>
          </h1>

          <p className="mx-auto mb-10 max-w-2xl text-lg leading-8 text-slate-400">
            Real-time fraud detection, risk scoring, spending analytics, and an intelligent
            AI assistant — all in one platform built for modern finance teams.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => setView("login")}
              className="group flex items-center gap-2 rounded-xl bg-teal-500 px-7 py-3.5 text-base
                         font-semibold text-slate-950 hover:bg-teal-400 transition-all shadow-lg
                         shadow-teal-500/20 hover:shadow-teal-500/30"
            >
              Launch Dashboard
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform" />
            </button>
          </div>

          {/* Trust line */}
          <p className="mt-5 text-xs text-slate-600">
            🔒 Your dashboard is built from transactions you upload
          </p>
        </div>

        {/* Product preview without fabricated financial values */}
        <div className="mt-20 mx-auto max-w-5xl">
          <div className="relative rounded-2xl border border-white/10 bg-slate-900/80
                          backdrop-blur-xl shadow-2xl shadow-black/50 overflow-hidden">
            {/* Fake browser bar */}
            <div className="flex items-center gap-2 border-b border-white/10 bg-white/5 px-4 py-3">
              <span className="size-3 rounded-full bg-rose-500/70" />
              <span className="size-3 rounded-full bg-amber-500/70" />
              <span className="size-3 rounded-full bg-teal-500/70" />
              <div className="ml-4 flex-1 rounded-md bg-white/5 px-3 py-1 text-xs text-slate-500">
                FinGuard AI — Personal financial dashboard
              </div>
            </div>

            <div className="mx-6 mb-6 flex min-h-40 items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-8 text-center">
              <div>
                <p className="text-sm font-medium text-slate-300">Your financial picture, grounded in your data</p>
                <p className="mt-2 text-xs text-slate-500">Sign in and upload a statement to populate your dashboard.</p>
              </div>
            </div>

            {/* Gradient overlay at bottom */}
            <div className="absolute bottom-0 inset-x-0 h-20 bg-gradient-to-t from-[#030712] to-transparent" />
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className="py-20 px-5 sm:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 text-center">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-teal-400">Features</p>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
              Everything you need to secure your finances
            </h2>
            <p className="mt-4 text-slate-400 max-w-2xl mx-auto">
              A complete financial security toolkit powered by AI and real-time risk analysis.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" id="analytics">
            <FeatureCard
              icon={ShieldCheck}
              title="Real-Time Fraud Detection"
              description="Rule-based risk engine scores every transaction 0–100 across 7 risk dimensions including amount anomalies, velocity, merchant patterns, and location data."
              accent="bg-rose-500/15 text-rose-400"
            />
            <FeatureCard
              icon={TrendingUp}
              title="Spending Analytics"
              description="Interactive charts showing monthly cash flow, category breakdown, and spending trends. Drill down into any time period or merchant category."
              accent="bg-teal-500/15 text-teal-400"
            />
            <FeatureCard
              icon={Bot}
              title="AI Financial Assistant"
              description="Ask about your income, expenses, spending categories, recent transactions, and risk alerts. Built-in account-scoped answers work without an API key; OpenAI can add generative chat."
              accent="bg-blue-500/15 text-blue-400"
            />
            <FeatureCard
              icon={Activity}
              title="Risk Center"
              description="Dedicated view of all flagged transactions with detailed risk signal explanations. Understand exactly why a transaction was flagged."
              accent="bg-amber-500/15 text-amber-400"
            />
            <FeatureCard
              icon={FileDown}
              title="Report Generation"
              description="Download styled PDF financial reports and CSV exports with one click. Includes summary stats, account balances, alerts, and full transaction history."
              accent="bg-indigo-500/15 text-indigo-400"
            />
            <FeatureCard
              icon={Zap}
              title="Instant Risk Scoring"
              description="Every transaction is scored in milliseconds as it's created. High-risk transactions automatically trigger security alerts for immediate review."
              accent="bg-cyan-500/15 text-cyan-400"
            />
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section id="security" className="py-20 px-5 sm:px-8 bg-white/[0.02]">
        <div className="mx-auto max-w-5xl">
          <div className="mb-14 text-center">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-teal-400">How It Works</p>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Simple. Fast. Intelligent.</h2>
          </div>

          <div className="grid gap-8 md:grid-cols-3">
            {[
              { step: "01", icon: Lock, title: "Sign in securely",
                desc: "JWT-authenticated login. Your session is secure and your data is scoped to your account only." },
              { step: "02", icon: Activity, title: "Transactions are analyzed",
                desc: "Every transaction runs through the 7-rule risk engine and is scored, categorized, and stored in real time." },
              { step: "03", icon: BrainCircuit, title: "AI gives you insights",
                desc: "Ask the AI assistant anything. It reads your actual transaction data to give precise, grounded answers." },
            ].map(({ step, icon: Icon, title, desc }) => (
              <div key={step} className="relative pl-4 border-l border-teal-500/20">
                <p className="text-4xl font-black text-teal-500/20 mb-3">{step}</p>
                <div className="mb-3 inline-flex size-9 items-center justify-center rounded-lg bg-teal-500/15 text-teal-400">
                  <Icon className="size-4" />
                </div>
                <h3 className="mb-2 font-semibold text-white">{title}</h3>
                <p className="text-sm text-slate-400 leading-6">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Reports CTA ── */}
      <section id="reports" className="py-20 px-5 sm:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <div className="rounded-2xl border border-teal-500/20 bg-teal-500/5 p-10">
            <BarChart3 className="mx-auto mb-5 size-10 text-teal-400" />
            <h2 className="mb-4 text-2xl sm:text-3xl font-bold">Ready to secure your finances?</h2>
            <p className="mb-8 text-slate-400">
              Sign in and explore your full financial picture — risk scores, AI insights, and reports — in under a minute.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                onClick={() => setView("login")}
                className="flex items-center gap-2 rounded-xl bg-teal-500 px-8 py-3.5 font-semibold
                           text-slate-950 hover:bg-teal-400 transition-colors shadow-lg shadow-teal-500/20"
              >
                <Star className="size-4" />
                Open the Dashboard
              </button>
              <div className="flex items-center gap-1.5 text-sm text-slate-500">
                <CheckCircle2 className="size-4 text-teal-600" />
                Register or sign in to your account
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/5 py-10 px-5 sm:px-8">
        <div className="mx-auto max-w-6xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="flex size-7 items-center justify-center rounded-lg bg-teal-500/20 border border-teal-500/30">
              <BrainCircuit className="size-3.5 text-teal-400" />
            </div>
            <span className="text-sm font-bold">FinMind <span className="text-teal-400">AI</span></span>
          </div>
          <div className="flex items-center gap-6">
            {["Features", "Security", "Reports"].map((l) => (
              <a key={l} href={`#${l.toLowerCase()}`}
                 className="text-xs text-slate-600 hover:text-slate-300 transition-colors">{l}</a>
            ))}
          </div>
          <p className="text-xs text-slate-700">
            © 2026 FinGuard AI · Your financial data is scoped to your account
          </p>
        </div>
      </footer>

    </div>
  );
}
