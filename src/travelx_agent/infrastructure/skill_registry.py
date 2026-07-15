import json
from pathlib import Path

from travelx_agent.domain.department_agent import DepartmentSkill
from travelx_agent.domain.service_catalog import (
    SERVICE_CATALOG,
    Department,
    ServiceKey,
    get_service,
)


class SkillRegistryConfigurationError(RuntimeError):
    """Raised when department skills are missing, duplicated, or misrouted."""


class DepartmentSkillRegistry:
    def __init__(
        self,
        skills: list[DepartmentSkill],
        *,
        version: str,
    ) -> None:
        if not version.strip():
            raise SkillRegistryConfigurationError("Skill version cannot be empty")
        self._version = version.strip()
        self._skills = tuple(skills)
        self._by_service: dict[tuple[Department, ServiceKey], DepartmentSkill] = {}

        for skill in self._skills:
            for service_key in skill.service_keys:
                service = get_service(service_key)
                if service is None or service.primary_department is not skill.department:
                    raise SkillRegistryConfigurationError(
                        f"Skill {skill.key} cannot own service {service_key.value}"
                    )
                lookup_key = (skill.department, service_key)
                if lookup_key in self._by_service:
                    raise SkillRegistryConfigurationError(
                        f"Service {service_key.value} has more than one skill"
                    )
                self._by_service[lookup_key] = skill

        configured_services = {service_key for _, service_key in self._by_service}
        expected_services = set(SERVICE_CATALOG)
        if configured_services != expected_services:
            missing = sorted(
                service.value for service in expected_services - configured_services
            )
            unexpected = sorted(
                service.value for service in configured_services - expected_services
            )
            raise SkillRegistryConfigurationError(
                f"Skill coverage is incomplete; missing={missing}, "
                f"unexpected={unexpected}"
            )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "DepartmentSkillRegistry":
        skill_path = Path(path)
        if not skill_path.is_file():
            raise SkillRegistryConfigurationError(
                f"Skill file does not exist: {skill_path}"
            )
        try:
            payload = json.loads(skill_path.read_text(encoding="utf-8"))
            version = str(payload["version"])
            raw_skills = payload["skills"]
            skills = [DepartmentSkill.model_validate(item) for item in raw_skills]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SkillRegistryConfigurationError(
                f"Skill file is invalid: {skill_path}"
            ) from exc

        keys = [skill.key for skill in skills]
        if len(keys) != len(set(keys)):
            raise SkillRegistryConfigurationError("Every skill key must be unique")
        return cls(skills, version=version)

    @property
    def version(self) -> str:
        return self._version

    def resolve(
        self,
        department: Department,
        service_key: ServiceKey,
    ) -> DepartmentSkill:
        try:
            return self._by_service[(department, service_key)]
        except KeyError as exc:
            raise SkillRegistryConfigurationError(
                f"No skill maps {department.value} to {service_key.value}"
            ) from exc

    def for_department(self, department: Department) -> tuple[DepartmentSkill, ...]:
        return tuple(skill for skill in self._skills if skill.department is department)