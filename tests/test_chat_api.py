import json

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from travelx_agent.api.dependencies import provide_session_store, provide_workflow
from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.core.config import Settings
from travelx_agent.graph.workflow import build_customer_workflow
from travelx_agent.infrastructure.session_store import InMemorySessionStore
from travelx_agent.main import app


def test_chat_api_preserves_requirements_between_two_messages() -> None:
    first = {
        "primary_intent": "service_request",
        "secondary_intents": ["price_inquiry"],
        "user_goal": "إنشاء موقع لمطعم",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [{"service_key": "websites", "confidence": 0.95}],
        "extracted_requirements": [
            {"key": "project_type", "value": "مطعم", "evidence": "مطعم"}
        ],
        "pricing_requested": True,
        "has_existing_system": False,
        "needs_clarification": True,
        "confidence": 0.91,
    }
    second = {
        "primary_intent": "clarification",
        "secondary_intents": [],
        "user_goal": "توضيح هدف الموقع",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [],
        "extracted_requirements": [
            {
                "key": "website_goal",
                "value": "عرض المطعم واستقبال الطلبات",
                "evidence": "عرض المطعم واستقبال الطلبات",
            }
        ],
        "pricing_requested": False,
        "has_existing_system": None,
        "needs_clarification": True,
        "confidence": 0.93,
    }
    model = FakeListChatModel(responses=[json.dumps(first), json.dumps(second)])
    workflow = build_customer_workflow(build_message_classifier(model), Settings())
    store = InMemorySessionStore()
    app.dependency_overrides[provide_workflow] = lambda: workflow
    app.dependency_overrides[provide_session_store] = lambda: store

    try:
        client = TestClient(app)
        first_response = client.post(
            "/v1/chat",
            json={"message": "أشتي موقع لمطعمي وكم بيكلف؟"},
        )
        assert first_response.status_code == 200, first_response.text
        session_id = first_response.json()["session_id"]
        second_response = client.post(
            "/v1/chat",
            json={
                "session_id": session_id,
                "message": "أريده لعرض المطعم واستقبال الطلبات",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["service_key"] == "website_development"
    assert "website_goal" in first_response.json()["missing_requirements"]
    assert "website_goal" not in second_response.json()["missing_requirements"]
    assert "features" in second_response.json()["missing_requirements"]