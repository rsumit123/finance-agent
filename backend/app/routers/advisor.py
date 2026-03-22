"""Purchase advisor endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import PurchaseQuery, PurchaseVerdict
from ..services.advisor import analyze_purchase

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


@router.post("/can-i-buy", response_model=PurchaseVerdict)
def can_i_buy(query: PurchaseQuery, db: Session = Depends(get_db)):
    """Analyze whether you can afford a purchase right now."""
    return analyze_purchase(db, query.amount, query.category)
