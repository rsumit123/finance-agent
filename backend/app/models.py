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


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    bank_name = Column(String(100), nullable=False)  # e.g. "Axis", "HDFC"
    card_type = Column(String(50), nullable=False)    # "credit_card" or "bank_account"
    last_four = Column(String(10), default="")        # e.g. "1088"
    nickname = Column(String(100), default="")        # user-given name
    source_prefix = Column(String(100), default="")   # e.g. "stmt_axis_cc" for auto-matching
    created_at = Column(DateTime, server_default=func.now())


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
    card_id = Column(Integer, nullable=True)           # links to Card for CC payment tracking
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


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    job_type = Column(String(50), nullable=False)  # "alerts", "statements", "all"
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    result = Column(Text, default="")  # JSON string
    error = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class AccountBalance(Base):
    __tablename__ = "account_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    card_id = Column(Integer, nullable=True)
    bank_name = Column(String(100), default="")
    account_hint = Column(String(10), default="")  # last 4 digits
    balance = Column(Float, nullable=False)
    balance_date = Column(DateTime, nullable=False)
    source = Column(String(50), default="sms")  # sms, statement
    created_at = Column(DateTime, server_default=func.now())


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    keyword = Column(String(200), nullable=False)  # normalized merchant/description pattern
    category = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    key = Column(String(100), nullable=False)  # e.g. "excluded_banks"
    value = Column(Text, default="")  # JSON string
    created_at = Column(DateTime, server_default=func.now())


class UploadHistory(Base):
    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    transactions_found = Column(Integer, default=0)
    uploaded_at = Column(DateTime, server_default=func.now())
