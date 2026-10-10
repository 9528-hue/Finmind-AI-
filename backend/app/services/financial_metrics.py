REVENUE_CATEGORIES = frozenset({
    "revenue",
    "business revenue",
    "sales",
    "freelance revenue",
    "service revenue",
})


def is_revenue_category(category: str | None) -> bool:
    return (category or "").strip().lower() in REVENUE_CATEGORIES
