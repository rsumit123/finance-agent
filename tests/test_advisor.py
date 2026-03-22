"""Tests for the purchase advisor."""

from datetime import date
from pathlib import Path

import pytest

from finance_agent.advisor import analyze_purchase
from finance_agent.tracker import add_expense, set_budget


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "test_data.json"


class TestPurchaseAdvisor:
    def test_no_budget_set(self, data_file):
        verdict = analyze_purchase(2000, data_file=data_file)
        assert verdict.can_buy is True
        assert "No budget set" in verdict.reasons[0]

    def test_can_afford(self, data_file):
        set_budget(30000, 7500, data_file=data_file)
        add_expense(1000, "food", "upi", "groceries", data_file=data_file)

        verdict = analyze_purchase(2000, data_file=data_file)
        assert verdict.can_buy is True
        assert verdict.weekly_remaining_after == 4500
        assert verdict.monthly_remaining_after == 27000

    def test_exceeds_weekly_budget(self, data_file):
        set_budget(30000, 5000, data_file=data_file)
        add_expense(4000, "shopping", "credit_card", "electronics", data_file=data_file)

        verdict = analyze_purchase(2000, data_file=data_file)
        assert verdict.can_buy is False
        assert any("weekly" in r.lower() for r in verdict.reasons)

    def test_exceeds_monthly_budget(self, data_file):
        set_budget(5000, 7500, data_file=data_file)
        add_expense(4500, "shopping", "credit_card", "stuff", data_file=data_file)

        verdict = analyze_purchase(2000, data_file=data_file)
        assert verdict.can_buy is False
        assert any("monthly" in r.lower() for r in verdict.reasons)

    def test_category_limit_exceeded(self, data_file):
        set_budget(
            30000, 7500,
            category_limits={"shopping": 3000},
            data_file=data_file,
        )
        add_expense(2500, "shopping", "upi", "clothes", data_file=data_file)

        verdict = analyze_purchase(1000, category="shopping", data_file=data_file)
        assert verdict.can_buy is False
        assert any("shopping" in r.lower() for r in verdict.reasons)

    def test_warning_near_weekly_limit(self, data_file):
        set_budget(30000, 5000, data_file=data_file)
        add_expense(500, "food", "upi", "snacks", data_file=data_file)

        # Purchase that uses > 80% of remaining weekly
        verdict = analyze_purchase(4000, data_file=data_file)
        assert verdict.can_buy is True
        assert len(verdict.warnings) > 0

    def test_small_purchase_no_warnings(self, data_file):
        set_budget(30000, 7500, data_file=data_file)

        verdict = analyze_purchase(100, data_file=data_file)
        assert verdict.can_buy is True
        assert len(verdict.warnings) == 0
