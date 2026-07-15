from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from travelx_agent.domain.knowledge import KnowledgeAnswerResult
from travelx_agent.domain.service_catalog import Department, ServiceKey


class DepartmentAgentStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    UNAVAILABLE = "unavailable"


class DepartmentSkill(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1)
    name_ar: str = Field(min_length=1)
    department: Department
    service_keys: tuple[ServiceKey, ...] = Field(min_length=1)
    instructions_ar: str = Field(min_length=10)


class DepartmentAgentRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    service_key: ServiceKey
    previous_answer: str | None = None
    explain_differently: bool = False


class DepartmentAgentResult(BaseModel):
    department: Department
    service_key: ServiceKey
    skill_key: str | None = None
    status: DepartmentAgentStatus
    knowledge: KnowledgeAnswerResult
    failure_code: str | None = None