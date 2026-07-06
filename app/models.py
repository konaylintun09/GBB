"""ORM models — the database schema for the Flowea CMMS.

Tables: users, equipment, maintenance_schedule, checklist_template,
checklist_item, inspection_record, inspection_result, media.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Allowed value sets (kept in the app rather than DB enums for easy evolution)
ROLES = ("admin", "engineer", "manager", "customer", "leadership")
FREQUENCIES = ("1M", "3M", "6M", "12M")
FREQ_MONTHS = {"1M": 1, "3M": 3, "6M": 6, "12M": 12}
RESULT_STATUSES = ("yes", "no", "na")
OVERALL_STATUSES = ("good", "attention", "fault")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160))
    first_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ic: Mapped[str | None] = mapped_column(String(40), nullable=True)
    position: Mapped[str | None] = mapped_column(String(80), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="engineer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Equipment(Base):
    __tablename__ = "equipment"
    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=_uuid)
    tag: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(80), index=True)
    location: Mapped[str] = mapped_column(String(160))
    site_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    system: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="Active")
    cooling_capacity: Mapped[str | None] = mapped_column(String(40), nullable=True)  # e.g. "20000 CMH"
    unit_type: Mapped[str | None] = mapped_column(String(20), nullable=True)         # e.g. CHW / DX
    qr_token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    schedule: Mapped["MaintenanceSchedule"] = relationship(
        back_populates="equipment", uselist=False, cascade="all, delete-orphan"
    )


class MaintenanceSchedule(Base):
    __tablename__ = "maintenance_schedule"
    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=_uuid)
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), unique=True, index=True
    )
    frequency: Mapped[str] = mapped_column(String(24))             # display label (admin-owned), e.g. "3M" or "Weekly"
    interval_value: Mapped[int] = mapped_column(Integer, default=1)
    interval_unit: Mapped[str] = mapped_column(String(10), default="month")  # day/week/month/year
    last_done: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due: Mapped[date] = mapped_column(Date, index=True)

    equipment: Mapped[Equipment] = relationship(back_populates="schedule")


class ChecklistTemplate(Base):
    __tablename__ = "checklist_template"
    __table_args__ = (UniqueConstraint("equipment_type", "frequency", name="uq_type_freq"),)
    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=_uuid)
    equipment_type: Mapped[str] = mapped_column(String(80), index=True)
    frequency: Mapped[str] = mapped_column(String(24))

    items: Mapped[list["ChecklistItem"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="ChecklistItem.sort_order"
    )


class ChecklistItem(Base):
    __tablename__ = "checklist_item"
    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=_uuid)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checklist_template.id", ondelete="CASCADE"))
    item_no: Mapped[str] = mapped_column(String(12))
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)   # group heading
    description: Mapped[str] = mapped_column(Text)
    requires_reading: Mapped[bool] = mapped_column(Boolean, default=False)
    reading_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    readings: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)  # [{"code","unit"}] for multi-value items
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    template: Mapped[ChecklistTemplate] = relationship(back_populates="items")


class InspectionRecord(Base):
    """Append-only audit trail of completed maintenance."""
    __tablename__ = "inspection_record"
    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=_uuid)
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id"), index=True)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    frequency: Mapped[str] = mapped_column(String(24))
    performed_at: Mapped[date] = mapped_column(Date, index=True)
    overall_status: Mapped[str] = mapped_column(String(20), default="good")
    site_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    serviced_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    checked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signature: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # approval workflow: submitted -> approved (manager) -> closed (customer); or rejected
    approval: Mapped[str] = mapped_column(String(20), default="submitted")
    manager_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manager_signature: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manager_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_signature: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rejected_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_file: Mapped[str | None] = mapped_column(String(255), nullable=True)   # archived file path once closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    results: Mapped[list["InspectionResult"]] = relationship(
        back_populates="record", cascade="all, delete-orphan"
    )
    media: Mapped[list["Media"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class InspectionResult(Base):
    __tablename__ = "inspection_result"
    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=_uuid)
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_record.id", ondelete="CASCADE"))
    item_no: Mapped[str] = mapped_column(String(12))
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(8))                  # yes / no / na
    reading_value: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reading_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    readings: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)  # [{"code","value","unit"}]
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    record: Mapped[InspectionRecord] = relationship(back_populates="results")


class Media(Base):
    __tablename__ = "media"
    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=_uuid)
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_record.id", ondelete="CASCADE"))
    item_no: Mapped[str | None] = mapped_column(String(12), nullable=True)   # which checklist item (null = general)
    kind: Mapped[str] = mapped_column(String(10), default="photo")  # photo / video
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)   # for S3/R2
    content: Mapped[str | None] = mapped_column(Text, nullable=True)              # inline data URL (no object store)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    record: Mapped[InspectionRecord] = relationship(back_populates="media")

    @property
    def url(self) -> str:
        return self.content or self.storage_key or ""
