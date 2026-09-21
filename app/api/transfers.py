from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models import User
from app.repositories.account import (
    get_account_by_number,
    get_accounts_by_user_id,
)
from app.schemas.transfer import TransferCreate, TransferResponse
from app.services.transfer import transfer

router = APIRouter(
    prefix="/transfers",
    tags=["Transfers"],
)


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transfer(
    transfer_data: TransferCreate,
    idempotency_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = get_accounts_by_user_id(
        db=db,
        user_id=current_user.id,
    )

    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender account not found.",
        )

    sender = accounts[0]

    receiver = get_account_by_number(
        db=db,
        account_number=transfer_data.receiver_account_number,
    )

    if receiver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver account not found.",
        )

    try:
        transfer_record = transfer(
            db=db,
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            sender_account_number=sender.account_number,
            receiver_account_number=receiver.account_number,
            amount=transfer_data.amount,
            currency=sender.currency,
            note=transfer_data.note,
        )

    except ValueError as error:
        message = str(error)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            ) from error

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        ) from error

    return transfer_record