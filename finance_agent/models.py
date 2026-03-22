"""Data models for expenses, budgets, and payment methods."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from enum import Enum
from typing import Optional
import json
import uuid


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    UPI = "upi"
    CASH = "cash"


class Category(str, Enum):
    FOOD = "food"
    TRANSPORT = "transport"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    BILLS = "bills"
    HEALTH = "health"
    EDUCATION = "education"
    GROCERIES = "groceries"
    RENT = "rent"
    OTHER = "other"


@dataclass
class Expense:
    amount: float
    category: Category
    payment_method: PaymentMethod
    description: str
    date: str  # ISO format YYYY-MM-DD
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "amount": self.amount,
            "category": self.category.value,
            "payment_method": self.payment_method.value,
            "description": self.description,
            "date": self.date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Expense":
        return cls(
            id=data["id"],
            amount=data["amount"],
            category=Category(data["category"]),
            payment_method=PaymentMethod(data["payment_method"]),
            description=data["description"],
            date=data["date"],
        )


@dataclass
class Budget:
    monthly_limit: float
    weekly_limit: float
    category_limits: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "monthly_limit": self.monthly_limit,
            "weekly_limit": self.weekly_limit,
            "category_limits": self.category_limits,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Budget":
        return cls(
            monthly_limit=data["monthly_limit"],
            weekly_limit=data["weekly_limit"],
            category_limits=data.get("category_limits", {}),
        )
