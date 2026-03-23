"""SQLAlchemy models for users, expenses, budgets, and parsed statements."""

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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), default="")
    picture = Column(String(500), default="")
    created_at = Column(DateTime, server_default=func.now())


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
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50), nullable=False, default=Category.OTHER.value)
    payment_method = Column(String(50), nullable=False)
    description = Column(Text, default="")
    date = Column(DateTime, nullable=False)
    source = Column(String(50), default="manual")
    reference_id = Column(String(100), default="")
    created_at = Column(DateTime, server_default=func.now())


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    monthly_limit = Column(Float, nullable=False)
    weekly_limit = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class CategoryBudget(Base):
    __tablename__ = "category_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)
    limit_amount = Column(Float, nullable=False)


class PdfPassword(Base):
    __tablename__ = "pdf_passwords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    label = Column(String(100), default="")
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class GmailAccount(Base):
    __tablename__ = "gmail_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    email = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expiry = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class UploadHistory(Base):
    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    transactions_found = Column(Integer, default=0)
    uploaded_at = Column(DateTime, server_default=func.now())
