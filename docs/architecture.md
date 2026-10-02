# System architecture

## Overview

The platform is structured as a monorepo with a single shared backend service and separate client applications for web and Android.

## Runtime architecture

```text
WEB APP (Next.js)      MOBILE APP (Expo)
        |                    |
        +---------|----------+
                  |
                  v
             REST API (FastAPI)
                  |
          +-------+--------+
          |                |
          v                v
     PostgreSQL        Redis
          |
          v
    Object storage abstraction
```

## Separation of concerns

- Web: user dashboard, analytics, settings, and configuration
- Mobile: mobile-first access, pending detections, review workflows, and notifications
- Backend: authentication, profiles, account logic, financial rules, and API orchestration
- Database: source of truth for all persisted financial records and audit data
- Storage: non-relational binary assets such as profile images and supporting media

## Persistence model

- PostgreSQL keeps the relational financial data model.
- Redis is reserved for caches, rate limiting, and optional queues.
- File/object storage handles profile photos and future document attachments.

## Security model

- Passwords never stored as plain text.
- JWTs are short-lived and used for access.
- Refresh tokens are stored with hashes and can be revoked.
- Authenticated requests use HTTP Bearer tokens.
- File uploads are validated before acceptance.

## Deployment model

- Local: Docker Compose for backend, database, and Redis
- Production: Vercel for web, Render/AWS/GCP for backend, managed PostgreSQL, object storage, and managed Redis
