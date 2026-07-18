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
from app.security import sniff_image

router = APIRouter(prefix="/api/photos", tags=["photos"])

MAX_SIZE = 15 * 1024 * 1024
EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}


PHASES = ("before", "during", "after")


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    taken_at: object
    pose: str
    phase: str


class PhaseUpdate(BaseModel):
    phase: str


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
    phase: str = Form("before"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ProgressPhoto:
    if pose not in ("front", "side", "back"):
        raise HTTPException(400, "Ogiltig pose.")
    if phase not in PHASES:
        raise HTTPException(400, "Ogiltig fas — före, mittemellan eller efter.")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "Bilden är för stor (max 15 MB).")
    # Lita på filens innehåll, inte på insänd Content-Type — det avgör
    # både lagrad typ och hur filen senare serveras.
    content_type = sniff_image(content)
    if content_type is None:
        raise HTTPException(400, "Endast JPEG/PNG/WebP/HEIC stöds.")

    photo_id = uuid.uuid4()
    path = _photos_dir(user.id) / f"{photo_id}{EXT[content_type]}"
    path.write_bytes(content)

    photo = ProgressPhoto(
        id=photo_id,
        user_id=user.id,
        pose=pose,
        phase=phase,
        file_path=str(path),
        content_type=content_type,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


@router.patch("/{photo_id}", response_model=PhotoOut)
async def update_photo_phase(
    photo_id: uuid.UUID,
    payload: PhaseUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ProgressPhoto:
    """Flytta ett foto mellan grupperna före/mittemellan/efter."""
    if payload.phase not in PHASES:
        raise HTTPException(400, "Ogiltig fas — före, mittemellan eller efter.")
    photo = await db.get(ProgressPhoto, photo_id)
    if photo is None or photo.user_id != user.id:
        raise HTTPException(404, "Fotot finns inte.")
    photo.phase = payload.phase
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
