"""Pydantic schemas for request validation and response serialisation."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---- auth ----
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    ic: str | None = None
    position: str | None = None
    remark: str | None = None
    role: str
    is_active: bool = True


# ---- users (admin) ----
class UserCreate(BaseModel):
    first_name: str
    last_name: str | None = None
    email: EmailStr
    password: str = Field(min_length=6)
    role: str = "engineer"
    phone: str | None = None
    ic: str | None = None
    position: str | None = None
    remark: str | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    phone: str | None = None
    ic: str | None = None
    position: str | None = None
    remark: str | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6)


# ---- checklist ----
class ReadingDef(BaseModel):
    """A labelled reading field on a checklist item, e.g. code 'IH1'."""
    code: str
    unit: str | None = None


class ReadingVal(BaseModel):
    code: str
    value: str | None = None
    unit: str | None = None


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_no: str
    section: str | None = None
    description: str
    requires_reading: bool
    reading_unit: str | None = None
    readings: list[ReadingDef] = []

    @field_validator("readings", mode="before")
    @classmethod
    def _rd(cls, v):
        return v or []


class ChecklistOut(BaseModel):
    equipment_type: str
    frequency: str
    items: list[ChecklistItemOut]


class TemplateItemIn(BaseModel):
    item_no: str
    section: str | None = None
    description: str
    requires_reading: bool = False
    reading_unit: str | None = None
    readings: list[ReadingDef] = []


class ChecklistTemplateIn(BaseModel):
    equipment_type: str
    frequency: str
    items: list[TemplateItemIn]


class ChecklistTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    equipment_type: str
    frequency: str
    items: list[ChecklistItemOut]


class TemplateSummary(BaseModel):
    id: uuid.UUID
    equipment_type: str
    frequency: str
    item_count: int


# ---- equipment + schedule ----
class ScheduleOut(BaseModel):
    frequency: str
    interval_value: int
    interval_unit: str
    last_done: date | None
    next_due: date
    status: str  # computed: ok / due_soon / overdue
    days_until: int


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tag: str
    name: str
    type: str
    location: str
    site_name: str | None = None
    system: str
    status: str
    cooling_capacity: str | None = None
    unit_type: str | None = None
    qr_token: str
    schedule: ScheduleOut | None = None


class EquipmentCreate(BaseModel):
    # everything optional / custom for production flexibility
    name: str | None = None
    tag: str | None = None
    type: str | None = None
    location: str | None = None
    site_name: str | None = None
    system: str | None = None
    cooling_capacity: str | None = None
    unit_type: str | None = None
    status: str = "Active"
    frequency: str | None = None           # display label, e.g. "3M" or "Weekly"
    interval_value: int | None = None      # if given, overrides parsing of frequency
    interval_unit: str | None = None       # day/week/month/year


class EquipmentUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    location: str | None = None
    site_name: str | None = None
    system: str | None = None
    cooling_capacity: str | None = None
    unit_type: str | None = None
    status: str | None = None
    frequency: str | None = None
    interval_value: int | None = None
    interval_unit: str | None = None


class MetaOut(BaseModel):
    types: list[str]
    systems: list[str]
    unit_types: list[str]
    frequencies: list[str]
    sites: list[str]


# ---- records ----
class ResultIn(BaseModel):
    item_no: str
    section: str | None = None
    description: str
    status: str = Field(description="yes | no | na")
    reading_value: str | None = None
    reading_unit: str | None = None
    readings: list[ReadingVal] = []
    remarks: str | None = None


class MediaIn(BaseModel):
    kind: str = "photo"
    item_no: str | None = None
    data_url: str | None = None       # inline base64 (used when object storage is not configured)
    storage_key: str | None = None    # object-storage key (S3/R2)


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    item_no: str | None = None
    url: str


class RecordCreate(BaseModel):
    equipment_id: uuid.UUID
    overall_status: str = "good"
    frequency: str | None = None
    serviced_by: str | None = None
    checked_by: str | None = None
    signature: str | None = None
    note: str | None = None
    performed_at: date | None = None
    results: list[ResultIn]
    media: list[MediaIn] = []


class ApprovalIn(BaseModel):
    name: str | None = None
    signature: str | None = None
    note: str | None = None


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_no: str
    section: str | None = None
    description: str
    status: str
    reading_value: str | None
    reading_unit: str | None
    readings: list[ReadingVal] = []
    remarks: str | None

    @field_validator("readings", mode="before")
    @classmethod
    def _rd(cls, v):
        return v or []


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    equipment_id: uuid.UUID
    frequency: str
    performed_at: date
    overall_status: str
    site_name: str | None
    serviced_by: str | None
    checked_by: str | None
    signature: str | None
    note: str | None
    approval: str
    manager_name: str | None
    manager_signature: str | None
    manager_note: str | None
    manager_signed_at: datetime | None
    customer_name: str | None
    customer_signature: str | None
    customer_note: str | None
    customer_signed_at: datetime | None
    rejected_by: str | None
    rejected_note: str | None
    report_file: str | None
    created_at: datetime
    results: list[ResultOut]
    media: list[MediaOut] = []


# ---- dashboard ----
class DashboardSummary(BaseModel):
    total: int
    ok: int
    due_soon: int
    overdue: int
    completed_today: int


# ---- media presign ----
class PresignIn(BaseModel):
    filename: str
    content_type: str = "image/jpeg"


class PresignOut(BaseModel):
    upload_url: str
    storage_key: str
