"""Budget management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import BudgetCreate, BudgetOut, BudgetStatus, CategoryBudgetIn
from ..services.tracker import get_budget, get_budget_status, get_category_limits, set_budget

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.post("/", response_model=BudgetOut)
def create_budget(data: BudgetCreate, db: Session = Depends(get_db)):
    budget = set_budget(db, data)
    cat_limits = get_category_limits(db, budget.id)
    return BudgetOut(
        id=budget.id,
        monthly_limit=budget.monthly_limit,
        weekly_limit=budget.weekly_limit,
        category_limits=[
            CategoryBudgetIn(category=cl.category, limit_amount=cl.limit_amount)
            for cl in cat_limits
        ],
    )


@router.get("/", response_model=BudgetOut | None)
def get_current_budget(db: Session = Depends(get_db)):
    budget = get_budget(db)
    if not budget:
        return None
    cat_limits = get_category_limits(db, budget.id)
    return BudgetOut(
        id=budget.id,
        monthly_limit=budget.monthly_limit,
        weekly_limit=budget.weekly_limit,
        category_limits=[
            CategoryBudgetIn(category=cl.category, limit_amount=cl.limit_amount)
            for cl in cat_limits
        ],
    )


@router.get("/status", response_model=BudgetStatus | None)
def budget_status(db: Session = Depends(get_db)):
    return get_budget_status(db)
