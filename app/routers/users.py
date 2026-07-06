"""User / personnel management endpoints (admin only)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role
from app.models import ROLES, User
from app.schemas import PasswordReset, UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _full_name(first: str | None, last: str | None) -> str:
    return " ".join(p for p in [(first or "").strip(), (last or "").strip()] if p) or "Unnamed"


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    return (await db.execute(select(User).order_by(User.created_at))).scalars().all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {', '.join(ROLES)}")
    if body.email and (await db.execute(select(User.id).where(User.email == body.email))).first():
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    user = User(
        name=_full_name(body.first_name, body.last_name),
        first_name=body.first_name, last_name=body.last_name,
        email=body.email, phone=body.phone, ic=body.ic, position=body.position, remark=body.remark,
        role=body.role,
        password_hash=hash_password(body.password) if body.password else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, body: UserUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(require_role("admin"))):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current.id:
        if body.role is not None and body.role != user.role:
            raise HTTPException(status_code=400, detail="You cannot change your own role (prevents lock-out). Ask another admin.")
        if body.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot disable your own account.")
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(status_code=422, detail=f"role must be one of {', '.join(ROLES)}")
        user.role = body.role
    for f in ("first_name", "last_name", "phone", "ic", "position", "remark"):
        v = getattr(body, f)
        if v is not None:
            setattr(user, f, v)
    if body.first_name is not None or body.last_name is not None:
        user.name = _full_name(user.first_name, user.last_name)
    if body.is_active is not None:
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(user_id: uuid.UUID, body: PasswordReset, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
