"""Dashboard summary endpoint."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import InspectionRecord, MaintenanceSchedule, User
from app.schemas import DashboardSummary
from app.util import schedule_status

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def summary(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    due_dates = (await db.execute(select(MaintenanceSchedule.next_due))).scalars().all()
    counts = {"ok": 0, "due_soon": 0, "overdue": 0}
    for d in due_dates:
        counts[schedule_status(d)] += 1

    completed_today = (await db.execute(
        select(func.count()).select_from(InspectionRecord).where(InspectionRecord.performed_at == date.today())
    )).scalar_one()

    return DashboardSummary(
        total=len(due_dates),
        ok=counts["ok"],
        due_soon=counts["due_soon"],
        overdue=counts["overdue"],
        completed_today=completed_today,
    )
