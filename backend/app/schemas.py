"""Pydantic schemas for request/response validation."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


# --- Expense schemas ---


class ExpenseCreate(BaseModel):
    amount: float
    category: str = "other"
    payment_method: str
    description: str = ""
    date: datetime
    source: str = "manual"
    reference_id: str = ""


class ExpenseOut(BaseModel):
    id: int
    amount: float
    category: str
    payment_method: str
    description: str
    date: datetime
    source: str
    reference_id: str
    card_id: Optional[int] = None
    linked_transaction_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExpenseSummary(BaseModel):
    total: float
    count: int
    income: float = 0
    expense: float = 0
    transfers: float = 0
    by_category: dict[str, float]
    by_payment_method: dict[str, float]


# --- Budget schemas ---


class CategoryBudgetIn(BaseModel):
    category: str
    limit_amount: float


class BudgetCreate(BaseModel):
    monthly_limit: float
    weekly_limit: float
    category_limits: list[CategoryBudgetIn] = []


class BudgetOut(BaseModel):
    id: int
    monthly_limit: float
    weekly_limit: float
    category_limits: list[CategoryBudgetIn] = []

    model_config = {"from_attributes": True}


class BudgetStatus(BaseModel):
    weekly_limit: float
    weekly_spent: float
    weekly_remaining: float
    weekly_percent: float
    monthly_limit: float
    monthly_spent: float
    monthly_remaining: float
    monthly_percent: float
    categories: dict[str, dict]


# --- Purchase advisor schemas ---


class PurchaseQuery(BaseModel):
    amount: float
    category: Optional[str] = None


class PurchaseVerdict(BaseModel):
    can_buy: bool
    amount: float
    reasons: list[str]
    warnings: list[str]
    weekly_remaining_after: float
    monthly_remaining_after: float
    suggestion: str


# --- Upload schemas ---


class UploadResult(BaseModel):
    filename: str
    file_type: str
    transactions_found: int
    transactions: list[ExpenseOut]
    duplicates_skipped: int = 0
    duplicate_transactions: list[ExpenseOut] = []


# --- Subscription schemas ---


class Subscription(BaseModel):
    name: str
    amount: float
    frequency: str = "monthly"
    last_charged: date
    next_expected: Optional[date] = None
    total_spent: float
    occurrence_count: int
