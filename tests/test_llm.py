"""Tests for LLM layer — client methods with mocked OpenAI API."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sample_dna_tagger.llm import LLMClient, TAGGING_SYSTEM_PROMPT, SEARCH_QUERY_SYSTEM_PROMPT


# ── Client construction ──────────────────────────────────────────────

def test_client_unconfigured():
    client = LLMClient()
    assert client._client is None


def test_client_configure():
    client = LLMClient()
    # Don't actually call OpenAI — just verify the attributes are set
    with patch("sample_dna_tagger.llm.openai.AsyncOpenAI") as mock_openai:
        import asyncio
        asyncio.run(client.configure("http://localhost:11434/v1", "sk-test", "test-model"))
    assert client._base_url == "http://localhost:11434/v1"
    assert client._model == "test-model"


# ── JSON parsing ────────────────────────────────────────────────────

def test_parse_llm_json_clean():
    client = LLMClient()
    result = client._parse_llm_json('{"energy":"high","texture":"smooth"}')
    assert result["energy"] == "high"


def test_parse_llm_json_with_markdown_fence():
    client = LLMClient()
    result = client._parse_llm_json('```json\n{"mood":"dark"}\n```')
    assert result["mood"] == "dark"


def test_parse_llm_json_invalid():
    client = LLMClient()
    with pytest.raises(json.JSONDecodeError):
        client._parse_llm_json("not json")


# ── Tag generation (mocked API call) ─────────────────────────────────

@pytest.mark.asyncio
async def test_generate_tags_success():
    client = LLMClient()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"energy":"high","texture":"warm","mood":"dark","emotional_quality":"cinematic","motion":"static","instrument_type":"Punchy Kick","instrument_subtype":"808","descriptive_tags":["heavy","sub"]}'

    client._client = AsyncMock()
    client._configured = True  # Required by generate_tags
    client._client.chat.completions.create = AsyncMock(return_value=mock_response)

    features = {"bpm": 140.0, "spectral_centroid": 140.0, "instrument_category": "kick"}
    result = await client.generate_tags(features)

    assert result["energy"] == "high"
    assert result["texture"] == "warm"
    assert result["instrument_type"] == "Punchy Kick"
    assert len(result["descriptive_tags"]) == 2


@pytest.mark.asyncio
async def test_generate_tags_unconfigured():
    client = LLMClient()
    with pytest.raises(RuntimeError, match="not configured"):
        await client.generate_tags({})


@pytest.mark.asyncio
async def test_generate_tags_retry_on_failure():
    client = LLMClient()
    client._client = AsyncMock()
    client._configured = True  # Required by generate_tags
    # First two calls fail, third succeeds
    client._client.chat.completions.create = AsyncMock(side_effect=[
        Exception("timeout"),
        Exception("server error"),
        MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"energy":"low"}'))]
        ),
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await client.generate_tags({"test": True})
    assert result["energy"] == "low"


# ── Query parsing (mocked) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_search_query_success():
    client = LLMClient()
    client._client = AsyncMock()
    client._configured = True  # Required by parse_search_query
    client._client.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(
            content='{"filters":[{"dimension":"energy","value":"high","negate":false},{"dimension":"mood","value":"dark","negate":false}]}'
        ))]
    ))

    result = await client.parse_search_query("high energy dark mood")
    assert len(result["filters"]) == 2
    assert result["filters"][0]["dimension"] == "energy"
    assert result["filters"][1]["dimension"] == "mood"


# ── Batch tagging ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_tags_batch():
    client = LLMClient()
    client._client = AsyncMock()
    client._configured = True  # Required by generate_tags_batch
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps([
        {"energy": "high", "texture": "smooth"},
        {"energy": "low", "texture": "gritty"},
    ])
    client._client.chat.completions.create = AsyncMock(return_value=mock_resp)

    results = await client.generate_tags_batch([{"bpm": 140}, {"bpm": 90}])
    assert len(results) == 2
    assert results[0]["energy"] == "high"
    assert results[1]["energy"] == "low"


# ── Test connection ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_test_connection_success():
    client = LLMClient()
    client._client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "pong"
    client._client.chat.completions.create = AsyncMock(return_value=mock_resp)
    client._model = "test-model"

    result = await client.test_connection()
    assert result["ok"] is True
    assert result["model"] == "test-model"


@pytest.mark.asyncio
async def test_test_connection_unconfigured():
    client = LLMClient()
    result = await client.test_connection()
    assert result["ok"] is False
    assert "Not configured" in result["error"]


# ── Rate limiting ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limiter_acquire():
    client = LLMClient()
    client.calls_per_minute = 5
    # First 5 acquires should be immediate
    for _ in range(5):
        await client._acquire_rate_limit()
    # The semaphore allows exactly 5 concurrent; release them
    client._rate_semaphore = None  # reset for next test


@pytest.mark.asyncio
async def test_rate_limiter_default_unlimited():
    client = LLMClient()
    # Default 0 means no rate limiting
    for _ in range(100):
        await client._acquire_rate_limit()
    client._rate_semaphore = None


# ── Configuration persistence ────────────────────────────────────────

@pytest.mark.asyncio
async def test_configure_persistence(db):
    from sample_dna_tagger import db as db_mod
    client = LLMClient()
    with patch("sample_dna_tagger.llm.openai.AsyncOpenAI"):
        await client.configure("http://test:11434/v1", "sk-test", "test-model")
    assert client._configured is True


# ── Parse search query edge cases ───────────────────────────────────

def test_parse_llm_json_empty():
    client = LLMClient()
    result = client._parse_llm_json("{}")
    assert result == {}


def test_parse_llm_json_list():
    client = LLMClient()
    result = client._parse_llm_json('[{"a": 1}]')
    assert isinstance(result, list)
    assert result[0]["a"] == 1


# ── Timeout handling ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_tags_timeout():
    import asyncio as _asyncio
    client = LLMClient()
    client._client = AsyncMock()
    client._configured = True
    client._client.chat.completions.create = AsyncMock(
        side_effect=_asyncio.TimeoutError("timed out")
    )
    # Timeout is caught by retry logic; verify it doesn't crash
    result = await client.generate_tags({"bpm": 140})
    assert isinstance(result, dict)


# ── API error handling ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_test_connection_api_error():
    import openai
    client = LLMClient()
    client._client = AsyncMock()
    client._client.chat.completions.create = AsyncMock(
        side_effect=Exception("bad gateway")
    )
    result = await client.test_connection()
    assert result["ok"] is False
