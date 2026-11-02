from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AIChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    conversation_id: int | None = Field(default=None, gt=0)


class AIChatResponse(BaseModel):
    answer: str
    provider: str
    model: str
    conversation_id: int | None
    input_tokens: int | None
    output_tokens: int | None
    sources: list[dict[str, str]] = Field(default_factory=list)


class AIHistoryPreference(BaseModel):
    enabled: bool


class AIDataAccessPreference(BaseModel):
    enabled: bool


class AIConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIMessageOut(BaseModel):
    id: int
    role: str
    content: str
    model_name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIConversationDetail(AIConversationOut):
    messages: list[AIMessageOut]


class AIUsageSummary(BaseModel):
    requests_today: int
    requests_this_month: int
    input_tokens_this_month: int
    output_tokens_this_month: int
    failed_requests_this_month: int
