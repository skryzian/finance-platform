from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.alert import Alert, AlertRule
from app.models.market_asset import MarketAsset
from app.models.opportunity import Opportunity, OpportunityReview
from app.models.user import User
from app.schemas.intelligence import (
    AlertOut,
    AlertRuleCreate,
    AlertRuleOut,
    OpportunityOut,
    OpportunityReviewOut,
    OpportunityReviewUpdate,
)

router = APIRouter(prefix="/api", tags=["financial intelligence"])


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Alert).filter(Alert.user_id == current_user.id).order_by(Alert.created_at.desc()).limit(limit).all()


@router.get("/alert-rules", response_model=list[AlertRuleOut])
def list_alert_rules(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(AlertRule).filter(AlertRule.user_id == current_user.id).order_by(AlertRule.created_at.desc()).all()


@router.post("/alert-rules", response_model=AlertRuleOut, status_code=201)
def create_alert_rule(payload: AlertRuleCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.market_asset_id is not None:
        asset = db.query(MarketAsset).filter(MarketAsset.id == payload.market_asset_id, MarketAsset.is_active.is_(True)).first()
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market asset not found")

    rule = AlertRule(user_id=current_user.id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
    status_filter: str | None = Query(default=None, alias="status", max_length=24),
    country_code: str | None = Query(default=None, min_length=2, max_length=2),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Opportunity).filter(or_(Opportunity.user_id.is_(None), Opportunity.user_id == current_user.id))
    if status_filter:
        query = query.filter(Opportunity.status == status_filter.upper())
    if country_code:
        query = query.filter(or_(Opportunity.country_code.is_(None), Opportunity.country_code == country_code.upper()))
    return query.order_by(Opportunity.discovered_at.desc()).limit(limit).all()


@router.put("/opportunities/{opportunity_id}/review", response_model=OpportunityReviewOut)
def review_opportunity(
    opportunity_id: int,
    payload: OpportunityReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
        or_(Opportunity.user_id.is_(None), Opportunity.user_id == current_user.id),
    ).first()
    if opportunity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    review = db.query(OpportunityReview).filter(
        OpportunityReview.opportunity_id == opportunity_id,
        OpportunityReview.user_id == current_user.id,
    ).first()
    if review is None:
        review = OpportunityReview(
            opportunity_id=opportunity_id,
            user_id=current_user.id,
            status=payload.status,
            user_notes=payload.user_notes,
        )
        db.add(review)
    else:
        review.status = payload.status
        review.user_notes = payload.user_notes

    db.commit()
    db.refresh(review)
    return review
