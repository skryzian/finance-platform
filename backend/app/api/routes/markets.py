from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.market_asset import MarketAsset
from app.models.user import User
from app.schemas.intelligence import MarketAssetOut

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/assets", response_model=list[MarketAssetOut])
def list_market_assets(
    search: str | None = Query(default=None, max_length=80),
    asset_type: str | None = Query(default=None, max_length=50),
    exchange: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    query = db.query(MarketAsset).filter(MarketAsset.is_active.is_(True))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter((MarketAsset.symbol.ilike(pattern)) | (MarketAsset.name.ilike(pattern)))
    if asset_type:
        query = query.filter(MarketAsset.asset_type == asset_type)
    if exchange:
        query = query.filter(MarketAsset.exchange == exchange)
    return query.order_by(MarketAsset.symbol).limit(limit).all()
