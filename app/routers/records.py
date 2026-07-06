"""Inspection record endpoints — submit, list, and the approval workflow."""
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import require_role
from app.models import Equipment, InspectionRecord, InspectionResult, Media, User
from app.schemas import ApprovalIn, RecordCreate, RecordOut
from app.util import next_due_from

router = APIRouter(prefix="/records", tags=["records"])


@router.post("", response_model=RecordOut, status_code=status.HTTP_201_CREATED)
async def submit_record(
    body: RecordCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "engineer")),
):
    eq = (await db.execute(
        select(Equipment).where(Equipment.id == body.equipment_id).options(selectinload(Equipment.schedule))
    )).scalar_one_or_none()
    if eq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    if eq.schedule is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Equipment has no maintenance schedule")

    performed = body.performed_at or date.today()
    frequency = body.frequency or eq.schedule.frequency

    record = InspectionRecord(
        equipment_id=eq.id,
        technician_id=user.id,
        frequency=frequency,
        performed_at=performed,
        overall_status=body.overall_status,
        site_name=eq.site_name,
        serviced_by=body.serviced_by,
        checked_by=body.checked_by or user.name,
        signature=body.signature,
        note=body.note,
        approval="submitted",
        results=[
            InspectionResult(
                item_no=r.item_no, section=r.section, description=r.description, status=r.status,
                reading_value=r.reading_value, reading_unit=r.reading_unit,
                readings=[rv.model_dump() for rv in r.readings] if r.readings else [],
                remarks=r.remarks,
            ) for r in body.results
        ],
        media=[Media(kind=m.kind, item_no=m.item_no, content=m.data_url, storage_key=m.storage_key) for m in body.media],
    )
    db.add(record)

    eq.schedule.last_done = performed
    eq.schedule.next_due = next_due_from(performed, eq.schedule.interval_value, eq.schedule.interval_unit)

    await db.commit()
    await db.refresh(record, attribute_names=["results", "media"])
    return record


@router.get("", response_model=list[RecordOut])
async def list_records(
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "leadership", "manager", "customer", "engineer")),
):
    q = (select(InspectionRecord).options(selectinload(InspectionRecord.results), selectinload(InspectionRecord.media))
         .order_by(InspectionRecord.created_at.desc()).limit(limit))
    if user.role == "engineer":
        q = q.where(InspectionRecord.technician_id == user.id)  # engineers see only their own
    rows = (await db.execute(q)).scalars().all()
    return rows


async def _get(db, record_id) -> InspectionRecord:
    rec = (await db.execute(
        select(InspectionRecord).where(InspectionRecord.id == record_id).options(selectinload(InspectionRecord.results), selectinload(InspectionRecord.media))
    )).scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return rec


@router.post("/{record_id}/approve", response_model=RecordOut)
async def manager_approve(
    record_id: uuid.UUID, body: ApprovalIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "manager")),
):
    """Manager review & sign. Approves the report and forwards it to the customer."""
    rec = await _get(db, record_id)
    rec.manager_name = body.name or user.name
    rec.manager_signature = body.signature
    rec.manager_note = body.note
    rec.manager_signed_at = datetime.now(timezone.utc)
    rec.rejected_by = None
    rec.rejected_note = None
    rec.approval = "approved"
    await db.commit()
    await db.refresh(rec, attribute_names=["results", "media"])
    return rec


@router.post("/{record_id}/customer-sign", response_model=RecordOut)
async def customer_sign(
    record_id: uuid.UUID, body: ApprovalIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "customer")),
):
    """Customer review & sign-off. Closes the report once agreed."""
    rec = await _get(db, record_id)
    if rec.approval not in ("approved",):
        raise HTTPException(status_code=400, detail="Awaiting manager approval before customer sign-off")
    rec.customer_name = body.name or user.name
    rec.customer_signature = body.signature
    rec.customer_note = body.note
    rec.customer_signed_at = datetime.now(timezone.utc)
    rec.approval = "closed"
    # archive the closed report to app/files_data
    eq = await db.get(Equipment, rec.equipment_id)
    try:
        from app.reportgen import archive_report
        rec.report_file = archive_report(rec, eq)
    except Exception:
        rec.report_file = None
    await db.commit()
    await db.refresh(rec, attribute_names=["results", "media"])
    return rec


@router.get("/{record_id}/file")
async def get_report_file(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "leadership", "manager", "customer", "engineer")),
):
    """Download the archived HTML report file for a closed record."""
    import os
    from fastapi.responses import FileResponse
    rec = await db.get(InspectionRecord, record_id)
    if rec is None or not rec.report_file:
        raise HTTPException(status_code=404, detail="No archived file for this report")
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), rec.report_file)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Archived file missing on disk")
    return FileResponse(path, media_type="text/html", filename=os.path.basename(path))


@router.post("/{record_id}/reject", response_model=RecordOut)
async def reject(
    record_id: uuid.UUID, body: ApprovalIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "manager", "customer")),
):
    """Send a report back (e.g. blank/insufficient remarks) with a reason."""
    rec = await _get(db, record_id)
    rec.rejected_by = body.name or f"{user.name} ({user.role})"
    rec.rejected_note = body.note
    rec.approval = "rejected"
    await db.commit()
    await db.refresh(rec, attribute_names=["results", "media"])
    return rec
