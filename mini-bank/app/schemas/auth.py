from pydantic import BaseModel, EmailStr, Field

from app.schemas.account import AccountProfile

class SignupRequest(BaseModel):
    fulL_name: str
    email: EmailStr
    phone: str
    password: str = Field(min_length=8)
    terms_accpeted: bool


class AuthRequest(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    account: AccountProfile