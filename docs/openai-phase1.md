# OpenAI Financial Copilot: Phase 1

> **Current status:** The original phase-1 foundation below has since been extended. The current consent and finance-data retrieval behavior is documented in [phase6-integrations.md](./phase6-integrations.md).

## Existing architecture and AI gap analysis

- The app already had FastAPI, JWT auth, PostgreSQL/SQLAlchemy, Redis, Next.js, and Expo entry points.
- The previous AI capability was only a provider protocol, an explicit tool registry, and generic `ai_interactions`/`ai_tool_calls` audit tables. It did not call a model or expose a chat endpoint.
- No financial account, transaction, portfolio, market quote, or verified news APIs are currently present in the inspected backend. Therefore, this phase does not pass personal financial records to OpenAI and Copilot is instructed to report unavailable data rather than infer it.
- Existing web and mobile clients had no login flow or Copilot interface. Added UI signs in through the existing auth API and keeps the access token in component memory only.

## Dependency and configuration

The backend uses the official OpenAI Python SDK, constrained to the v1 SDK API (`openai>=1.66,<2.0`). Configure the server environment only:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_ENABLED=false
AI_MAX_REQUESTS_PER_USER=20
AI_GLOBAL_MAX_REQUESTS_PER_DAY=1000
AI_MAX_RESPONSE_TOKENS=600
AI_REQUEST_TIMEOUT_SECONDS=25
AI_MAX_PROMPT_CHARACTERS=4000
AI_HISTORY_ENABLED_BY_DEFAULT=false
AI_HISTORY_RETENTION_DAYS=30
AI_REQUEST_LOGGING=false
AI_PRIVACY_MODE=true
```

Set a real key and model using the deployment secret manager, then explicitly enable the feature. The API key is never compiled into either client. Temperature is optional; if a configured model does not support it, leave it unset.

## Database changes

Revision `20260926_000003_ai_copilot` adds:

- `users.ai_history_enabled`
- `ai_conversations` and `ai_messages` for per-user, opt-in history
- `ai_usage` for model, request state, token counts, duration, and error code

Prompts are not copied into usage records. Chat text is stored only when a user enables history; disabling history deletes that user's saved conversations. Usage cost remains null because no authoritative pricing configuration is installed; the platform does not invent a cost estimate.

## Backend and API

OpenAI access is isolated in `backend/app/services/openai_provider.py`; application code uses `AIService` in `backend/app/ai/service.py`. The provider is constructed from server settings and closed after use. Provider exceptions and timeouts produce a generic 503 response; no credentials, prompts, or provider error text are returned.

Authenticated endpoints:

- `POST /api/ai/chat` with `{ "question": "...", "conversation_id": null }`
- `GET /api/ai/history`
- `PUT /api/ai/history` with `{ "enabled": true|false }`
- `GET /api/ai/conversations`
- `GET /api/ai/conversations/{id}`
- `DELETE /api/ai/conversations/{id}`
- `DELETE /api/ai/conversations`
- `GET /api/ai/usage`

Redis enforces daily atomic limits for each user and globally. If Redis is unavailable, Copilot fails closed with 503; the rest of the finance API does not depend on OpenAI or the AI endpoint. Request length, output tokens, SDK timeout, and one SDK retry are bounded/configurable.

AI request logs contain only request ID, user ID, model, timings, token counts, and error category. User text and assistant responses are never written to application logs. `AI_PRIVACY_MODE=true` means saved history is not sent back to OpenAI as context.

## Client changes

- Web Copilot: `/financial-copilot`, linked from the existing dashboard.
- Expo Copilot: added to the existing mobile dashboard.
- Both clients send requests only to FastAPI, hold access tokens in memory, and show generic failures. No OpenAI key or SDK is included client-side.

Set `NEXT_PUBLIC_API_URL` for the web API URL. Mobile reads `EXPO_PUBLIC_API_URL`, then `expo.extra.apiUrl`; the default is the Android emulator's `http://10.0.2.2:8000`.

## Security and data boundaries

- All AI endpoints require the existing authenticated user dependency.
- Conversations are scoped to the authenticated user; other users receive 404.
- External/untrusted content is labeled as untrusted in the model input and cannot override fixed system instructions.
- No transaction, news, market, opportunity, or tool-calling endpoint is connected in this phase. Financial facts absent from explicit verified context must be reported as unavailable.
- No trading, transfer, loan application, SMS interpretation, or other consequential action is available to the model.
- AI remains optional; account operations, reports, and other finance functionality do not call it.

## Testing

Tests mock the provider and do not use API credentials or consume OpenAI credits. They cover authentication, prompt validation, rate limiting, sanitized provider errors, usage recording, opt-in history, history deletion/ownership, and instruction/input boundaries.

```powershell
Set-Location "C:\Users\Administrator\Desktop\New folder\finance-platform\backend"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

## Deployment

Run the `OPENAI_API_KEY`, `OPENAI_MODEL`, and `OPENAI_ENABLED` values only as backend secrets/configuration. Never add them to `web/.env*`, `mobile`, or source control. The new migration runs through the existing Docker backend startup command (`alembic upgrade head`). The Redis service must be available for AI request quotas.

## Phase-1 deferred scope (historical)

This foundation does not yet include finance-data retrieval tools, actual account/transaction/portfolio calculations, AI SMS classification, structured news/opportunity analysis, administrator UI, model/provider administration page, or mobile conversation-history browser. These require existing authoritative data services and are intentionally not simulated here.
