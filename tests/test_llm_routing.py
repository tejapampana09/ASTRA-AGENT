"""Unit tests for LLM routing, quota handling, and circuit breaker."""
import time
import pytest
from unittest.mock import MagicMock, patch

from astra.llm import (
    LLMClient,
    LLMProvider,
    LLMResponse,
    LLMRouter,
    ProviderState,
    QuotaCircuitBreaker,
    circuit_breaker,
)
from astra.config import settings


def test_circuit_breaker_state_transitions():
    cb = QuotaCircuitBreaker()
    provider = "test_provider"

    # Initial state
    assert cb.is_available(provider) is True
    status = cb.get_status(provider)
    assert status["state"] == "healthy"

    # Rate limit error (429)
    state = cb.record_error(provider, Exception("429 Too Many Requests"))
    assert state == ProviderState.RATE_LIMITED
    assert cb.is_available(provider) is False
    assert cb.get_status(provider)["cooldown_remaining_sec"] > 0

    # Reset
    cb.reset(provider)
    assert cb.is_available(provider) is True

    # Generic quota wording does not prove daily exhaustion.
    state = cb.record_error(provider, Exception("ResourceExhausted: Quota exceeded for quota metric"))
    assert state == ProviderState.RATE_LIMITED
    assert cb.is_available(provider) is False

    # Auth error
    state = cb.record_error(provider, Exception("401 Unauthorized: Invalid_api_key"))
    assert state == ProviderState.AUTH_ERROR
    assert cb.is_available(provider) is False

    # Success records back to healthy
    cb.record_success(provider)
    assert cb.is_available(provider) is True


def test_llm_client_fallback_without_circular_loop():
    # Setup mock providers
    client = LLMClient()
    mock_gemini = MagicMock(spec=LLMProvider)
    mock_groq = MagicMock(spec=LLMProvider)
    mock_ollama = MagicMock(spec=LLMProvider)

    # Primary (Gemini) fails with 429 quota exhaustion
    mock_gemini.complete.side_effect = RuntimeError("ResourceExhausted: 429 Quota Exceeded")
    # Secondary (Groq) succeeds
    mock_groq.complete.return_value = LLMResponse(content="Groq response", provider="groq", model="gpt-oss")

    client.router.gemini = mock_gemini
    client.router.groq = mock_groq
    client.router.ollama = mock_ollama

    with patch.object(settings, "gemini_api_key", "test-gemini-key"), \
         patch.object(settings, "groq_api_key", "test-groq-key"), \
         patch.object(client.router, "get_provider_and_model", return_value=(mock_gemini, "gemini-3.5-flash-lite")), \
         patch.object(client.router, "get_provider_name", return_value="gemini"):

        client.circuit_breaker.reset()
        res = client.complete([{"role": "user", "content": "hi"}])
        assert res.provider == "groq"
        assert res.content == "Groq response"
        # Primary was called once
        mock_gemini.complete.assert_called_once()
        # Fallback was called once
        mock_groq.complete.assert_called_once()


def test_llm_client_circular_fallback_prevented_when_all_fail():
    client = LLMClient()
    mock_gemini = MagicMock(spec=LLMProvider)
    mock_groq = MagicMock(spec=LLMProvider)

    # Both fail with 429
    mock_gemini.complete.side_effect = RuntimeError("Gemini 429 Quota Exceeded")
    mock_groq.complete.side_effect = RuntimeError("Groq 429 Rate Limit Exceeded")

    client.router.gemini = mock_gemini
    client.router.groq = mock_groq

    with patch.object(settings, "gemini_api_key", "test-gemini-key"), \
         patch.object(settings, "groq_api_key", "test-groq-key"), \
         patch.object(client.router.ollama, "health", return_value={"connected": False}), \
         patch.object(client.router, "get_provider_and_model", return_value=(mock_gemini, "gemini-3.5-flash-lite")), \
         patch.object(client.router, "get_provider_name", return_value="gemini"):

        client.circuit_breaker.reset()
        with pytest.raises(RuntimeError) as exc_info:
            client.complete([{"role": "user", "content": "test"}])

        assert "429" in str(exc_info.value)
        # Each provider should be called EXACTLY once — no circular re-entry!
        assert mock_gemini.complete.call_count == 1
        assert mock_groq.complete.call_count == 1


def test_circuit_breaker_daily_quota_exhaustion():
    cb = QuotaCircuitBreaker()
    # Daily quota error like Gemini GenerateTokensPerDay
    state = cb.record_error("gemini", Exception("ResourceExhausted: GenerateTokensPerDay quota exceeded"))
    assert state == ProviderState.QUOTA_EXHAUSTED
    assert cb.is_available("gemini") is False
    status = cb.get_status("gemini")
    # Daily cooldown ends at the next Pacific midnight, including DST.
    from astra.quota import pacific_window
    remaining = pacific_window()[1] - time.time()
    assert abs(status["cooldown_remaining_sec"] - remaining) < 1


def test_fallback_does_not_call_quota_exhausted_provider():
    client = LLMClient()
    mock_gemini = MagicMock(spec=LLMProvider)
    mock_groq = MagicMock(spec=LLMProvider)
    mock_ollama = MagicMock(spec=LLMProvider)
    mock_ollama.complete.return_value = LLMResponse(content="Ollama response", provider="ollama", model="qwen")

    client.router.gemini = mock_gemini
    client.router.groq = mock_groq
    client.router.ollama = mock_ollama

    client.circuit_breaker.reset()
    # Simulate Gemini having previously exhausted daily quota
    client.circuit_breaker.record_error("gemini", Exception("daily limit exceeded"))
    assert client.circuit_breaker.is_available("gemini") is False

    # Groq fails with an error
    mock_groq.complete.side_effect = RuntimeError("Groq connection timeout")

    with patch.object(settings, "gemini_api_key", "test-gemini-key"), \
         patch.object(settings, "groq_api_key", "test-groq-key"), \
         patch.object(client.router.ollama, "health", return_value={"connected": True}), \
         patch.object(client.router, "get_provider_and_model", return_value=(mock_groq, "qwen/qwen3.8-27b")), \
         patch.object(client.router, "get_provider_name", return_value="groq"):

        res = client.complete([{"role": "user", "content": "test"}])
        assert res.provider == "ollama"
        assert res.content == "Ollama response"
        # Gemini must NEVER be called because it is quota exhausted
        mock_gemini.complete.assert_not_called()
        mock_groq.complete.assert_called_once()
        mock_ollama.complete.assert_called_once()

