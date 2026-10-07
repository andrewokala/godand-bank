# godand-bank

A backend banking API built with **FastAPI and PostgreSQL**, designed to demonstrate secure authentication, account management, transactional money transfers, idempotency, concurrency control, double-entry ledger tracking, audit logging, and authorization.

> **Project status:** Core banking functionality implemented and tested.
> **Current test status:** 124 tests passing.

---

## Overview

`godand-bank` is a backend-focused mini banking system built to explore the engineering challenges involved in handling financial transactions safely.

The project focuses on correctness and transaction safety rather than building a complete consumer banking application.

It demonstrates how a banking backend can protect against problems such as:

- Unauthorized account access
- Unauthorized transfers
- Duplicate transaction requests
- Concurrent balance updates
- Race conditions
- Lost updates
- Insufficient funds
- Partial transaction failures
- Inconsistent ledger records
- Token reuse after logout

---

## Features

### Authentication

- User registration
- User login
- JWT access tokens
- Password hashing with bcrypt
- Failed-login tracking
- Account lockout after repeated failed authentication attempts
- Token expiration
- Unique JWT IDs (`jti`)
- Token revocation on logout
- Authentication and authorization dependencies

### Account Management

- Create bank accounts
- Server-side account number generation
- Unique 10-digit account numbers
- Account ownership enforcement
- Account balance tracking
- Account status management
- Account version tracking
- Account currency support

### Transfers

- Money transfers between accounts
- Sender ownership verification
- Receiver validation
- Self-transfer prevention
- Insufficient-balance protection
- Frozen-account protection
- Transfer references
- Transfer status tracking
- Transfer history
- Transfer pagination

### Idempotency

Transfers support idempotency keys to prevent accidental duplicate money movement.

The system detects:

- Repeated requests using the same key and same request
- Reuse of an idempotency key with different request data
- Expired idempotency keys
- Failed transactions that must not leave behind an idempotency record

Concurrent requests using the same idempotency key are also tested.

### Concurrency Control

The transfer engine uses database row locking to protect account balances during concurrent transfers.

The implementation includes:

- `SELECT ... FOR UPDATE` account locking
- Deterministic account-lock ordering
- Protection against lost updates
- Protection against concurrent overdrafts
- Opposite-direction transfer tests
- Concurrent idempotency tests
- Deadlock prevention testing

### Double-Entry Ledger

Every successful transfer produces two ledger entries:

1. Debit entry for the sender
2. Credit entry for the receiver

Ledger records include:

- Account
- Transfer
- Direction
- Amount
- Balance after transaction
- Creation timestamp

The project includes reconciliation tests to verify that account balances remain consistent with ledger balances.

### Audit Logging

Important system actions are recorded in audit logs.

Audit records can contain:

- Acting user
- Action
- IP address
- Metadata
- Timestamp

Users can retrieve their own audit history with pagination.

### Authorization

Authenticated users can only access resources they are authorized to access.

Authorization boundaries are enforced for:

- Accounts
- Account ledgers
- Transfers
- Transfer history
- Audit logs
- Sender accounts during transfers

Cross-user access is covered by automated tests.

---

## Tech Stack

### Backend

- Python
- FastAPI
- Uvicorn

### Database

- PostgreSQL
- SQLAlchemy
- Psycopg
- Alembic

### Authentication & Security

- `python-jose`
- Passlib
- bcrypt
- Pydantic Settings

### Testing

- Pytest
- HTTPX

### Validation

- Pydantic
- email-validator

---

## Architecture

The project follows a layered backend architecture:

```text
Client
  │
  ▼
FastAPI Routes
  │
  ▼
Dependencies / Authentication
  │
  ▼
Services
  │
  ▼
Repositories
  │
  ▼
SQLAlchemy Models
  │
  ▼
PostgreSQL
```

### API Layer

Handles:

- HTTP requests
- Authentication dependencies
- Authorization checks
- Request validation
- HTTP responses
- Pagination parameters

### Service Layer

Contains application/business logic such as:

- Authentication
- Transfers
- Idempotency
- Audit events
- Transfer response construction

### Repository Layer

Handles database operations such as:

- Creating and retrieving accounts
- Retrieving transfers
- Creating ledger entries
- Managing idempotency records
- Managing revoked tokens
- Retrieving audit logs
- Locking database rows

### Model Layer

Contains SQLAlchemy database models representing:

- Users
- Accounts
- Transfers
- Ledger entries
- Audit logs
- Idempotency keys
- Revoked tokens

### Schema Layer

Contains Pydantic request and response schemas used by the API.

---

## Project Structure

```text
godand-bank/
│
├── app/
│   ├── api/
│   │   ├── accounts.py
│   │   ├── audit.py
│   │   ├── auth.py
│   │   ├── dependencies.py
│   │   └── transfers.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   │
│   ├── db/
│   │   ├── dependencies.py
│   │   └── session.py
│   │
│   ├── models/
│   │   ├── account.py
│   │   ├── audit_log.py
│   │   ├── idempotency_key.py
│   │   ├── ledger_entry.py
│   │   ├── revoked_token.py
│   │   ├── transfer.py
│   │   └── user.py
│   │
│   ├── repositories/
│   │   ├── account.py
│   │   ├── audit_log.py
│   │   ├── idempotency.py
│   │   ├── ledger_entry.py
│   │   ├── revoked_token.py
│   │   ├── transfer.py
│   │   └── user.py
│   │
│   ├── schemas/
│   │   ├── account.py
│   │   ├── audit.py
│   │   ├── ledger.py
│   │   ├── transfer.py
│   │   └── user.py
│   │
│   ├── services/
│   │   ├── audit.py
│   │   ├── auth.py
│   │   ├── idempotency.py
│   │   ├── transfer.py
│   │   └── transfer_response.py
│   │
│   └── main.py
│
├── alembic/
│   ├── versions/
│   └── env.py
│
├── tests/
│
├── .env
├── .gitignore
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## API Endpoints

The API currently exposes the following endpoints.

### Authentication

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| POST | `/auth/register` | No | Register a new user |
| POST | `/auth/login` | No | Authenticate and receive an access token |
| POST | `/auth/logout` | Yes | Revoke the current access token |

### Accounts

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| POST | `/accounts` | Yes | Create an account |
| GET | `/accounts` | Yes | List the authenticated user's accounts |
| GET | `/accounts/{account_id}` | Yes | Retrieve an owned account |
| GET | `/accounts/{account_id}/ledger` | Yes | Retrieve an account's ledger |

Ledger pagination:

```text
GET /accounts/{account_id}/ledger?limit=20&offset=0
```

- `limit`: 1–100
- `offset`: 0 or greater

### Transfers

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| POST | `/transfers` | Yes | Create a transfer |
| GET | `/transfers` | Yes | Retrieve the user's transfer history |
| GET | `/transfers/{transfer_id}` | Yes | Retrieve an accessible transfer |

Transfer history pagination:

```text
GET /transfers?limit=20&offset=0
```

Creating a transfer requires an idempotency key:

```text
POST /transfers?idempotency_key=<unique-key>
```

### Audit Logs

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| GET | `/audit-logs` | Yes | Retrieve the authenticated user's audit logs |

Example:

```text
GET /audit-logs?limit=20&offset=0
```

### Health Check

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| GET | `/health` | No | Check whether the API is responding |

Example response:

```json
{
  "status": "ok"
}
```

---

## Database

The project uses **PostgreSQL** with **SQLAlchemy** as the ORM.

Database schema changes are managed with **Alembic**.

The current migration chain includes migrations for:

- Initial banking schema
- Failed-login count constraint
- Account version constraint
- Transfer currency constraint
- Revoked-token storage

The database is currently at the latest Alembic migration.

Useful commands:

```bash
alembic current
```

Check whether the database is synchronized:

```bash
alembic check
```

Apply migrations:

```bash
alembic upgrade head
```

---

## Environment Variables

Create a `.env` file in the project root.

Example:

```env
DATABASE_URL=your_database_url
SECRET_KEY=your_secret_key
```

Do not commit real credentials or secrets to Git.

---

## Installation

Clone the repository and enter the project directory:

```bash
git clone <repository-url>
cd godand-bank
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the `.env` file with the required database URL and secret key.

Run database migrations:

```bash
alembic upgrade head
```

---

## Running the API

Start the development server:

```bash
uvicorn app.main:app --reload
```

The API will normally be available at:

```text
http://127.0.0.1:8000
```

FastAPI automatically provides interactive API documentation at:

```text
/docs
```

and alternative documentation at:

```text
/redoc
```

---

## Testing

Run the complete test suite:

```bash
pytest -v
```

The current verified result is:

```text
124 passed
```

The test suite covers:

- Authentication
- Authorization
- Account management
- Transfer behavior
- Transfer history
- Idempotency
- Concurrent transfers
- Authentication concurrency
- Transaction rollback
- Atomicity
- Double-entry ledger behavior
- Audit logging
- Repository behavior
- Database models
- API schemas
- JWT security
- Revoked tokens
- Pagination
- Ownership boundaries

---

## Transaction Safety

Transfers are designed to execute atomically.

A successful transfer updates:

```text
Sender Account
      │
      ├── Debit
      │
      ▼
Transfer Record
      │
      ├── Sender Ledger Entry
      └── Receiver Ledger Entry
```

If an important part of the transaction fails, the database transaction is rolled back so that partial money movement is not persisted.

The project contains explicit atomicity tests covering rollback scenarios.

---

## Concurrency Safety

The transfer service locks both accounts before modifying balances.

The accounts are locked in a deterministic order to avoid circular lock acquisition when two transfers occur in opposite directions.

For example:

```text
Transfer A → B
Transfer B → A
```

Both operations use the same account-lock ordering strategy.

The project includes concurrency tests for:

- Concurrent successful transfers
- Concurrent overdraft attempts
- Opposite-direction transfers
- Concurrent use of the same idempotency key

---

## Idempotency

Each transfer requires a unique idempotency key.

The system stores a request hash associated with the key.

This allows the backend to distinguish between:

```text
Same key + same request
```

and:

```text
Same key + different request
```

The first can safely return the existing transaction, while the second is rejected.

Expired idempotency keys cannot be reused for another transfer.

---

## Authentication Security

Access tokens contain:

- `sub`
- `iat`
- `exp`
- `jti`
- `type`

Tokens are signed using the configured secret key and algorithm.

Logout records the token's JTI as revoked until its expiration time.

Authentication also tracks failed login attempts and locks accounts after repeated failures.

---

## Authorization

Authorization is enforced at the application level.

Users cannot:

- View another user's account
- View another user's ledger
- Transfer money from another user's account
- View unrelated transfers
- View another user's audit logs

These boundaries are covered by automated tests.

---

## API Documentation

When the application is running, FastAPI provides interactive documentation.

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

The `/docs` interface can be used to inspect request schemas, response schemas, authentication requirements, and available endpoints.

---

## Current Project Status

### Completed

- Authentication
- JWT security
- Logout/token revocation
- Account management
- Server-side account number generation
- Transfer processing
- Transfer history
- Idempotency
- Transaction rollback protection
- Concurrency protection
- Double-entry ledger
- Ledger reconciliation
- Audit logging
- Pagination
- Authorization boundaries
- Automated testing
- Database migrations
- Repository/service/API separation

### Test Status

```text
124 tests passed
2 warnings
```

The remaining warnings are dependency-related deprecation warnings and do not currently cause test failures.

---

## Important Note

This project is an educational/backend engineering project demonstrating banking transaction concepts.

It should **not** be treated as a production-ready banking platform or connected to real customer funds without additional security, compliance, operational, monitoring, infrastructure, and regulatory work.

---

## Development Philosophy

The project emphasizes:

- Correctness before convenience
- Explicit transaction boundaries
- Database-enforced constraints
- Authorization at resource boundaries
- Idempotent financial operations
- Concurrency safety
- Atomic state changes
- Auditable transactions
- Automated regression testing
- Clear separation between API, service, repository, and model layers
