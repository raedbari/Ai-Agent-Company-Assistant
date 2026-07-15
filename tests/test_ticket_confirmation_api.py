import asyncio
import json

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from travelx_agent.api.dependencies import provide_session_store, provide_workflow
from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.core.config import Settings
from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.service_catalog import Department, ServiceKey
from travelx_agent.domain.ticket_draft import TicketDraft
from travelx_agent.graph.workflow import build_customer_workflow
from travelx_agent.infrastructure.session_store import InMemorySessionStore
from travelx_agent.infrastructure.ticket_repository import InMemoryTicketRepository
from travelx_agent.main import app


def confirmation_decision() -> dict:
    return {
        "primary_intent": "ticket_confirm",
        "secondary_intents": [],
        "user_goal": "تأكيد إنشاء التذكرة",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [],
        "extracted_requirements": [],
        "pricing_requested": False,
        "has_existing_system": None,
        "needs_clarification": False,
        "confidence": 0.99,
    }


def review_conversation(session_id: str) -> ConversationState:
    requirements = {
        "business_type": "مطعم",
        "website_goal": "عرض قائمة الطعام واستقبال الطلبات",
        "existing_website": "no",
        "features": "قائمة الطعام والطلبات",
        "languages": "العربية",
    }
    return ConversationState(
        session_id=session_id,
        stage=ConversationStage.DRAFT_REVIEW,
        current_service=ServiceKey.WEBSITE_DEVELOPMENT,
        collected_requirements=requirements,
        missing_requirements=[],
        ticket_draft=TicketDraft(
            service_key=ServiceKey.WEBSITE_DEVELOPMENT,
            primary_department=Department.TXSAAS,
            requirements=requirements,
        ),
    )


def configure_confirmation_api(response_count: int = 1):
    model = FakeListChatModel(
        responses=[json.dumps(confirmation_decision()) for _ in range(response_count)]
    )
    repository = InMemoryTicketRepository()
    workflow = build_customer_workflow(
        build_message_classifier(model),
        Settings(),
        ticket_repository=repository,
    )
    store = InMemorySessionStore()
    session_id = "confirmation-session"
    asyncio.run(store.save(review_conversation(session_id)))
    app.dependency_overrides[provide_workflow] = lambda: workflow
    app.dependency_overrides[provide_session_store] = lambda: store
    return TestClient(app), repository, session_id


def test_api_creates_once_when_the_exact_draft_version_is_confirmed() -> None:
    client, repository, session_id = configure_confirmation_api(response_count=2)

    try:
        first = client.post(
            "/v1/chat",
            json={
                "session_id": session_id,
                "message": "موافق، أنشئ التذكرة",
                "draft_version": 1,
            },
        )
        second = client.post(
            "/v1/chat",
            json={
                "session_id": session_id,
                "message": "موافق، أنشئ التذكرة",
                "draft_version": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["stage"] == "ticket_created"
    assert first.json()["ticket"]["assigned_department"] == "txsaas"
    assert second.json()["ticket"]["ticket_number"] == first.json()["ticket"][
        "ticket_number"
    ]
    assert "مكررة" in second.json()["reply"]
    assert asyncio.run(repository.count()) == 1


def test_api_rejects_a_stale_draft_version() -> None:
    client, repository, session_id = configure_confirmation_api()

    try:
        response = client.post(
            "/v1/chat",
            json={
                "session_id": session_id,
                "message": "موافق، أنشئ التذكرة",
                "draft_version": 2,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json()["stage"] == "draft_review"
    assert response.json()["ticket"] is None
    assert "الإصدار 1" in response.json()["reply"]
    assert asyncio.run(repository.count()) == 0