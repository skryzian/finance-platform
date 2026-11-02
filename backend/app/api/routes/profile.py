from io import BytesIO
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import ProfilePhotoUpload, ProfileUpdate, UserOut
from app.storage.storage import StorageUnavailable, get_storage_provider

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field in ("first_name", "last_name", "phone", "country", "currency", "timezone"):
        value = getattr(payload, field)
        if value is not None:
            if field in {"first_name", "last_name"}:
                value = value.strip()
            elif field in {"country", "currency"}:
                value = value.upper()
            setattr(current_user, field, value)

    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/photo", response_model=ProfilePhotoUpload)
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5MB limit")

    if content.startswith(b"\xff\xd8\xff"):
        content_type, extension = "image/jpeg", "jpg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        content_type, extension = "image/png", "png"
    elif len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        content_type, extension = "image/webp", "webp"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File content is not a supported image")

    try:
        storage = get_storage_provider()
    except StorageUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Profile photo storage is unavailable") from exc

    file_name = f"users/{current_user.id}/{uuid4().hex}.{extension}"
    upload_path = storage.upload_file(file_name=file_name, content=BytesIO(content), content_type=content_type)

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
