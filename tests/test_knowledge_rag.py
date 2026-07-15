import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from travelx_agent.application.knowledge_answerer import (
    answer_from_knowledge,
    build_knowledge_answerer,
)
from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.core.config import Settings
from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.domain.policy_decision import PolicyAction
from travelx_agent.domain.service_catalog import ServiceKey
from travelx_agent.graph.workflow import build_customer_workflow
from travelx_agent.infrastructure.knowledge_base import TravelXKnowledgeBase


KNOWLEDGE_PATH = "knowledge/travelx_knowledge.json"


def test_retriever_prioritizes_the_selected_service_and_common_policies() -> None:
    knowledge_base = TravelXKnowledgeBase.from_json_file(KNOWLEDGE_PATH)

    documents = knowledge_base.retrieve(
        "هل تقدمون تطوير مواقع؟",
        ServiceKey.WEBSITE_DEVELOPMENT,
        limit=4,
    )
    source_ids = {document.metadata["source_id"] for document in documents}

    assert "travelx-txsaas-services" in source_ids
    assert "travelx-company-overview" in source_ids
    assert "travelx-customer-service-policies" in source_ids


@pytest.mark.asyncio
async def test_service_question_uses_rag_without_entering_requirements_flow() -> None:
    classification = {
        "primary_intent": "service_question",
        "secondary_intents": [],
        "user_goal": "معرفة هل تتوفر خدمة تطوير المواقع",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [
            {"service_key": "website_development", "confidence": 0.96}
        ],
        "extracted_requirements": [],
        "pricing_requested": False,
        "has_existing_system": None,
        "needs_clarification": False,
        "confidence": 0.95,
    }
    knowledge_answer = {
        "answer_ar": "نعم، تقدم Travel-X تصميم وتطوير مواقع الويب.",
        "source_ids": ["travelx-txsaas-services"],
        "sufficient_context": True,
    }
    classifier_model = FakeListChatModel(
        responses=[json.dumps(classification, ensure_ascii=False)]
    )
    answer_model = FakeListChatModel(
        responses=[json.dumps(knowledge_answer, ensure_ascii=False)]
    )
    workflow = build_customer_workflow(
        build_message_classifier(classifier_model),
        Settings(),
        knowledge_answerer=build_knowledge_answerer(answer_model),
        knowledge_base=TravelXKnowledgeBase.from_json_file(KNOWLEDGE_PATH),
    )

    result = await workflow.ainvoke(
        {
            "message": "هل تقدمون تطوير مواقع؟",
            "conversation": ConversationState(session_id="rag-question"),
        }
    )

    assert "requirement_collection" not in result
    assert result["assistant_response"].service_key is ServiceKey.WEBSITE_DEVELOPMENT
    assert result["assistant_response"].knowledge_sources[0].source_id == (
        "travelx-txsaas-services"
    )
    assert "تصميم وتطوير مواقع" in result["assistant_response"].text


@pytest.mark.asyncio
async def test_unretrieved_source_from_model_is_rejected() -> None:
    model = FakeListChatModel(
        responses=[
            json.dumps(
                {
                    "answer_ar": "إجابة غير موثقة",
                    "source_ids": ["invented-source"],
                    "sufficient_context": True,
                },
                ensure_ascii=False,
            )
        ]
    )

    result = await answer_from_knowledge(
        build_knowledge_answerer(model),
        TravelXKnowledgeBase.from_json_file(KNOWLEDGE_PATH),
        "هل تقدمون تطوير مواقع؟",
        ServiceKey.WEBSITE_DEVELOPMENT,
    )

    assert result.sufficient_context is False
    assert result.sources == []
    assert "معلومات موثقة" in result.text


@pytest.mark.asyncio
async def test_repeated_price_question_is_rephrased_without_fake_human_check() -> None:
    classification = {
        "primary_intent": "price_inquiry",
        "secondary_intents": [],
        "user_goal": "معرفة تكلفة بناء وكيل ذكاء اصطناعي",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [{"service_key": "ai_agent", "confidence": 0.97}],
        "extracted_requirements": [],
        "pricing_requested": True,
        "pricing_evidence": "كم تكلفة",
        "has_existing_system": None,
        "needs_clarification": False,
        "confidence": 0.96,
    }
    classifier_model = FakeListChatModel(
        responses=[json.dumps(classification, ensure_ascii=False)] * 3
    )
    workflow = build_customer_workflow(
        build_message_classifier(classifier_model),
        Settings(),
    )
    conversation = ConversationState(session_id="repeat-price")
    results = []

    for _ in range(4):
        result = await workflow.ainvoke(
            {
                "message": "كم تكلفة بناء AI Agent؟",
                "conversation": conversation,
            }
        )
        conversation = result["conversation"]
        results.append(result)

    assert results[0]["assistant_response"].policy_action is (
        PolicyAction.APPLY_PRICING_POLICY
    )
    assert "بصياغة أبسط" in results[1]["assistant_response"].text
    assert results[0]["assistant_response"].text != results[1][
        "assistant_response"
    ].text
    assert results[3]["assistant_response"].policy_action is (
        PolicyAction.APPLY_PRICING_POLICY
    )
    assert "classification" in results[3]


@pytest.mark.asyncio
async def test_price_paraphrases_share_one_semantic_repeat_sequence() -> None:
    messages_and_evidence = [
        ("كم تكلفة بناء AI Agent؟", "كم تكلفة"),
        ("ما سعر إنشاء وكيل ذكاء اصطناعي؟", "ما سعر"),
        ("بكم تسوون agent ذكي؟", "بكم"),
        ("كم سيكون سعر الوكيل؟", "سعر"),
    ]
    classifications = []
    for _, evidence in messages_and_evidence:
        classifications.append(
            json.dumps(
                {
                    "primary_intent": "price_inquiry",
                    "secondary_intents": [],
                    "user_goal": "معرفة تكلفة بناء وكيل ذكاء اصطناعي",
                    "language": "ar",
                    "tone": "neutral",
                    "service_candidates": [
                        {"service_key": "ai_agent", "confidence": 0.97}
                    ],
                    "extracted_requirements": [],
                    "pricing_requested": True,
                    "pricing_evidence": evidence,
                    "has_existing_system": None,
                    "needs_clarification": False,
                    "confidence": 0.96,
                },
                ensure_ascii=False,
            )
        )

    workflow = build_customer_workflow(
        build_message_classifier(FakeListChatModel(responses=classifications)),
        Settings(),
    )
    conversation = ConversationState(session_id="semantic-price-repeat")
    results = []

    for message, _ in messages_and_evidence:
        result = await workflow.ainvoke(
            {"message": message, "conversation": conversation}
        )
        conversation = result["conversation"]
        results.append(result)

    assert "بصياغة أبسط" in results[1]["assistant_response"].text
    assert "سياسة السعر لم تتغير" in results[2]["assistant_response"].text
    assert results[3]["assistant_response"].policy_action is (
        PolicyAction.APPLY_PRICING_POLICY
    )
    assert results[3]["conversation"].counters.semantic_repeat_count == 3