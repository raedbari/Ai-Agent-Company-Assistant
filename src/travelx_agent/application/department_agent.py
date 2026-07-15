from collections.abc import Mapping

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable

from travelx_agent.application.ports.department_agent import DepartmentAgentPort
from travelx_agent.domain.department_agent import (
    DepartmentAgentRequest,
    DepartmentAgentResult,
    DepartmentAgentStatus,
)
from travelx_agent.domain.knowledge import (
    KnowledgeAnswerResult,
    KnowledgeModelAnswer,
    KnowledgeSource,
)
from travelx_agent.domain.service_catalog import Department
from travelx_agent.infrastructure.knowledge_base import TravelXKnowledgeBase
from travelx_agent.infrastructure.skill_registry import DepartmentSkillRegistry
from travelx_agent.prompts.department_agent import DEPARTMENT_AGENT_PROMPT


DEPARTMENT_NAMES: dict[Department, str] = {
    Department.CYBTX: "CYBTX",
    Department.DESTINATION: "Destination",
    Department.TXSAAS: "TXSaaS",
}


class DepartmentAgentConfigurationError(RuntimeError):
    """Raised when the department agent registry is incomplete."""


class DepartmentAgentRegistry:
    def __init__(
        self,
        agents: Mapping[Department, DepartmentAgentPort],
    ) -> None:
        registered = set(agents)
        expected = set(Department)
        if registered != expected:
            missing = sorted(item.value for item in expected - registered)
            unexpected = sorted(item.value for item in registered - expected)
            raise DepartmentAgentConfigurationError(
                f"Invalid department agent registry; missing={missing}, "
                f"unexpected={unexpected}"
            )
        self._agents = dict(agents)

    def get(self, department: Department) -> DepartmentAgentPort:
        try:
            return self._agents[department]
        except KeyError as exc:
            raise DepartmentAgentConfigurationError(
                f"No department agent registered for {department.value}"
            ) from exc


def build_department_answerer(
    model: BaseChatModel,
    department: Department,
) -> Runnable:
    parser = PydanticOutputParser(pydantic_object=KnowledgeModelAnswer)
    prompt = DEPARTMENT_AGENT_PROMPT.partial(
        department_name=DEPARTMENT_NAMES[department],
        format_instructions=parser.get_format_instructions(),
    )
    return prompt | model.bind(response_format={"type": "json_object"}) | parser


class DepartmentKnowledgeAgent(DepartmentAgentPort):
    def __init__(
        self,
        department: Department,
        answerer: Runnable,
        knowledge_base: TravelXKnowledgeBase,
        skills: DepartmentSkillRegistry,
        *,
        knowledge_limit: int = 4,
    ) -> None:
        if knowledge_base.scope_department is not department:
            raise ValueError("Department agent requires a matching RAG scope")
        self._department = department
        self._answerer = answerer
        self._knowledge_base = knowledge_base
        self._skills = skills
        self._knowledge_limit = knowledge_limit

    @property
    def department(self) -> Department:
        return self._department

    async def run(self, request: DepartmentAgentRequest) -> DepartmentAgentResult:
        skill = self._skills.resolve(self.department, request.service_key)
        documents = self._knowledge_base.retrieve(
            request.question,
            request.service_key,
            limit=self._knowledge_limit,
        )
        retrieved_sources = {
            str(document.metadata["source_id"]): KnowledgeSource(
                source_id=str(document.metadata["source_id"]),
                title_ar=str(document.metadata["title_ar"]),
            )
            for document in documents
        }
        context = "\n\n".join(
            (
                f"[source_id={document.metadata['source_id']}]\n"
                f"{document.page_content}"
            )
            for document in documents
        )
        raw = await self._answerer.ainvoke(
            {
                "skill_name": skill.name_ar,
                "skill_instructions": skill.instructions_ar,
                "question": request.question,
                "context": context,
                "answer_mode": (
                    "rephrase" if request.explain_differently else "normal"
                ),
                "previous_answer": request.previous_answer or "none",
            }
        )
        model_answer = KnowledgeModelAnswer.model_validate(raw)
        source_ids = [
            source_id
            for source_id in model_answer.source_ids
            if source_id in retrieved_sources
        ]

        if not model_answer.sufficient_context or not source_ids:
            return DepartmentAgentResult(
                department=self.department,
                service_key=request.service_key,
                skill_key=skill.key,
                status=DepartmentAgentStatus.INSUFFICIENT_CONTEXT,
                knowledge=KnowledgeAnswerResult(
                    text=(
                        f"لا تتوفر لدى قسم {DEPARTMENT_NAMES[self.department]} "
                        "معلومات موثقة كافية للإجابة. يمكن تجهيز طلب للقسم المختص."
                    ),
                    sufficient_context=False,
                ),
            )

        return DepartmentAgentResult(
            department=self.department,
            service_key=request.service_key,
            skill_key=skill.key,
            status=DepartmentAgentStatus.ANSWERED,
            knowledge=KnowledgeAnswerResult(
                text=model_answer.answer_ar,
                sources=[retrieved_sources[source_id] for source_id in source_ids],
                sufficient_context=True,
            ),
        )


def build_department_agents(
    model: BaseChatModel,
    knowledge_base: TravelXKnowledgeBase,
    skills: DepartmentSkillRegistry,
    *,
    knowledge_limit: int = 4,
) -> dict[Department, DepartmentKnowledgeAgent]:
    return {
        department: DepartmentKnowledgeAgent(
            department,
            build_department_answerer(model, department),
            knowledge_base.for_department(department),
            skills,
            knowledge_limit=knowledge_limit,
        )
        for department in Department
    }