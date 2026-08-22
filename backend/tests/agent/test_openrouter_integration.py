"""OpenRouter-specific response safety and recovery tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.chat_agent import ChatAgent, ensure_openrouter_safe_message
from app.models.schemas.chat import ChatResponse


def test_openrouter_raw_structured_payload_is_not_exposed_to_customer():
    response = ChatResponse(message='{{\n"message": "internal",\n"transfer_to_human":')

    safe = ensure_openrouter_safe_message(response)

    assert safe.message == "I apologize, but I couldn't generate a valid response. Please try again."
    assert not safe.message.startswith("{")
    assert safe.end_chat is False


def test_openrouter_normal_message_is_unchanged():
    response = ChatResponse(message="Here are the services in the knowledge base.")

    assert ensure_openrouter_safe_message(response) is response


@pytest.mark.asyncio
async def test_empty_openrouter_turn_retries_with_bounded_knowledge_context():
    chat_agent = ChatAgent.__new__(ChatAgent)
    chat_agent.model_type = "OPENROUTER"
    chat_agent.model_name = "test/model"
    chat_agent.api_key = "test-key"
    chat_agent._guardrail_ctx = SimpleNamespace(
        business_name="Acme", business_domain=None, org_name="Workspace"
    )
    chat_agent.knowledge_tool = MagicMock()
    chat_agent.knowledge_tool.search_knowledge_base.return_value = (
        "[WEBSITE - https://acme.test/about] Acme provides family insurance."
    )
    retry_agent = MagicMock()
    retry_agent.arun = AsyncMock(
        return_value=SimpleNamespace(content="Acme provides family insurance.")
    )

    with patch("app.agents.chat_agent.create_model", return_value=MagicMock()), \
         patch("app.agents.chat_agent.Agent", return_value=retry_agent):
        response = await chat_agent._retry_openrouter_empty_with_knowledge(
            "What does Acme provide?"
        )

    assert response.message == "Acme provides family insurance."
    chat_agent.knowledge_tool.search_knowledge_base.assert_called_once_with(
        "What does Acme provide?"
    )
    prompt = retry_agent.arun.await_args.kwargs["message"]
    assert "Retrieved knowledge" in prompt
    assert "family insurance" in prompt


@pytest.mark.asyncio
async def test_empty_openrouter_turn_reports_missing_knowledge_without_second_llm():
    chat_agent = ChatAgent.__new__(ChatAgent)
    chat_agent.knowledge_tool = MagicMock()
    chat_agent.knowledge_tool.search_knowledge_base.return_value = (
        "No relevant information found in the knowledge base."
    )

    response = await chat_agent._retry_openrouter_empty_with_knowledge("unknown")

    assert "don't have specific information" in response.message


@pytest.mark.asyncio
async def test_groq_provider_failure_recovers_from_last_bounded_knowledge_result():
    chat_agent = ChatAgent.__new__(ChatAgent)
    chat_agent.model_type = "GROQ"
    chat_agent.model_name = "openai/gpt-oss-20b"
    chat_agent.api_key = "test-key"
    chat_agent._guardrail_ctx = SimpleNamespace(
        business_name="Acme", business_domain=None, org_name="Workspace"
    )
    chat_agent.knowledge_tool = MagicMock()
    chat_agent.knowledge_tool.last_result = (
        "[WEBSITE - https://acme.test/services] Acme offers family insurance."
    )
    retry_agent = MagicMock()
    retry_agent.arun = AsyncMock(
        return_value=SimpleNamespace(content="Acme offers family insurance.")
    )

    with patch("app.agents.chat_agent.create_model", return_value=MagicMock()), \
         patch("app.agents.chat_agent.Agent", return_value=retry_agent):
        response = await chat_agent._retry_groq_failure_with_knowledge(
            "What services do you provide?"
        )

    assert response.message == "Acme offers family insurance."
    prompt = retry_agent.arun.await_args.kwargs["message"]
    assert "https://acme.test/services" in prompt
