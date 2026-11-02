# Security Audit

**Assessment date:** 2026-11-02  
**Method:** Static inspection of first-party code/configuration plus the existing backend tests. No penetration test, live deployment, secret-validity check, or third-party dependency scan was performed.

> **Remediation status:** This document records the pre-remediation findings. The environment templates have been sanitized; upload names/path/content/size are constrained; production now rejects weak/default/equal JWT secrets; refresh rotation and session-bound access-token revocation are implemented; and the unused Android SMS permission was removed. Authentication throttling and configured remote object storage remain outstanding. Active secrets that may have appeared in earlier templates must still be rotated by the owner; deployments and repository history were not inspected.

## Findings

### S-01 - Credential-like values in a shared environment template

- **Severity:** Critical until revoked; validity is unverified.
- **Location:** Root [.env.example](./.env.example), including credential-bearing entries around lines 3 and 10-14.
- **Status:** Confirmed in the working copy; do not reproduce the values.
- **Technical detail / impact:** An example template contains non-placeholder values matching database/JWT/provider credential formats. If any remain valid or this file has been shared/committed, an unauthorized party could use provider accounts or forge tokens depending on the credential. The repository status showed this file already modified when the audit began; it was not changed during this audit.
- **Remediation:** Immediately revoke/rotate every possibly real credential, including JWT signing secrets; inspect repository history and deployment logs; replace values with blank or clearly fake placeholders; add secret scanning and a commit/CI block. Treat values as compromised even if current validity is unknown.

### S-02 - User-supplied photo filename is joined into a writable path

- **Severity:** High
- **Location:** [profile.py](./backend/app/api/routes/profile.py#L58) and [storage.py](./backend/app/storage/storage.py#L22)
- **Status:** Confirmed code path; exploitation was not attempted.
- **Technical detail / impact:** The authenticated upload route builds a storage key from `UploadFile.filename`. `LocalStorageProvider` joins that key under `.storage` without resolving it and checking that it remains beneath the storage root. Traversal components can escape the intended directory and overwrite files writable by the backend process. The app allows public self-registration, so authentication alone is not a sufficient trust boundary.
- **Remediation:** Generate opaque server-side object names; discard the client path/basename; resolve the destination and assert it remains under the configured root; use a dedicated non-writable application directory or object-storage SDK; add tests for traversal and symlink cases. Run the container as a non-root user.

### S-03 - Production may use predictable default JWT secrets

- **Severity:** High when deployment omits secrets
- **Location:** [config.py](./backend/app/core/config.py#L12)
- **Status:** Confirmed fallback; whether any deployed environment uses it is unknown.
- **Technical detail / impact:** Settings silently default to fixed, publicly known signing strings. There is no production-mode validator requiring strong distinct secrets. A deployment missing environment configuration may accept forged JWTs.
- **Remediation:** Make both secrets required in production, reject defaults and weak/equal values at startup, generate separate high-entropy secrets in a managed secret store, and rotate exposed values.

### S-04 - Refresh-token/session lifecycle is incomplete and logout is not immediate

- **Severity:** High
- **Location:** [auth.py](./backend/app/api/routes/auth.py#L77), [auth.py](./backend/app/api/routes/auth.py#L86), [auth.py](./backend/app/api/routes/auth.py#L91), and [deps.py](./backend/app/api/deps.py)
- **Status:** Confirmed code behavior.
- **Technical detail / impact:** Login stores `expires_at` as the current timestamp. The refresh route always returns 501. Logout deletes session records, but bearer authentication only verifies the signed access JWT and does not consult session/revocation state. Consequently refresh cannot work, and an already issued access token remains accepted until its JWT expiry (currently one hour).
- **Remediation:** Implement refresh-token rotation with hashed opaque tokens, expiry/revocation checks and reuse detection; link access-token validity to revocation strategy or use short-lived access tokens with a documented residual window; have logout revoke the current session and test replay/revocation cases.

### S-05 - Upload validation does not establish file content or bound request ingestion

- **Severity:** Medium
- **Location:** [profile.py](./backend/app/api/routes/profile.py#L50) and [profile.py](./backend/app/api/routes/profile.py#L54)
- **Status:** Confirmed validation approach; resource-exhaustion impact depends on proxy/server limits.
- **Technical detail / impact:** The route trusts the multipart MIME declaration and enforces a 5 MB check only after the multipart parser has received/spooled the upload. A forged MIME value may store non-image content, while oversized requests can consume temporary storage before rejection.
- **Remediation:** Enforce request/file limits at the reverse proxy and application boundary, inspect file signatures with a safe image decoder, re-encode allowed images, strip metadata, and test oversized/invalid uploads. Do not rely on filename extensions or client-provided MIME.

### S-06 - Authentication endpoints have no visible rate limiting

- **Severity:** Medium
- **Location:** [auth.py](./backend/app/api/routes/auth.py#L19) and [auth.py](./backend/app/api/routes/auth.py#L61)
- **Status:** No limiter is present in the route code; upstream controls were not inspected.
- **Technical detail / impact:** Registration/login can be used for credential stuffing, password guessing, and account enumeration. Login responses are generic, but registration distinguishes an already-registered email.
- **Remediation:** Add IP and account-aware throttling, progressive delays/abuse monitoring, generic registration responses where appropriate, and operational alerting. Avoid permanent lockouts that enable denial of service.

### S-07 - Unneeded Android SMS permission is declared

- **Severity:** Low/Medium
- **Location:** [app.json](./mobile/app.json#L21)
- **Status:** Confirmed manifest configuration; no SMS-reading implementation was found in the reviewed mobile source.
- **Technical detail / impact:** `READ_SMS` is highly sensitive, unnecessary for the current UI, and subject to platform/store restrictions. An unused permission increases user concern and review friction.
- **Remediation:** Remove the permission until a separately approved SMS feature exists; if added later, use a clear consent and data-minimization design, platform policy review, and explicit local-only processing rules.

## Existing controls observed

- Passwords use Passlib bcrypt hashing in [security.py](./backend/app/core/security.py).
- Most private routes use the bearer-token `get_current_user` dependency.
- Watchlists and conversations are scoped to the current user; conversation ownership is tested.
- AI is disabled by default, receives empty verified finance context in the current endpoint, and uses an allowlisted tool registry that is not wired to a database session.
- Chat history is opt-in and can be deleted; AI provider errors are returned in sanitized form and tested.
- CORS origins are configurable and are not a wildcard in the supplied Render blueprint.

These are useful foundations, not proof of end-to-end security.

## Security checks not completed

- No live endpoint penetration test, TLS/certificate check, CORS/browser test, production secret inspection, or database authorization test.
- No dependency scanner result: `npm audit` could not run because `web` has no lockfile; no Python advisory scanner was available/run.
- No confirmation that template values are active or that the file is publicly accessible.
- No upload exploit attempt was made; the finding is based on the path construction and storage implementation.
