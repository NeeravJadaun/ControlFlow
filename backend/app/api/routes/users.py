from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_correlation_id, get_current_user, get_db, require_roles
from app.core.security import hash_password
from app.models.enums import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserOut
from app.services.audit_log import record_audit

router = APIRouter()


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[User]:
    return list(db.execute(select(User).order_by(User.full_name)).scalars().all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
    correlation_id: str = Depends(get_correlation_id),
) -> User:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        actor_id=admin.id,
        entity_type="user",
        entity_id=user.id,
        action="create",
        after={"email": user.email, "role": user.role.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(user)
    return user
