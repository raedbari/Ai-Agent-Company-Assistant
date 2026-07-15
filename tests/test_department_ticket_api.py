from fastapi.testclient import TestClient

from travelx_agent.api.dependencies import provide_ticket_repository
from travelx_agent.domain.service_catalog import Department
from travelx_agent.main import app


class RecordingTicketRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[Department, int]] = []

    async def list_by_department(
        self,
        department: Department,
        limit: int = 50,
    ) -> list:
        self.calls.append((department, limit))
        return []


def test_department_ticket_route_passes_department_and_limit() -> None:
    repository = RecordingTicketRepository()
    app.dependency_overrides[provide_ticket_repository] = lambda: repository

    try:
        response = TestClient(app).get(
            "/v1/departments/txsaas/tickets",
            params={"limit": 25},
        )
    finally:
        app.dependency_overrides.pop(provide_ticket_repository, None)

    assert response.status_code == 200
    assert response.json() == {
        "department": "txsaas",
        "tickets": [],
    }

    assert len(repository.calls) == 1
    department, limit = repository.calls[0]
    assert department.value == "txsaas"
    assert limit == 25


def test_department_ticket_route_rejects_unknown_department() -> None:
    repository = RecordingTicketRepository()
    app.dependency_overrides[provide_ticket_repository] = lambda: repository

    try:
        response = TestClient(app).get(
            "/v1/departments/unknown/tickets"
        )
    finally:
        app.dependency_overrides.pop(provide_ticket_repository, None)

    assert response.status_code == 422
    assert repository.calls == []