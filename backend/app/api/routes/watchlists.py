from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.market_asset import MarketAsset
from app.models.user import User
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.intelligence import WatchlistCreate, WatchlistItemCreate, WatchlistItemOut, WatchlistOut

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


@router.get("", response_model=list[WatchlistOut])
def list_watchlists(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Watchlist).filter(Watchlist.user_id == current_user.id).order_by(Watchlist.name).all()


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def create_watchlist(payload: WatchlistCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    watchlist = Watchlist(user_id=current_user.id, name=payload.name.strip(), description=payload.description)
    db.add(watchlist)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A watchlist with this name already exists") from exc
    db.refresh(watchlist)
    return watchlist


@router.get("/{watchlist_id}/items", response_model=list[WatchlistItemOut])
def list_watchlist_items(watchlist_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id).first()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    return db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == watchlist.id).order_by(WatchlistItem.added_at.desc()).all()


@router.post("/{watchlist_id}/items", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
def add_watchlist_item(
    watchlist_id: int,
    payload: WatchlistItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id).first()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    asset = db.query(MarketAsset).filter(MarketAsset.id == payload.market_asset_id, MarketAsset.is_active.is_(True)).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market asset not found")

    item = WatchlistItem(watchlist_id=watchlist.id, market_asset_id=asset.id, notes=payload.notes)
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Asset is already in this watchlist") from exc
    db.refresh(item)
    return item
