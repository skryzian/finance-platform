from dataclasses import dataclass
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class AIAnswer:
    text: str
    provider_key: str
    model_name: str
    source_references: list[dict[str, str]]
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class AIProviderResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class AIProvider(Protocol):
    provider_key: str
    model_name: str

    async def generate(self, prompt: str, context: dict[str, Any], max_output_tokens: int) -> AIProviderResult:
        """Generate an explanation from explicitly supplied, verified context."""
        ...


class AIUnavailable(RuntimeError):
    pass


class ToolRegistry:
    """An explicit allowlist of callable backend tools; never exposes a database session."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, tool: Callable[..., Any]) -> None:
        if not name or name in self._tools:
            raise ValueError("Tool name must be non-empty and unique")
        self._tools[name] = tool

    def invoke(self, name: str, **arguments: Any) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise PermissionError(f"AI tool is not allowlisted: {name}")
        return tool(**arguments)

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))


class AIService:
    def __init__(self, provider: AIProvider, tools: ToolRegistry) -> None:
        self.provider = provider
        self.tools = tools

    async def answer(self, prompt: str, context: dict[str, Any], max_output_tokens: int = 600) -> AIAnswer:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        response = await self.provider.generate(prompt, context, max_output_tokens)
        return AIAnswer(
            text=response.text,
            provider_key=self.provider.provider_key,
            model_name=self.provider.model_name,
            source_references=list(context.get("source_references", [])),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    async def aclose(self) -> None:
        close = getattr(self.provider, "aclose", None)
        if close is not None:
            await close()


class FinancialCopilot(AIService):
    pass
