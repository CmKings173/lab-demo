def test_editable_package_surface_imports() -> None:
    import lab1_finetune.data.schema as dataset_schema
    import lab2_rag_agent.catalog.api as catalog_api
    import lab2_rag_agent.openclaw.plugins.catalog_tools as catalog_tools
    import lab3_workflow.configuration.service as configuration_service
    import lab3_workflow.workflow.orchestrator as orchestrator
    import shared.tool_contracts as tool_contracts

    assert dataset_schema.FineTuneExample
    assert catalog_tools.CatalogTools
    assert catalog_api.search_products
    assert configuration_service.ProductConfigurationBuilder
    assert tool_contracts.TOOL_DEFINITIONS
    assert orchestrator.DeterministicWorkflow


def test_package_discovery_excludes_removed_zombie_namespaces() -> None:
    from setuptools import find_packages

    packages = set(find_packages())

    assert {"shared", "lab1_finetune", "lab2_rag_agent", "lab3_workflow", "adapters"} <= packages
    assert not any(
        package == root or package.startswith(f"{root}.")
        for package in packages
        for root in ("services", "agent", "api", "mocks", "tests")
    )
