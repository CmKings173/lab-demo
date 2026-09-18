def test_editable_package_surface_imports() -> None:
    import agent.openclaw.plugins.catalog_tools as catalog_tools
    import api.catalog as catalog_api
    import services.configuration.service as configuration_service
    import shared.tool_contracts as tool_contracts
    import workflow.orchestrator as orchestrator

    assert catalog_tools.CatalogTools
    assert catalog_api.search_products
    assert configuration_service.ProductConfigurationBuilder
    assert tool_contracts.TOOL_DEFINITIONS
    assert orchestrator.DeterministicWorkflow
