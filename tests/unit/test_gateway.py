import pytest

from app.gateway.client import UnifiedLLMGateway
from app.gateway.router import FailoverRouter, ProviderEndpoint


def test_router_initialization():
    router = FailoverRouter()
    status = router.get_status()

    assert len(status) == 4
    names = [p["name"] for p in status]
    assert "openai" in names
    assert "groq" in names
    assert "bedrock" in names
    assert "mock" in names

    # Mock provider is always healthy
    mock = next(p for p in router.providers if p.name == "mock")
    assert mock.is_healthy() is True


def test_circuit_breaker_trips_after_failures():
    endpoint = ProviderEndpoint(name="test-provider", model="test-model", failure_threshold=2)
    assert endpoint.is_healthy() is True

    endpoint.record_failure(Exception("Network timeout"))
    assert endpoint.is_healthy() is True

    endpoint.record_failure(Exception("Rate limit 429"))
    assert endpoint.is_healthy() is False  # Tripped!

    endpoint.record_success()
    assert endpoint.is_healthy() is True


@pytest.mark.asyncio
async def test_gateway_mock_completion():
    gateway = UnifiedLLMGateway()
    response = await gateway.acomplete(
        prompt="Generate 3 search queries for topic: pgvector indexing",
        system_prompt="You are a research assistant",
    )

    assert response.content is not None
    assert response.latency_ms >= 0.0
    assert response.provider in ["mock", "mock-safety-net", "openai", "groq"]
