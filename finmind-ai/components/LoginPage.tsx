"use client";

import { useState } from "react";
import { BrainCircuit, Eye, EyeOff, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login, register, getCurrentUser, ApiError } from "@/lib/api";

interface Props {
  onLogin: (token: string, name: string) => void;
}

export default function LoginPage({ onLogin }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        const data = await login(email, password);
        const profile = await getCurrentUser(data.access_token);
        onLogin(data.access_token, profile.full_name);
      } else {
        await register(email, fullName, password);
        const data = await login(email, password);
        onLogin(data.access_token, fullName);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Cannot connect to the backend. Make sure it is running on port 8000.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-teal-950 flex items-center justify-center p-4">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-teal-500/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-[600px] h-[600px] rounded-full bg-blue-500/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center size-16 rounded-2xl bg-teal-500/20 border border-teal-500/30 backdrop-blur mb-4">
            <BrainCircuit className="size-8 text-teal-400" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            FinMind <span className="text-teal-400">AI</span>
          </h1>
          <p className="mt-2 text-slate-400 text-sm">Intelligent financial security platform</p>
        </div>

        {/* Card */}
        <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-2xl p-8 shadow-2xl">
          {/* Tabs */}
          <div className="flex bg-white/5 rounded-xl p-1 mb-6">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(""); }}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                  mode === m
                    ? "bg-teal-500 text-slate-950 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {m === "login" ? "Sign In" : "Register"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Full name</label>
                <Input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Alex Sterling"
                  required
                  className="bg-white/5 border-white/15 text-white placeholder:text-slate-500 focus-visible:ring-teal-500/50"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Email</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                className="bg-white/5 border-white/15 text-white placeholder:text-slate-500 focus-visible:ring-teal-500/50"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Password</label>
              <div className="relative">
                <Input
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="bg-white/5 border-white/15 text-white placeholder:text-slate-500 focus-visible:ring-teal-500/50 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                >
                  {showPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-rose-500/15 border border-rose-500/25 px-3 py-2 text-sm text-rose-300">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-teal-500 hover:bg-teal-400 text-slate-950 font-semibold h-10"
            >
              {loading ? (
                <><Loader2 className="size-4 animate-spin" /> {mode === "login" ? "Signing in..." : "Creating account..."}</>
              ) : (
                mode === "login" ? "Sign In" : "Create Account"
              )}
            </Button>
          </form>

          {/* Account guidance */}
          {mode === "login" && (
            <div className="mt-4 rounded-lg bg-teal-500/10 border border-teal-500/20 p-3">
              <div className="flex items-center gap-2 text-teal-300 text-xs font-semibold mb-1">
                <ShieldCheck className="size-3.5" />
                Your transactions stay private
              </div>
              <p className="text-slate-400 text-xs">
                Sign in to your account or choose <strong className="text-slate-300">Register</strong> to create one.
              </p>
            </div>
          )}
        </div>

        <p className="text-center text-slate-600 text-xs mt-6">
          🔒 Upload your transaction history after signing in.
        </p>
      </div>
    </div>
  );
}
