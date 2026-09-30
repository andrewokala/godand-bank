from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_token_payload, get_current_user
from app.core.security import create_access_token
from app.db.dependencies import get_db
from app.models import User
from app.repositories.revoked_token import revoke_token
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth import authenticate_user, register_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    try:
        return register_user(
            db=db,
            full_name=user_data.full_name,
            email=user_data.email,
            phone=user_data.phone,
            password=user_data.password,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Unable to create user.",
        ) from error


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    try:
        user = authenticate_user(
            db=db,
            email=user_data.email,
            password=user_data.password,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error),
        ) from error

    access_token = create_access_token(
        user_id=user.id,
    )

    return TokenResponse(
        access_token=access_token,
    )


@router.post(
    "/logout",
)
def logout(
    payload: dict = Depends(get_current_token_payload),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expires_at = datetime.fromtimestamp(
        payload["exp"],
        tz=UTC,
    )

    revoke_token(
        db=db,
        jti=payload["jti"],
        user_id=user.id,
        expires_at=expires_at,
    )

    db.commit()

    return {
        "message": "Logged out successfully.",
    }
