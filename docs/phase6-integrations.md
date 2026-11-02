# Phase 6 integrations, notifications, and AI data access

Phase 6 adds optional Daraja M-Pesa flows, a durable notification outbox with provider adapters, and read-only AI retrieval from authoritative finance data. Nothing here is live-configured by default. Configure credentials only in the backend deployment secret store; never put them in the web/mobile client or commit them.

## Database and service configuration

Apply migrations before starting the API:

```powershell
python -m alembic upgrade head
```

Revision `20261102_000007` adds per-user AI data-access consent, notification preferences/devices/deliveries, and M-Pesa mapping/payment tables. The backend environment template contains the optional provider variable names. All provider credentials and the live-payment switch are blank/disabled by default.

## M-Pesa Daraja

The integration supports C2B validation/confirmation callbacks and STK Push. The shortcode is a single platform-managed Paybill/Till: a C2B receipt is a payment made to the platform merchant shortcode and assigned to a user's mapped KES account by its account reference. STK Push asks a user to authorize a merchant payment. Neither flow connects to or synchronizes a user's personal M-Pesa wallet.

1. The shortcode owner configures the Daraja consumer key/secret, shortcode, passkey, public callback base URL, and a random callback token of at least 32 characters.
2. Keep `MPESA_LIVE_PAYMENTS_ENABLED=false` until sandbox flows and reconciliation have been verified. Production requires `MPESA_ENVIRONMENT=production`, `MPESA_ENABLED=true`, and HTTPS callback URLs; only then may the owner explicitly enable live STK payments.
3. Configure each user’s eligible KES account/category mapping through the authenticated integrations UI/API.
4. Register C2B callback URLs from the backend environment:

   ```powershell
   python -m app.integrations.mpesa register-c2b
   ```

5. Redact the callback `token` query parameter in reverse-proxy, CDN, application-access, and observability logs. Callback validation uses a constant-time shared-token comparison; protect and rotate the token as a secret.

Successful callbacks are reconciled idempotently before posting ledger entries. An unmatched or invalid event is not represented as a successful ledger posting. C2B receipts may require manual review; inspect their reconciliation-required status before resolving them. Provider sandbox mocking is tested, but real Daraja account registration, production callbacks, and payments have not been tested.

## Notifications

The authenticated `/api/notifications` API provides the in-app feed, channel preferences, device registration/revocation, delivery status, and bounded retry requests. Budget, M-Pesa, sync, and security events are supported. External email, SMS, and push preferences default off; SMS requires an E.164 profile phone number, and push requires a registered Expo device. The mobile app asks the operating system for notification permission before registering its Expo token.

Configure only the channels the service owner intends to operate:

- Email: `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`
- SMS: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- Push: `EXPO_ACCESS_TOKEN` and the mobile build's `EXPO_PUBLIC_EAS_PROJECT_ID`

External messages use generic content to avoid disclosing ledger details. API background tasks attempt immediate delivery; run the durable outbox worker as a separately supervised backend process for queued/retryable work:

```powershell
python -m app.workers.notification_outbox --once
python -m app.workers.notification_outbox
```

`ACCEPTED` means the provider accepted the request, not that a person received or read it. Provider credentials and end-to-end live delivery remain unconfigured and unverified.

## AI data access and consent

The Financial Copilot can retrieve bounded, read-only context from the authenticated user's own accounts, transactions, budgets, balance-sheet records, and sourced dated valuations. It does not retrieve another user's data, execute financial actions, or treat unsupported prices as live. The user must explicitly enable data access through the Copilot consent control (or authenticated `/api/ai/data-access`) before a chat request can include this context.

AI provider access remains server-side and optional. To enable it, configure the OpenAI API key/model and `OPENAI_ENABLED=true` in the backend secret store, ensure Redis is available for quotas, and keep each user's data-access choice explicit. Consent can be revoked from the UI/API; after revocation, further chat requests are rejected rather than sent with financial context. Do not copy prompts, ledger records, or provider credentials into logs or support tickets.

The AI adapter and retrieval behavior have mocked tests only. No live OpenAI credentials, external model requests, or provider billing have been used for validation.
