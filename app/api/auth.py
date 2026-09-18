from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.dependencies import get_db
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
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            email=user_data.email,
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