import pytest

from app.ai.service import ToolRegistry
from app.providers.contracts import ProviderRegistry, ProviderUnavailable


def test_provider_registry_requires_explicit_provider():
    providers = ProviderRegistry()
    with pytest.raises(ProviderUnavailable):
        providers.get("market", "unconfigured")

    provider = object()
    providers.register("market", provider, "test-provider")
    assert providers.get("market", "test-provider") is provider


def test_ai_tools_are_explicitly_allowlisted():
    tools = ToolRegistry()
    tools.register("get_net_worth", lambda user_id: {"user_id": user_id})

    assert tools.invoke("get_net_worth", user_id=42) == {"user_id": 42}
    assert tools.allowed_tools == ("get_net_worth",)
    with pytest.raises(PermissionError):
        tools.invoke("arbitrary_sql", query="select * from users")


def test_ai_tool_names_must_be_unique():
    tools = ToolRegistry()
    tools.register("get_portfolio", lambda: [])
    with pytest.raises(ValueError):
        tools.register("get_portfolio", lambda: ["unexpected"])
