from pydantic import BaseModel


class AccountProfile(BaseModel):
    full_name: str
    account_number: str
    balance: str
    currency: str
    status: str