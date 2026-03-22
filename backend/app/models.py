"""SQLAlchemy models for expenses, budgets, and parsed statements."""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    func,
)

from .database import Base


class PaymentMethod(str, enum.Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    UPI = "upi"
    CASH = "cash"
    NEFT = "neft"
    IMPS = "imps"


class Category(str, enum.Enum):
    FOOD = "food"
    TRANSPORT = "transport"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    BILLS = "bills"
    HEALTH = "health"
    EDUCATION = "education"
    GROCERIES = "groceries"
    RENT = "rent"
    SALARY = "salary"
    TRANSFER = "transfer"
    ATM = "atm"
    EMI = "emi"
    OTHER = "other"


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(Float, nullable=False)
    category = Column(String(50), nullable=False, default=Category.OTHER.value)
    payment_method = Column(String(50), nullable=False)
    description = Column(Text, default="")
    date = Column(Date, nullable=False)
    source = Column(String(50), default="manual")  # manual, bank_pdf, credit_card_pdf, upi
    reference_id = Column(String(100), default="")
    created_at = Column(DateTime, server_default=func.now())


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    monthly_limit = Column(Float, nullable=False)
    weekly_limit = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class CategoryBudget(Base):
    __tablename__ = "category_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)
    limit_amount = Column(Float, nullable=False)


class UploadHistory(Base):
    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # bank_statement, credit_card, upi
    transactions_found = Column(Integer, default=0)
    uploaded_at = Column(DateTime, server_default=func.now())
