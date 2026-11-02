import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.ai.service import AIService, AIUnavailable
from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.ai_usage import AIUsage
from app.models.user import User
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    AIConversationDetail,
    AIConversationOut,
    AIDataAccessPreference,
    AIHistoryPreference,
    AIMessageOut,
    AIUsageSummary,
)
from app.services.ai_service import create_ai_service
from app.services.ai_retrieval import build_verified_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["financial copilot"])

_RATE_LIMIT_SCRIPT = """
local user_count = tonumber(redis.call('GET', KEYS[1]) or '0')
local global_count = tonumber(redis.call('GET', KEYS[2]) or '0')
local user_limit = tonumber(ARGV[1])
local global_limit = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
if user_count >= user_limit or global_count >= global_limit then
    return 0
end
user_count = redis.call('INCR', KEYS[1])
global_count = redis.call('INCR', KEYS[2])
if user_count == 1 then redis.call('EXPIRE', KEYS[1], ttl) end
if global_count == 1 then redis.call('EXPIRE', KEYS[2], ttl) end
return 1
"""


class AIRateLimiter:
    async def acquire(self, user_id: int, now: datetime) -> bool:
        seconds_until_reset = max(1, int((now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 86400) - now.timestamp()))
        date_key = now.strftime("%Y-%m-%d")
        user_key = f"ai:quota:user:{user_id}:{date_key}"
        global_key = f"ai:quota:global:{date_key}"
        try:
            async with Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            ) as redis:
                result = await redis.eval(
                    _RATE_LIMIT_SCRIPT,
                    2,
                    user_key,
                    global_key,
                    settings.ai_max_requests_per_user,
                    settings.ai_global_max_requests_per_day,
                    seconds_until_reset,
                )
        except RedisError as exc:
            raise AIUnavailable("Financial Copilot rate limiter is unavailable") from exc
        return bool(result)


def get_ai_service_dependency() -> AIService:
    try:
        return create_ai_service()
    except AIUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Financial Copilot is unavailable") from exc


def get_ai_rate_limiter() -> AIRateLimiter:
    return AIRateLimiter()


def _conversation_for_user(db: Session, conversation_id: int, user_id: int) -> AIConversation:
    conversation = db.query(AIConversation).filter(
        AIConversation.id == conversation_id,
        AIConversation.user_id == user_id,
    ).first()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.get("/history")
def get_history_preference(current_user: User = Depends(get_current_user)):
    return {"enabled": current_user.ai_history_enabled}


@router.put("/history")
def update_history_preference(
    payload: AIHistoryPreference,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.ai_history_enabled = payload.enabled
    if not payload.enabled:
        db.query(AIConversation).filter(AIConversation.user_id == current_user.id).delete(synchronize_session=False)
    db.commit()
    return {"enabled": current_user.ai_history_enabled}


@router.get("/data-access")
def get_data_access_preference(current_user: User = Depends(get_current_user)):
    return {"enabled": current_user.ai_data_access_enabled}


@router.put("/data-access")
def update_data_access_preference(
    payload: AIDataAccessPreference,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.ai_data_access_enabled = payload.enabled
    db.commit()
    return {"enabled": current_user.ai_data_access_enabled}


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    payload: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_service: AIService = Depends(get_ai_service_dependency),
    rate_limiter: AIRateLimiter = Depends(get_ai_rate_limiter),
):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question cannot be blank")
    if len(question) > settings.ai_max_prompt_characters:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Question exceeds the configured size limit")
    if not current_user.ai_data_access_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enable financial-data access before sending a question to the configured AI provider",
        )
    if payload.conversation_id is not None and not current_user.ai_history_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enable chat history before continuing a saved conversation")

    now = datetime.now(timezone.utc)
    try:
        permitted = await rate_limiter.acquire(current_user.id, now)
    except AIUnavailable as exc:
        await ai_service.aclose()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Financial Copilot is unavailable") from exc
    if not permitted:
        await ai_service.aclose()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Financial Copilot request limit reached")

    conversation = None
    is_new_conversation = False
    if current_user.ai_history_enabled:
        retention_cutoff = now - timedelta(days=settings.ai_history_retention_days)
        db.query(AIConversation).filter(
            AIConversation.user_id == current_user.id,
            AIConversation.updated_at < retention_cutoff,
        ).delete(synchronize_session=False)
        if payload.conversation_id is not None:
            conversation = _conversation_for_user(db, payload.conversation_id, current_user.id)
        else:
            conversation = AIConversation(user_id=current_user.id)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            is_new_conversation = True

    conversation_history: list[dict[str, str]] = []
    if conversation is not None and not settings.ai_privacy_mode:
        previous = (
            db.query(AIMessage)
            .filter(AIMessage.conversation_id == conversation.id)
            .order_by(AIMessage.created_at.desc())
            .limit(8)
            .all()
        )
        conversation_history = [
            {"role": message.role, "content": message.content[: settings.ai_max_prompt_characters]}
            for message in reversed(previous)
        ]

    verified_context, source_references = build_verified_context(db, current_user.id)
    usage = AIUsage(
        request_id=str(uuid4()),
        user_id=current_user.id,
        conversation_id=conversation.id if conversation is not None else None,
        model_name=ai_service.provider.model_name,
        status="STARTED",
    )
    db.add(usage)
    db.commit()
    started = time.perf_counter()

    try:
        answer = await asyncio.wait_for(
            ai_service.answer(
                question,
                {
                    "verified_context": verified_context,
                    "conversation_history": conversation_history,
                    "source_references": source_references,
                },
                max_output_tokens=settings.ai_max_response_tokens,
            ),
            timeout=settings.ai_request_timeout_seconds + 1,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        usage.status = "SUCCEEDED"
        usage.input_tokens = answer.input_tokens
        usage.output_tokens = answer.output_tokens
        usage.duration_ms = duration_ms

        if conversation is not None:
            db.add(AIMessage(conversation_id=conversation.id, role="user", content=question))
            db.add(AIMessage(conversation_id=conversation.id, role="assistant", content=answer.text, model_name=answer.model_name))
            conversation.updated_at = datetime.now(timezone.utc)

        db.commit()
        if settings.ai_request_logging:
            logger.info(
                "ai_request_succeeded request_id=%s user_id=%s model=%s duration_ms=%s input_tokens=%s output_tokens=%s",
                usage.request_id,
                current_user.id,
                answer.model_name,
                duration_ms,
                answer.input_tokens,
                answer.output_tokens,
            )
        return AIChatResponse(
            answer=answer.text,
            provider=answer.provider_key,
            model=answer.model_name,
            conversation_id=conversation.id if conversation is not None else None,
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
            sources=answer.source_references,
        )
    except (AIUnavailable, asyncio.TimeoutError) as exc:
        usage.status = "FAILED"
        usage.error_code = "TIMEOUT" if isinstance(exc, asyncio.TimeoutError) else "PROVIDER_UNAVAILABLE"
        usage.duration_ms = int((time.perf_counter() - started) * 1000)
        if is_new_conversation and conversation is not None:
            db.delete(conversation)
        db.commit()
        logger.warning("ai_request_failed request_id=%s user_id=%s code=%s", usage.request_id, current_user.id, usage.error_code)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Financial Copilot is temporarily unavailable") from exc
    except Exception as exc:
        usage.status = "FAILED"
        usage.error_code = "INTERNAL_ERROR"
        usage.duration_ms = int((time.perf_counter() - started) * 1000)
        if is_new_conversation and conversation is not None:
            db.delete(conversation)
        db.commit()
        logger.error("ai_request_failed request_id=%s user_id=%s code=INTERNAL_ERROR", usage.request_id, current_user.id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Financial Copilot is temporarily unavailable") from exc
    finally:
        await ai_service.aclose()


@router.get("/conversations", response_model=list[AIConversationOut])
def list_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.ai_history_enabled:
        return []
    return db.query(AIConversation).filter(AIConversation.user_id == current_user.id).order_by(AIConversation.updated_at.desc()).all()


@router.get("/conversations/{conversation_id}", response_model=AIConversationDetail)
def get_conversation(conversation_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.ai_history_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conversation = _conversation_for_user(db, conversation_id, current_user.id)
    messages = db.query(AIMessage).filter(AIMessage.conversation_id == conversation.id).order_by(AIMessage.created_at).all()
    return AIConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=messages,
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = _conversation_for_user(db, conversation_id, current_user.id)
    db.delete(conversation)
    db.commit()


@router.delete("/conversations", status_code=status.HTTP_204_NO_CONTENT)
def clear_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(AIConversation).filter(AIConversation.user_id == current_user.id).delete(synchronize_session=False)
    db.commit()


@router.get("/usage", response_model=AIUsageSummary)
def get_usage(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today = db.query(AIUsage).filter(AIUsage.user_id == current_user.id, AIUsage.created_at >= day_start).count()
    month_rows = db.query(AIUsage).filter(AIUsage.user_id == current_user.id, AIUsage.created_at >= month_start).all()
    return AIUsageSummary(
        requests_today=today,
        requests_this_month=len(month_rows),
        input_tokens_this_month=sum(row.input_tokens or 0 for row in month_rows),
        output_tokens_this_month=sum(row.output_tokens or 0 for row in month_rows),
        failed_requests_this_month=sum(row.status == "FAILED" for row in month_rows),
    )
