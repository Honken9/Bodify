from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import User
from app.services import weekly_report as report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/weekly")
async def weekly(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Senast avslutade veckans rapport, jämförd med veckan innan."""
    return await report_service.weekly_report(db, user.id)
