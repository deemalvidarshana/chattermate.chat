"""OpenRouter-specific response safety tests."""

from app.agents.chat_agent import ensure_openrouter_safe_message
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
