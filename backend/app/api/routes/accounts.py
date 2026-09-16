from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.entity import Account
from app.models.user import User
from app.schemas.common import Page
from app.schemas.entity import AccountOut

router = APIRouter()


@router.get("", response_model=Page[AccountOut])
def list_accounts(
    entity_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page:
    stmt = select(Account)
    if entity_id:
        stmt = stmt.where(Account.entity_id == entity_id)
    if status_filter:
        stmt = stmt.where(Account.status == status_filter)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Account.id).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=list(rows), total=total, page=page, page_size=page_size)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    return account
