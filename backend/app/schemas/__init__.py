import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Account
# ──────────────────────────────────────────────
class AccountOut(BaseModel):
    id: str
    user_id: str
    name: str
    account_type: str
    balance: float
    currency: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Transaction
# ──────────────────────────────────────────────
class TransactionCreate(BaseModel):
    account_id: Optional[str] = None
    amount: float
    currency: str = "USD"
    merchant: str
    category: str
    transaction_type: str = "debit"
    payment_method: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    timestamp: Optional[datetime.datetime] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.isalpha() or len(normalized) != 3:
            raise ValueError("Currency must be a three-letter ISO code")
        return normalized


class TransactionCategoryUpdate(BaseModel):
    category: str

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 100:
            raise ValueError("Category must contain 1 to 100 characters")
        return normalized


class TransactionOut(BaseModel):
    id: str
    user_id: str
    account_id: Optional[str]
    amount: float
    currency: str
    merchant: str
    category: str
    transaction_type: str
    payment_method: Optional[str]
    location: Optional[str]
    status: str
    description: Optional[str]
    risk_score: float
    risk_level: str
    is_flagged: bool
    risk_signals: Optional[str]
    timestamp: datetime.datetime
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class TransactionStats(BaseModel):
    currency: Optional[str] = None
    total_count: int
    total_amount: float
    total_income: float
    total_expenses: float
    flagged_count: int
    high_risk_count: int
    avg_risk_score: float


# ──────────────────────────────────────────────
# Alert
# ──────────────────────────────────────────────
class AlertOut(BaseModel):
    id: str
    user_id: str
    transaction_id: Optional[str]
    title: str
    description: str
    severity: str
    is_read: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────
class CategoryBreakdown(BaseModel):
    category: str
    amount: float
    count: int
    percentage: float


class MonthlyTrend(BaseModel):
    month: str
    income: float
    expenses: float
    net: float


class MerchantSpend(BaseModel):
    merchant: str
    amount: float
    count: int


class RiskDistribution(BaseModel):
    level: str
    count: int
    percentage: float


class AnalyticsOut(BaseModel):
    total_balance: float
    total_income: float
    total_revenue: Optional[float] = None
    total_expenses: float
    net_cash_flow: float
    currency: Optional[str] = None
    transaction_count: int
    flagged_count: int
    avg_risk_score: float
    savings_rate: Optional[float] = None
    average_transaction_amount: float
    largest_transaction_amount: float
    high_risk_count: int
    medium_risk_count: int
    category_breakdown: List[CategoryBreakdown]
    monthly_trends: List[MonthlyTrend]
    cash_flow_trends: List[MonthlyTrend]
    top_merchants: List[MerchantSpend]
    risk_distribution: List[RiskDistribution]


# ──────────────────────────────────────────────
# AI Chat
# ──────────────────────────────────────────────
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    include_context: bool = True
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    ai_unavailable: bool = False
