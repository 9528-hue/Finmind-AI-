# FINMIND AI

> AI-powered financial security platform with real-time fraud detection, risk scoring, spending analytics, and an intelligent financial assistant.

---

## 🚀 Quick Start

### Option 1 — One-Click (Recommended)

Double-click **`start.bat`** or right-click **`start.ps1`** → *Run with PowerShell*

This automatically:
- Prepares missing Python/npm dependencies on first run
- Starts the API and its configured database
- Starts the website and verifies it can reach the API and database
- Opens the complete FINMIND AI site at **http://localhost:3000**

Use only the website URL for normal app use. Frontend API calls and health
checks are proxied through the same origin; the backend port is an internal
local service. API documentation is available at **http://localhost:3000/api/docs**.
The SQLite database is stored under `backend/finmind.db` unless `DATABASE_URL`
in `backend/.env` selects another database.

---

### Option 2 — Manual Start

**Terminal 1 — Backend:**
```powershell
cd backend
$env:PYTHONIOENCODING = "utf-8"
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```powershell
cd finmind-ai
npm run dev
```

Then open **http://localhost:3000**

---

## 🔐 Account

Register a new account or sign in with your own credentials. Dashboard data is
scoped to the authenticated account and comes from transactions you upload.

---

## 🏗️ Architecture

```
localhost:3000  (Next.js)
    │
    ├─ Landing page  ─────────────── /
    ├─ Login / Register
    └─ Dashboard (SPA)
         │
         └─ /api/*  ──(Next.js proxy)──► localhost:8000 (FastAPI)
                                              │
                                              ├─ /auth/login
                                              ├─ /analytics/
                                              ├─ /transactions/
                                              ├─ /alerts/
                                              ├─ /ai/chat
                                              └─ /reports/**
```

The Next.js `next.config.ts` proxies all `/api/*` requests to the FastAPI backend.
The backend connects to the configured database and verifies database readiness
at `/api/health`. This provides one browser-facing website origin while keeping
the frontend, API, and persistent database in their appropriate layers.

---

## 📁 Project Structure

```
finmind-ai(ext)/
├── backend/                  # FastAPI Python backend
│   ├── app/
│   │   ├── main.py           # App entry point + router registration
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   ├── routers/          # auth, transactions, alerts, analytics, ai, reports
│   │   ├── services/         # risk_engine, auth_service, ai_service
│   │   └── database/         # SQLite session + base
│   ├── requirements.txt
│   └── venv/                 # Python virtual environment
│
├── finmind-ai/               # Next.js 16 frontend
│   ├── app/
│   │   ├── layout.tsx        # Root layout with SEO + Inter font
│   │   ├── page.tsx          # Landing page + SPA router
│   │   └── globals.css
│   ├── components/
│   │   ├── Dashboard.tsx     # Main app: Overview, Transactions, Risk, AI, Reports
│   │   └── LoginPage.tsx     # Auth form
│   ├── lib/
│   │   └── api.ts            # API client (uses /api/ proxy)
│   ├── next.config.ts        # Proxy rewrites /api/* → backend
│   └── .env.local            # BACKEND_URL config
│
├── start.bat                 # Windows one-click full-stack launcher
├── start.ps1                 # PowerShell launcher with readiness checks
└── README.md
```

---

## 🔧 First-Time Setup

### Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
$env:PYTHONIOENCODING = "utf-8"
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### Frontend
```powershell
cd finmind-ai
npm install
```

---

## 🌟 Features

| Feature | Description |
|---------|-------------|
| **Landing Page** | Product overview, feature cards, and account-access CTA |
| **Authentication** | JWT-based login/register with secure token storage |
| **Overview** | Date-aware income, explicitly categorized business revenue (when available), expenses, cash-flow, savings, risk, average/largest transaction KPIs; daily/weekly/monthly trends, spending categories, top merchants, and risk distribution |
| **Transactions** | CSV/XLS/XLSX validation preview before import, automatically finding transaction headers below title/blank rows and across workbook sheets; maps common bank labels such as Txn Date, Party, Narration, Dr/Cr, and Money In/Out; shows row/currency/date results; searchable, filterable history with editable categories and risk signals |
| **Risk Center** | Dedicated view of all flagged transactions with severity indicators |
| **AI Assistant** | Authenticated, account-scoped multi-turn chat. Built-in responses cover summaries, income/expenses, merchant and category queries, date-scoped totals, transaction lists, and risk alerts without an API key; setting `OPENAI_API_KEY` enables open-ended generative chat with conversational history. |
| **Reports** | PDF financial summary and security report; transaction CSV (all or flagged-only); monthly cash flow, category, merchant, risk/fraud, and alert CSVs. Exports are user-scoped and honor applicable active filters without combining currencies. |

---

## ⚙️ Environment Variables

### Backend (`backend/.env`)
```env
SECRET_KEY=your-secret-key-change-in-production
OPENAI_API_KEY=sk-...        # Optional: enables generative AI responses (built-in chat works without it)
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=sqlite:///./finmind.db
```

### Frontend (`finmind-ai/.env.local`)
```env
BACKEND_URL=http://localhost:8000   # Where FastAPI is running
```

---

## 🐍 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (Turbopack), TypeScript, Tailwind CSS v4, Recharts, shadcn/ui |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite |
| Auth | JWT (python-jose), bcrypt (passlib) |
| AI | OpenAI GPT-4o-mini (optional; reports unavailability when not configured) |
| Reports | ReportLab PDF, Python csv module |
| Runtime | Python 3.14, Node.js |
