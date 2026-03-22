"""JSON file-based storage for expenses and budgets."""

import json
import os
from pathlib import Path
from typing import Optional

from .models import Budget, Expense

DEFAULT_DATA_DIR = Path.home() / ".finance_agent"
DEFAULT_DATA_FILE = DEFAULT_DATA_DIR / "data.json"


def _ensure_data_dir(data_file: Path = DEFAULT_DATA_FILE):
    data_file.parent.mkdir(parents=True, exist_ok=True)


def _load_raw(data_file: Path = DEFAULT_DATA_FILE) -> dict:
    _ensure_data_dir(data_file)
    if not data_file.exists():
        return {"expenses": [], "budget": None}
    with open(data_file) as f:
        return json.load(f)


def _save_raw(data: dict, data_file: Path = DEFAULT_DATA_FILE):
    _ensure_data_dir(data_file)
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)


def load_expenses(data_file: Path = DEFAULT_DATA_FILE) -> list[Expense]:
    raw = _load_raw(data_file)
    return [Expense.from_dict(e) for e in raw.get("expenses", [])]


def save_expense(expense: Expense, data_file: Path = DEFAULT_DATA_FILE):
    raw = _load_raw(data_file)
    raw["expenses"].append(expense.to_dict())
    _save_raw(raw, data_file)


def delete_expense(expense_id: str, data_file: Path = DEFAULT_DATA_FILE) -> bool:
    raw = _load_raw(data_file)
    original_len = len(raw["expenses"])
    raw["expenses"] = [e for e in raw["expenses"] if e["id"] != expense_id]
    if len(raw["expenses"]) < original_len:
        _save_raw(raw, data_file)
        return True
    return False


def load_budget(data_file: Path = DEFAULT_DATA_FILE) -> Optional[Budget]:
    raw = _load_raw(data_file)
    if raw.get("budget"):
        return Budget.from_dict(raw["budget"])
    return None


def save_budget(budget: Budget, data_file: Path = DEFAULT_DATA_FILE):
    raw = _load_raw(data_file)
    raw["budget"] = budget.to_dict()
    _save_raw(raw, data_file)
