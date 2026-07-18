import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_session
from app.models import User
from app.schemas import UserOut, UserUpdate
from app.security import sniff_image

router = APIRouter(prefix="/api/me", tags=["me"])

AVATAR_MAX_SIZE = 5 * 1024 * 1024
AVATAR_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}


def _serialize(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    if user.avatar_path:
        # v=mtime så webbläsaren hämtar om bilden när den byts
        try:
            version = int(Path(user.avatar_path).stat().st_mtime)
        except OSError:
            version = int(time.time())
        out.avatar_url = f"/api/me/avatar?v={version}"
    return out


@router.get("", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)) -> UserOut:
    return _serialize(user)


@router.patch("", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    data = payload.model_dump(exclude_unset=True)
    profile = data.pop("profile", None)
    for field, value in data.items():
        setattr(user, field, value)
    if profile is not None:
        # Slå ihop med befintlig profil så delvisa uppdateringar funkar
        merged = dict(user.profile or {})
        for key, value in profile.items():
            if value is None or value == "":
                merged.pop(key, None)
            else:
                merged[key] = value
        user.profile = merged
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _serialize(user)


def _avatar_dir() -> Path:
    path = Path(get_settings().data_dir) / "avatars"
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    content = await file.read()
    if len(content) > AVATAR_MAX_SIZE:
        raise HTTPException(413, "Bilden är för stor (max 5 MB).")
    content_type = sniff_image(content)
    if content_type is None:
        raise HTTPException(400, "Endast JPEG/PNG/WebP/HEIC stöds.")

    # En fil per användare — gammal bild ersätts/rensas
    if user.avatar_path:
        Path(user.avatar_path).unlink(missing_ok=True)
    path = _avatar_dir() / f"{user.id}{AVATAR_EXT[content_type]}"
    path.write_bytes(content)
    user.avatar_path = str(path)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _serialize(user)


@router.get("/avatar")
async def get_avatar(user: User = Depends(get_current_user)) -> FileResponse:
    if not user.avatar_path or not Path(user.avatar_path).exists():
        raise HTTPException(404, "Inget profilfoto uppladdat.")
    suffix = Path(user.avatar_path).suffix
    media = next(
        (mime for mime, ext in AVATAR_EXT.items() if ext == suffix), "image/jpeg"
    )
    return FileResponse(user.avatar_path, media_type=media)


@router.delete("/avatar", status_code=204)
async def delete_avatar(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    if user.avatar_path:
        Path(user.avatar_path).unlink(missing_ok=True)
        user.avatar_path = None
        session.add(user)
        await session.commit()
