import json
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import ValidationError

from travelx_agent.application.department_agent import (
    DepartmentAgentConfigurationError,
    DepartmentAgentRegistry,
    build_department_agents,
)
from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.core.config import Settings
from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.domain.department_agent import (
    DepartmentAgentRequest,
    DepartmentAgentResult,
    DepartmentAgentStatus,
)
from travelx_agent.domain.knowledge import KnowledgeAnswerResult
from travelx_agent.domain.service_catalog import (
    SERVICE_CATALOG,
    Department,
    ServiceKey,
)
from travelx_agent.graph.department_subgraph import (
    build_local_department_agents,
)
from travelx_agent.graph.workflow import build_customer_workflow
from travelx_agent.infrastructure.knowledge_base import TravelXKnowledgeBase
from travelx_agent.infrastructure.skill_registry import (
    DepartmentSkillRegistry,
    SkillRegistryConfigurationError,
)


KNOWLEDGE_PATH = "knowledge/travelx_knowledge.json"
SKILLS_PATH = "skills/travelx_department_skills.json"


def test_every_service_resolves_to_one_department_skill() -> None:
    registry = DepartmentSkillRegistry.from_json_file(SKILLS_PATH)

    for service in SERVICE_CATALOG.values():
        skill = registry.resolve(service.primary_department, service.key)
        assert skill.department is service.primary_department
        assert service.key in skill.service_keys


def test_department_rag_excludes_other_department_documents() -> None:
    knowledge = TravelXKnowledgeBase.from_json_file(KNOWLEDGE_PATH)
    cybtx_knowledge = knowledge.for_department(Department.CYBTX)

    documents = cybtx_knowledge.retrieve(
        "ما خدمات الأمن السيبراني؟",
        ServiceKey.CYBERSECURITY,
        limit=20,
    )
    source_ids = {str(document.metadata["source_id"]) for document in documents}

    assert cybtx_knowledge.scope_department is Department.CYBTX
    assert "travelx-cybtx-services" in source_ids
    assert "travelx-txsaas-services" not in source_ids
    assert "travelx-destination-services" not in source_ids


class _TransientCybtxAgent:
    department = Department.CYBTX

    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self,
        request: DepartmentAgentRequest,
    ) -> DepartmentAgentResult:
        self.calls += 1
        raise TimeoutError("simulated provider timeout")


class _ProgrammingErrorCybtxAgent:
    department = Department.CYBTX

    async def run(
        self,
        request: DepartmentAgentRequest,
    ) -> DepartmentAgentResult:
        raise RuntimeError("simulated programming error")


class _WorkingTxsaasAgent:
    department = Department.TXSAAS

    async def run(
        self,
        request: DepartmentAgentRequest,
    ) -> DepartmentAgentResult:
        return DepartmentAgentResult(
            department=self.department,
            service_key=request.service_key,
            skill_key="txsaas_product_discovery",
            status=DepartmentAgentStatus.ANSWERED,
            knowledge=KnowledgeAnswerResult(
                text="تتوفر خدمة تطوير المواقع.",
                sufficient_context=True,
            ),
        )


@pytest.mark.asyncio
async def test_transient_failure_retries_then_returns_unavailable() -> None:
    settings = Settings(
        department_agent_max_attempts=2,
        department_agent_attempt_timeout_seconds=1,
        department_agent_total_timeout_seconds=3,
    )
    transient_agent = _TransientCybtxAgent()
    local_agents = build_local_department_agents(
        {Department.CYBTX: transient_agent},
        settings,
    )

    result = await local_agents[Department.CYBTX].run(
        DepartmentAgentRequest(
            question="هل تقدمون حماية للمواقع؟",
            service_key=ServiceKey.CYBERSECURITY,
        )
    )

    assert result.status is DepartmentAgentStatus.UNAVAILABLE
    assert transient_agent.calls == 2


@pytest.mark.asyncio
async def test_programming_error_is_visible_and_other_department_still_works() -> None:
    settings = Settings(
        department_agent_max_attempts=1,
        department_agent_attempt_timeout_seconds=1,
        department_agent_total_timeout_seconds=3,
    )
    local_agents = build_local_department_agents(
        {
            Department.CYBTX: _ProgrammingErrorCybtxAgent(),
            Department.TXSAAS: _WorkingTxsaasAgent(),
        },
        settings,
    )

    with pytest.raises(RuntimeError, match="programming error"):
        await local_agents[Department.CYBTX].run(
            DepartmentAgentRequest(
                question="هل تقدمون حماية للمواقع؟",
                service_key=ServiceKey.CYBERSECURITY,
            )
        )

    txsaas_result = await local_agents[Department.TXSAAS].run(
        DepartmentAgentRequest(
            question="هل تطورون مواقع؟",
            service_key=ServiceKey.WEBSITE_DEVELOPMENT,
        )
    )

    assert txsaas_result.status is DepartmentAgentStatus.ANSWERED


def test_registry_rejects_a_missing_department_agent() -> None:
    with pytest.raises(DepartmentAgentConfigurationError):
        DepartmentAgentRegistry(
            {Department.TXSAAS: _WorkingTxsaasAgent()}
        )


def test_timeout_settings_reject_non_positive_values() -> None:
    with pytest.raises(ValidationError):
        Settings(department_agent_total_timeout_seconds=0)


def test_skill_registry_rejects_incomplete_service_coverage(tmp_path: Path) -> None:
    payload = json.loads(Path(SKILLS_PATH).read_text(encoding="utf-8"))
    payload["skills"] = payload["skills"][1:]
    incomplete_path = tmp_path / "incomplete-skills.json"
    incomplete_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(SkillRegistryConfigurationError):
        DepartmentSkillRegistry.from_json_file(incomplete_path)


@pytest.mark.asyncio
async def test_parent_workflow_routes_service_question_to_department_agent() -> None:
    classification = {
        "primary_intent": "service_question",
        "secondary_intents": [],
        "user_goal": "معرفة هل تتوفر خدمة تطوير المواقع",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [
            {"service_key": "website_development", "confidence": 0.98}
        ],
        "extracted_requirements": [],
        "pricing_requested": False,
        "has_existing_system": None,
        "needs_clarification": False,
        "confidence": 0.97,
    }
    answer = {
        "answer_ar": "نعم، يقدم قسم TXSaaS تصميم وتطوير المواقع.",
        "source_ids": ["travelx-txsaas-services"],
        "sufficient_context": True,
    }
    settings = Settings()
    knowledge = TravelXKnowledgeBase.from_json_file(KNOWLEDGE_PATH)
    skills = DepartmentSkillRegistry.from_json_file(SKILLS_PATH)
    agents = build_department_agents(
        FakeListChatModel(responses=[json.dumps(answer, ensure_ascii=False)]),
        knowledge,
        skills,
    )
    local_agents = build_local_department_agents(agents, settings)
    workflow = build_customer_workflow(
        build_message_classifier(
            FakeListChatModel(
                responses=[json.dumps(classification, ensure_ascii=False)]
            )
        ),
        settings,
        knowledge_base=knowledge,
        department_agents=DepartmentAgentRegistry(local_agents),
    )

    result = await workflow.ainvoke(
        {
            "message": "هل تقدمون تطوير مواقع؟",
            "conversation": ConversationState(session_id="department-route"),
        }
    )

    agent_result = result["department_agent_result"]
    assert agent_result.department is Department.TXSAAS
    assert agent_result.skill_key == "txsaas_product_discovery"
    assert agent_result.status is DepartmentAgentStatus.ANSWERED
    assert result["assistant_response"].knowledge_sources[0].source_id == (
        "travelx-txsaas-services"
    )
    assert "requirement_collection" not in result