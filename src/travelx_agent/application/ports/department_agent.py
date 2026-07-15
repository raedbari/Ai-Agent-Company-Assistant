from typing import Protocol

from travelx_agent.domain.department_agent import (
    DepartmentAgentRequest,
    DepartmentAgentResult,
)
from travelx_agent.domain.service_catalog import Department


class DepartmentAgentPort(Protocol):
    @property
    def department(self) -> Department: ...

    async def run(self, request: DepartmentAgentRequest) -> DepartmentAgentResult: ...