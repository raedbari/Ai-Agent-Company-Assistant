import json

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from travelx_agent.api.dependencies import provide_session_store, provide_workflow
from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.application.ticket_feature_validator import (
    build_ticket_feature_validator,
)
from travelx_agent.core.config import Settings
from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.service_catalog import Department, ServiceKey
from travelx_agent.domain.ticket_draft import TicketDraft
from travelx_agent.graph.workflow import build_customer_workflow
from travelx_agent.infrastructure.session_store import InMemorySessionStore
from travelx_agent.main import app


def classifier_edit_response() -> dict:
    return {
        "primary_intent": "ticket_edit",
        "secondary_intents": [],
        "user_goal": "إضافة ميزة إلى مسودة التذكرة",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [],
        "extracted_requirements": [],
        "pricing_requested": False,
        "has_existing_system": None,
        "needs_clarification": False,
        "confidence": 0.96,
    }


def make_draft_conversation(session_id: str) -> ConversationState:
    return ConversationState(
        session_id=session_id,
        stage=ConversationStage.DRAFT_REVIEW,
        current_service=ServiceKey.WEBSITE_DEVELOPMENT,
        collected_requirements={
            "business_type": "مطعم",
            "website_goal": "استقبال الطلبات",
            "existing_website": "no",
            "features": "قائمة الطعام",
            "languages": "العربية",
        },
        missing_requirements=[],
        ticket_draft=TicketDraft(
            service_key=ServiceKey.WEBSITE_DEVELOPMENT,
            primary_department=Department.TXSAAS,
            requirements={"business_type": "مطعم"},
        ),
    )


def run_edit_request(
    feature_response: dict,
    message: str,
    classifier_response: dict | None = None,
) -> dict:
    classifier_model = FakeListChatModel(
        responses=[json.dumps(classifier_response or classifier_edit_response())]
    )
    feature_model = FakeListChatModel(responses=[json.dumps(feature_response)])
    workflow = build_customer_workflow(
        build_message_classifier(classifier_model),
        Settings(),
        build_ticket_feature_validator(feature_model),
    )
    store = InMemorySessionStore()
    session_id = "draft-session"

    import asyncio

    asyncio.run(store.save(make_draft_conversation(session_id)))
    app.dependency_overrides[provide_workflow] = lambda: workflow
    app.dependency_overrides[provide_session_store] = lambda: store

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/chat",
            json={"session_id": session_id, "message": message},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    return response.json()


def test_api_adds_relevant_feature_and_increments_draft_version() -> None:
    response = run_edit_request(
        {
            "action": "accept",
            "edits": [
                {
                    "operation": "add_feature",
                    "target": "الدفع الإلكتروني",
                    "replacement": None,
                }
            ],
            "reason_code": "relevant_website_feature",
            "clarification_question_ar": None,
            "suggested_service": None,
            "confidence": 0.97,
        },
        "أضف الدفع الإلكتروني",
    )

    assert response["ticket_draft"]["version"] == 2
    assert response["ticket_draft"]["additional_features"] == ["الدفع الإلكتروني"]


def test_api_rejects_random_text_without_mutating_draft() -> None:
    response = run_edit_request(
        {
            "action": "reject_off_topic",
            "edits": [],
            "reason_code": "random_unrelated_text",
            "clarification_question_ar": None,
            "suggested_service": None,
            "confidence": 0.98,
        },
        "أضف كتاب",
    )

    assert response["ticket_draft"]["version"] == 1
    assert response["ticket_draft"]["additional_features"] == []
    assert "لم أضف" in response["reply"]


def test_api_applies_multiple_features_in_one_draft_version() -> None:
    response = run_edit_request(
        {
            "action": "accept",
            "edits": [
                {
                    "operation": "add_feature",
                    "target": "حماية التطبيق من الهجمات",
                    "replacement": None,
                },
                {
                    "operation": "add_feature",
                    "target": "تحسين استهلاك الرموز وتقليل التكلفة التشغيلية",
                    "replacement": None,
                },
            ],
            "reason_code": "multiple_relevant_features",
            "clarification_question_ar": None,
            "suggested_service": None,
            "confidence": 0.98,
        },
        "أريده محميًا من الهجمات وألا يهدر الرموز",
    )

    assert response["ticket_draft"]["version"] == 2
    assert response["ticket_draft"]["additional_features"] == [
        "حماية التطبيق من الهجمات",
        "تحسين استهلاك الرموز وتقليل التكلفة التشغيلية",
    ]
    assert "تم تطبيق التعديلات التالية" in response["reply"]


def test_draft_review_routes_desired_capability_to_edit_gate() -> None:
    service_request = classifier_edit_response()
    service_request["primary_intent"] = "service_request"
    service_request["user_goal"] = "تقليل استهلاك الرموز"

    response = run_edit_request(
        {
            "action": "accept",
            "edits": [
                {
                    "operation": "add_feature",
                    "target": "تحسين استهلاك الرموز وتقليل التكلفة التشغيلية",
                    "replacement": None,
                }
            ],
            "reason_code": "relevant_efficiency_requirement",
            "clarification_question_ar": None,
            "suggested_service": None,
            "confidence": 0.97,
        },
        "أريده ألا يستهلك الرموز بشكل غير ضروري",
        classifier_response=service_request,
    )

    assert response["ticket_draft"]["version"] == 2
    assert response["ticket_draft"]["additional_features"] == [
        "تحسين استهلاك الرموز وتقليل التكلفة التشغيلية"
    ]