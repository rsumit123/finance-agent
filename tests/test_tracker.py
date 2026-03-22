"""Tests for expense tracking functionality."""

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from finance_agent.models import Category, PaymentMethod
from finance_agent.tracker import (
    add_expense,
    get_budget_status,
    get_current_month_expenses,
    get_current_week_expenses,
    remove_expense,
    set_budget,
    summarize_expenses,
)


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "test_data.json"


class TestAddExpense:
    def test_add_expense_basic(self, data_file):
        exp = add_expense(500, "food", "upi", "lunch", data_file=data_file)
        assert exp.amount == 500
        assert exp.category == Category.FOOD
        assert exp.payment_method == PaymentMethod.UPI
        assert exp.description == "lunch"
        assert exp.date == date.today().isoformat()

    def test_add_expense_custom_date(self, data_file):
        exp = add_expense(
            1000, "shopping", "credit_card", "shoes",
            expense_date="2026-03-15", data_file=data_file,
        )
        assert exp.date == "2026-03-15"

    def test_add_multiple_expenses(self, data_file):
        add_expense(100, "food", "upi", "tea", data_file=data_file)
        add_expense(200, "transport", "debit_card", "auto", data_file=data_file)
        add_expense(300, "food", "cash", "dinner", data_file=data_file)

        from finance_agent.storage import load_expenses
        expenses = load_expenses(data_file)
        assert len(expenses) == 3


class TestRemoveExpense:
    def test_remove_existing(self, data_file):
        exp = add_expense(500, "food", "upi", "lunch", data_file=data_file)
        assert remove_expense(exp.id, data_file) is True

        from finance_agent.storage import load_expenses
        assert len(load_expenses(data_file)) == 0

    def test_remove_nonexistent(self, data_file):
        assert remove_expense("nonexistent", data_file) is False


class TestSummarize:
    def test_summarize_empty(self):
        result = summarize_expenses([])
        assert result["total"] == 0
        assert result["count"] == 0

    def test_summarize_expenses(self, data_file):
        add_expense(500, "food", "upi", "lunch", data_file=data_file)
        add_expense(1500, "shopping", "credit_card", "clothes", data_file=data_file)
        add_expense(200, "food", "cash", "snacks", data_file=data_file)

        from finance_agent.storage import load_expenses
        expenses = load_expenses(data_file)
        summary = summarize_expenses(expenses)

        assert summary["total"] == 2200
        assert summary["count"] == 3
        assert summary["by_category"]["food"] == 700
        assert summary["by_category"]["shopping"] == 1500
        assert summary["by_payment_method"]["upi"] == 500


class TestBudget:
    def test_set_budget(self, data_file):
        budget = set_budget(30000, 7500, data_file=data_file)
        assert budget.monthly_limit == 30000
        assert budget.weekly_limit == 7500

    def test_set_budget_with_categories(self, data_file):
        budget = set_budget(
            30000, 7500,
            category_limits={"food": 8000, "shopping": 5000},
            data_file=data_file,
        )
        assert budget.category_limits["food"] == 8000

    def test_budget_status(self, data_file):
        set_budget(30000, 7500, data_file=data_file)
        add_expense(500, "food", "upi", "lunch", data_file=data_file)
        add_expense(1000, "shopping", "credit_card", "book", data_file=data_file)

        status = get_budget_status(data_file)
        assert status is not None
        assert status["weekly"]["spent"] == 1500
        assert status["monthly"]["spent"] == 1500
        assert status["weekly"]["remaining"] == 6000
        assert status["monthly"]["remaining"] == 28500

    def test_budget_status_no_budget(self, data_file):
        assert get_budget_status(data_file) is None
