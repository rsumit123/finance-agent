"""API endpoint tests."""

from datetime import date


class TestExpenses:
    def test_add_expense(self, client):
        resp = client.post("/api/expenses/", json={
            "amount": 500,
            "category": "food",
            "payment_method": "upi",
            "description": "lunch",
            "date": date.today().isoformat(),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 500
        assert data["category"] == "food"
        assert data["payment_method"] == "upi"

    def test_list_expenses(self, client):
        # Add two expenses
        for desc in ["lunch", "coffee"]:
            client.post("/api/expenses/", json={
                "amount": 100,
                "category": "food",
                "payment_method": "upi",
                "description": desc,
                "date": date.today().isoformat(),
            })

        resp = client.get("/api/expenses/", params={"period": "month"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_delete_expense(self, client):
        resp = client.post("/api/expenses/", json={
            "amount": 100,
            "category": "food",
            "payment_method": "cash",
            "description": "snack",
            "date": date.today().isoformat(),
        })
        eid = resp.json()["id"]

        resp = client.delete(f"/api/expenses/{eid}")
        assert resp.status_code == 200

        resp = client.delete(f"/api/expenses/{eid}")
        assert resp.status_code == 404

    def test_expense_summary(self, client):
        client.post("/api/expenses/", json={
            "amount": 500,
            "category": "food",
            "payment_method": "upi",
            "description": "lunch",
            "date": date.today().isoformat(),
        })
        client.post("/api/expenses/", json={
            "amount": 1500,
            "category": "shopping",
            "payment_method": "credit_card",
            "description": "clothes",
            "date": date.today().isoformat(),
        })

        resp = client.get("/api/expenses/summary", params={"period": "month"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2000
        assert data["count"] == 2
        assert data["by_category"]["food"] == 500
        assert data["by_category"]["shopping"] == 1500


class TestBudget:
    def test_set_budget(self, client):
        resp = client.post("/api/budget/", json={
            "monthly_limit": 30000,
            "weekly_limit": 7500,
            "category_limits": [
                {"category": "food", "limit_amount": 8000},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["monthly_limit"] == 30000
        assert data["weekly_limit"] == 7500
        assert len(data["category_limits"]) == 1

    def test_get_budget(self, client):
        client.post("/api/budget/", json={
            "monthly_limit": 25000,
            "weekly_limit": 6000,
            "category_limits": [],
        })

        resp = client.get("/api/budget/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["monthly_limit"] == 25000

    def test_budget_status(self, client):
        client.post("/api/budget/", json={
            "monthly_limit": 30000,
            "weekly_limit": 7500,
            "category_limits": [],
        })
        client.post("/api/expenses/", json={
            "amount": 1000,
            "category": "food",
            "payment_method": "upi",
            "description": "test",
            "date": date.today().isoformat(),
        })

        resp = client.get("/api/budget/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["weekly_spent"] == 1000
        assert data["monthly_spent"] == 1000
        assert data["weekly_remaining"] == 6500
        assert data["monthly_remaining"] == 29000

    def test_no_budget(self, client):
        resp = client.get("/api/budget/")
        assert resp.status_code == 200
        assert resp.json() is None


class TestAdvisor:
    def test_can_buy_no_budget(self, client):
        resp = client.post("/api/advisor/can-i-buy", json={"amount": 2000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_buy"] is True
        assert "No budget" in data["reasons"][0]

    def test_can_buy_within_budget(self, client):
        client.post("/api/budget/", json={
            "monthly_limit": 30000,
            "weekly_limit": 7500,
            "category_limits": [],
        })
        client.post("/api/expenses/", json={
            "amount": 1000,
            "category": "food",
            "payment_method": "upi",
            "description": "groceries",
            "date": date.today().isoformat(),
        })

        resp = client.post("/api/advisor/can-i-buy", json={"amount": 2000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_buy"] is True

    def test_cannot_buy_exceeds_weekly(self, client):
        client.post("/api/budget/", json={
            "monthly_limit": 30000,
            "weekly_limit": 5000,
            "category_limits": [],
        })
        client.post("/api/expenses/", json={
            "amount": 4000,
            "category": "shopping",
            "payment_method": "credit_card",
            "description": "stuff",
            "date": date.today().isoformat(),
        })

        resp = client.post("/api/advisor/can-i-buy", json={"amount": 2000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_buy"] is False
        assert any("weekly" in r.lower() for r in data["reasons"])

    def test_cannot_buy_exceeds_category(self, client):
        client.post("/api/budget/", json={
            "monthly_limit": 30000,
            "weekly_limit": 7500,
            "category_limits": [
                {"category": "shopping", "limit_amount": 3000},
            ],
        })
        client.post("/api/expenses/", json={
            "amount": 2500,
            "category": "shopping",
            "payment_method": "upi",
            "description": "clothes",
            "date": date.today().isoformat(),
        })

        resp = client.post("/api/advisor/can-i-buy", json={
            "amount": 1000,
            "category": "shopping",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_buy"] is False
        assert any("shopping" in r.lower() for r in data["reasons"])


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
