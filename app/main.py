from fastapi import FastAPI

from app.api.accounts import router as accounts_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.transfers import router as transfers_router

app = FastAPI(
    title="Mini Bank API",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(transfers_router)
app.include_router(audit_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}