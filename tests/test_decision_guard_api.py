import json

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from travelx_agent.api.dependencies import provide_session_store, provide_workflow
from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.core.config import Settings
from travelx_agent.graph.workflow import build_customer_workflow
from travelx_agent.infrastructure.session_store import InMemorySessionStore
from travelx_agent.main import app


def test_follow_up_does_not_guess_existing_site_or_repeat_pricing_policy() -> None:
    first = {
        "primary_intent": "service_request",
        "secondary_intents": ["price_inquiry"],
        "user_goal": "إنشاء موقع لمطعم ومعرفة التكلفة",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [{"service_key": "websites", "confidence": 0.95}],
        "extracted_requirements": [
            {"key": "project_type", "value": "مطعم", "evidence": "مطعم"}
        ],
        "pricing_requested": True,
        "has_existing_system": None,
        "needs_clarification": True,
        "confidence": 0.94,
    }
    second_with_unsupported_claims = {
        "primary_intent": "clarification",
        "secondary_intents": ["price_inquiry"],
        "user_goal": "توضيح هدف الموقع",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [],
        "extracted_requirements": [
            {
                "key": "website_goal",
                "value": "عرض قائمة الطعام واستقبال الطلبات",
                "evidence": "عرض قائمة الطعام واستقبال الطلبات",
            },
            {"key": "existing_website", "value": "no"},
        ],
        "pricing_requested": True,
        "has_existing_system": False,
        "needs_clarification": True,
        "confidence": 0.92,
    }
    model = FakeListChatModel(
        responses=[json.dumps(first), json.dumps(second_with_unsupported_claims)]
    )
    workflow = build_customer_workflow(build_message_classifier(model), Settings())
    store = InMemorySessionStore()
    app.dependency_overrides[provide_workflow] = lambda: workflow
    app.dependency_overrides[provide_session_store] = lambda: store

    try:
        client = TestClient(app)
        first_response = client.post(
            "/v1/chat",
            json={
                "session_id": "manual-test-guard",
                "message": "أريد موقعًا لمطعمي، وأريد معرفة التكلفة",
            },
        )
        second_response = client.post(
            "/v1/chat",
            json={
                "session_id": "manual-test-guard",
                "message": "الهدف عرض قائمة الطعام واستقبال الطلبات",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    body = second_response.json()
    assert body["policy_action"] == "continue"
    assert body["missing_requirements"] == [
        "existing_website",
        "features",
        "languages",
    ]
    assert "هل يوجد موقع حالي" in body["reply"]
    assert "التكلفة" not in body["reply"]