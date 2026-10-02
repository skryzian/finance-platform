from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import ProfilePhotoUpload, UserOut
from app.storage.storage import get_storage_provider

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("", response_model=UserOut)
def update_profile(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if "first_name" in payload:
        current_user.first_name = str(payload["first_name"]).strip()
    if "last_name" in payload:
        current_user.last_name = str(payload["last_name"]).strip()
    if "phone" in payload:
        current_user.phone = str(payload["phone"])
    if "country" in payload:
        current_user.country = str(payload["country"]).upper()
    if "currency" in payload:
        current_user.currency = str(payload["currency"]).upper()
    if "timezone" in payload:
        current_user.timezone = str(payload["timezone"])

    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/photo", response_model=ProfilePhotoUpload)
def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported image type")

    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds 5MB limit")

    storage = get_storage_provider()
    file_name = f"users/{current_user.id}/{file.filename or 'profile-image'}"
    upload_path = storage.upload_file(file_name=file_name, content=file.file, content_type=file.content_type or "image/jpeg")

    current_user.profile_image_url = upload_path
    current_user.profile_thumbnail_url = upload_path
    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)

    return ProfilePhotoUpload(image_url=current_user.profile_image_url, thumbnail_url=current_user.profile_thumbnail_url)


@router.delete("/photo")
def delete_profile_photo(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.profile_image_url = None
    current_user.profile_thumbnail_url = None
    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Profile photo removed"}
