from app.routers.auth import router as auth_router
from app.routers.transactions import router as transactions_router
from app.routers.alerts import router as alerts_router
from app.routers.analytics import router as analytics_router
from app.routers.ai import router as ai_router
from app.routers.reports import router as reports_router

__all__ = [
    "auth_router",
    "transactions_router",
    "alerts_router",
    "analytics_router",
    "ai_router",
    "reports_router",
]
