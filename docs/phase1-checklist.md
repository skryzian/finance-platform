# Phase 1 checklist

This document records the required Phase 1 scope and the exact status of each item.

## Included

- Monorepo root and directory structure
- Docker Compose with PostgreSQL, Redis, backend, web, and mobile skeletons
- FastAPI backend and health endpoint
- PostgreSQL + SQLAlchemy connection setup
- User model and session model
- Authentication foundation with password hashing and JWT tokens
- Basic profile endpoints
- Profile photo architecture and upload abstraction
- Environment templates and documentation
- README and architecture docs

## Deferred

- Accounts, budgets, transactions, and net worth modules
- SMS detection engine
- Import logic
- Dashboard analytics
- Production hardening
- Deployment-specific infrastructure

## Validation required from user

The user should confirm that the following commands work in their environment:

1. `docker compose up --build`
2. `http://localhost:8000/health`
3. `http://localhost:3000`
4. API register/login flow via Swagger docs or test clients

Once confirmed, Phase 2 may proceed.
