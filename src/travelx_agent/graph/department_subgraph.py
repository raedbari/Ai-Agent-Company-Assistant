import asyncio
from collections.abc import Mapping
from typing import NotRequired, TypedDict

from langgraph.errors import NodeError, NodeTimeoutError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from travelx_agent.application.department_agent import DEPARTMENT_NAMES
from travelx_agent.application.ports.department_agent import DepartmentAgentPort
from travelx_agent.core.config import Settings
from travelx_agent.domain.department_agent import (
    DepartmentAgentRequest,
    DepartmentAgentResult,
    DepartmentAgentStatus,
)
from travelx_agent.domain.knowledge import KnowledgeAnswerResult
from travelx_agent.domain.service_catalog import Department


class DepartmentAgentState(TypedDict):
    request: DepartmentAgentRequest
    result: NotRequired[DepartmentAgentResult]


_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_transient_department_error(error: Exception) -> bool:
    if isinstance(error, (NodeTimeoutError, TimeoutError, ConnectionError)):
        return True
    return getattr(error, "status_code", None) in _TRANSIENT_STATUS_CODES


def unavailable_department_result(
    department: Department,
    request: DepartmentAgentRequest,
    failure_code: str,
) -> DepartmentAgentResult:
    return DepartmentAgentResult(
        department=department,
        service_key=request.service_key,
        status=DepartmentAgentStatus.UNAVAILABLE,
        failure_code=failure_code,
        knowledge=KnowledgeAnswerResult(
            text=(
                f"قسم {DEPARTMENT_NAMES[department]} غير متاح مؤقتًا. "
                "تستطيع متابعة خدمات الأقسام الأخرى أو المحاولة لاحقًا."
            ),
            sufficient_context=False,
        ),
    )


def build_department_subgraph(
    agent: DepartmentAgentPort,
    settings: Settings,
) -> CompiledStateGraph:
    async def answer_question(state: DepartmentAgentState) -> dict:
        return {"result": await agent.run(state["request"])}

    def recover_from_failure(
        state: DepartmentAgentState,
        error: NodeError,
    ) -> dict:
        if not is_transient_department_error(error.error):
            raise error.error
        return {
            "result": unavailable_department_result(
                agent.department,
                state["request"],
                type(error.error).__name__,
            )
        }

    graph = StateGraph(DepartmentAgentState)
    graph.add_node(
        "answer_department_question",
        answer_question,
        retry_policy=RetryPolicy(
            max_attempts=settings.department_agent_max_attempts,
            initial_interval=0.25,
            max_interval=1.0,
            jitter=True,
            retry_on=is_transient_department_error,
        ),
        timeout=settings.department_agent_attempt_timeout_seconds,
        error_handler=recover_from_failure,
    )
    graph.add_edge(START, "answer_department_question")
    graph.add_edge("answer_department_question", END)
    return graph.compile(name=f"{agent.department.value}_department_agent")


class LocalDepartmentAgentAdapter(DepartmentAgentPort):
    def __init__(
        self,
        department: Department,
        subgraph: CompiledStateGraph,
        *,
        total_timeout_seconds: float,
    ) -> None:
        self._department = department
        self._subgraph = subgraph
        self._total_timeout_seconds = total_timeout_seconds

    @property
    def department(self) -> Department:
        return self._department

    async def run(
        self,
        request: DepartmentAgentRequest,
    ) -> DepartmentAgentResult:
        try:
            async with asyncio.timeout(self._total_timeout_seconds):
                state = await self._subgraph.ainvoke(
                    {"request": request},
                    config={
                        "run_name": f"{self.department.value}_department_subgraph",
                        "tags": [
                            "department-agent",
                            self.department.value,
                            request.service_key.value,
                        ],
                        "metadata": {
                            "department": self.department.value,
                            "service_key": request.service_key.value,
                            "knowledge_scope": self.department.value,
                        },
                    },
                )
        except TimeoutError:
            return unavailable_department_result(
                self.department,
                request,
                "TotalTimeoutError",
            )

        result = state.get("result")
        if not isinstance(result, DepartmentAgentResult):
            raise TypeError("Department subgraph returned an invalid result")
        return result


def build_local_department_agents(
    agents: Mapping[Department, DepartmentAgentPort],
    settings: Settings,
) -> dict[Department, DepartmentAgentPort]:
    return {
        department: LocalDepartmentAgentAdapter(
            department,
            build_department_subgraph(agent, settings),
            total_timeout_seconds=settings.department_agent_total_timeout_seconds,
        )
        for department, agent in agents.items()
    }