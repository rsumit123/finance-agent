"""Budget management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import BudgetCreate, BudgetOut, BudgetStatus, CategoryBudgetIn
from ..services.tracker import get_budget, get_budget_status, get_category_limits, set_budget

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.post("/", response_model=BudgetOut)
def create_budget(
    data: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = set_budget(db, data, user_id=current_user.id)
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
def get_current_budget(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = get_budget(db, user_id=current_user.id)
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
def budget_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_budget_status(db, user_id=current_user.id)
