from travelx_agent.domain.service_catalog import Department, ServiceKey, get_service


def test_legacy_websites_key_is_normalized_to_canonical_service() -> None:
    service = get_service("websites")

    assert service is not None
    assert service.key is ServiceKey.WEBSITE_DEVELOPMENT
    assert service.primary_department is Department.TXSAAS
