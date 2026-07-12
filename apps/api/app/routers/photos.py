import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_session
from app.models import ProgressPhoto, User

router = APIRouter(prefix="/api/photos", tags=["photos"])

MAX_SIZE = 15 * 1024 * 1024
ALLOWED = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    taken_at: object
    pose: str


def _photos_dir(user_id: uuid.UUID) -> Path:
    root = Path(get_settings().data_dir) / "photos" / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


@router.get("", response_model=list[PhotoOut])
async def list_photos(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[ProgressPhoto]:
    rows = await db.scalars(
        select(ProgressPhoto)
        .where(ProgressPhoto.user_id == user.id)
        .order_by(ProgressPhoto.taken_at.desc())
    )
    return list(rows)


@router.post("", response_model=PhotoOut, status_code=201)
async def upload_photo(
    file: UploadFile = File(...),
    pose: str = Form("front"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ProgressPhoto:
    if pose not in ("front", "side", "back"):
        raise HTTPException(400, "Ogiltig pose.")
    ext = ALLOWED.get(file.content_type or "")
    if ext is None:
        raise HTTPException(400, "Endast JPEG/PNG/WebP/HEIC stöds.")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "Bilden är för stor (max 15 MB).")

    photo_id = uuid.uuid4()
    path = _photos_dir(user.id) / f"{photo_id}{ext}"
    path.write_bytes(content)

    photo = ProgressPhoto(
        id=photo_id,
        user_id=user.id,
        pose=pose,
        file_path=str(path),
        content_type=file.content_type or "image/jpeg",
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


@router.get("/{photo_id}/file")
async def photo_file(
    photo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> FileResponse:
    photo = await db.get(ProgressPhoto, photo_id)
    if photo is None or photo.user_id != user.id:
        raise HTTPException(404, "Fotot finns inte.")
    if not Path(photo.file_path).exists():
        raise HTTPException(404, "Filen saknas på disken.")
    return FileResponse(photo.file_path, media_type=photo.content_type)


@router.delete("/{photo_id}", status_code=204)
async def delete_photo(
    photo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    photo = await db.get(ProgressPhoto, photo_id)
    if photo is None or photo.user_id != user.id:
        raise HTTPException(404, "Fotot finns inte.")
    Path(photo.file_path).unlink(missing_ok=True)
    await db.delete(photo)
    await db.commit()
