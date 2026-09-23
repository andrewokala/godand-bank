from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models import User
from app.repositories.account import (
    create_account,
    generate_account_number,
    get_account_by_id,
    get_accounts_by_user_id,
)
from app.schemas.account import AccountCreate, AccountResponse
from app.repositories.ledger_entry import (
    get_ledger_entries_by_account_id,
)

from app.schemas.ledger import LedgerEntryListResponse

router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_account(
    account_data: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_number = generate_account_number(db)

    try:
        account = create_account(
            db=db,
            user_id=current_user.id,
            account_number=account_number,
            currency=account_data.currency,
        )
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create account.",
        ) from error

    return account


@router.get(
    "",
    response_model=list[AccountResponse],
)
def get_my_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_accounts_by_user_id(
        db=db,
        user_id=current_user.id,
    )


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
)
def get_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = get_account_by_id(
        db=db,
        account_id=account_id,
    )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account.",
        )

    return account

@router.get(
    "/{account_id}/ledger",
    response_model=LedgerEntryListResponse,
)
def get_account_ledger(
    account_id: UUID,
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = get_account_by_id(
        db=db,
        account_id=account_id,
    )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account.",
        )

    entries, total = get_ledger_entries_by_account_id(
        db=db,
        account_id=account.id,
        limit=limit,
        offset=offset,
    )

    return {
        "items": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
