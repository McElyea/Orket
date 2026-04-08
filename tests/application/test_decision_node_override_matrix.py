from types import SimpleNamespace

from orket.decision_nodes.registry import DecisionNodeRegistry


def test_runtime_override_matrix_process_rules_resolution(monkeypatch):
    """Layer: contract. Verifies process-rule overrides still resolve for the surviving decision-node families."""
    monkeypatch.delenv("ORKET_API_RUNTIME_NODE", raising=False)
    monkeypatch.delenv("ORKET_TOOL_STRATEGY_NODE", raising=False)
    monkeypatch.delenv("ORKET_SANDBOX_POLICY_NODE", raising=False)
    monkeypatch.delenv("ORKET_LOADER_STRATEGY_NODE", raising=False)
    monkeypatch.delenv("ORKET_EXECUTION_RUNTIME_NODE", raising=False)

    registry = DecisionNodeRegistry()

    api_custom = type(
        "ApiCustom",
        (),
        {
            "parse_allowed_origins": lambda self, v: ["custom"],
            "resolve_asset_id": lambda self, p, i: "X",
        },
    )()
    tool_custom = type("ToolCustom", (), {"compose": lambda self, toolbox: {}})()
    sandbox_custom = type(
        "SandboxCustom",
        (),
        {
            "build_sandbox_id": lambda self, rock_id: "sandbox-custom",
            "build_compose_project": lambda self, sandbox_id: "project-custom",
            "get_database_url": lambda self, tech_stack, ports, db_password="": "db://custom",
            "generate_compose_file": lambda self, sandbox, db_password, admin_password: "version: '3.8'",
        },
    )()
    loader_custom = type(
        "LoaderCustom",
        (),
        {
            "organization_modular_paths": lambda self, config_dir: (config_dir / "a.json", config_dir / "b.json"),
            "organization_fallback_paths": lambda self, config_dir, model_dir: [config_dir / "organization.json"],
            "department_paths": lambda self, config_dir, model_dir, name: [config_dir / f"{name}.json"],
            "asset_paths": lambda self, config_dir, model_dir, dept, category, name: [config_dir / category / f"{name}.json"],
            "list_asset_search_paths": lambda self, config_dir, model_dir, dept, category: [config_dir / category],
            "apply_organization_overrides": lambda self, org, get_setting: org,
        },
    )()
    execution_custom = type(
        "ExecutionCustom",
        (),
        {
            "select_epic_build_id": lambda self, build_id, epic_name, sanitize_name: "BUILD",
            "select_epic_collection_build_id": lambda self, build_id, collection_name, sanitize_name: "COLLECTIONBUILD",
        },
    )()

    registry.register_api_runtime("api-custom", api_custom)
    registry.register_tool_strategy("tool-custom", tool_custom)
    registry.register_sandbox_policy("sandbox-custom", sandbox_custom)
    registry.register_loader_strategy("loader-custom", loader_custom)
    registry.register_execution_runtime("execution-custom", execution_custom)

    org = SimpleNamespace(
        process_rules={
            "api_runtime_node": "api-custom",
            "tool_strategy_node": "tool-custom",
            "sandbox_policy_node": "sandbox-custom",
            "loader_strategy_node": "loader-custom",
            "execution_runtime_node": "execution-custom",
        }
    )

    assert registry.resolve_api_runtime(org) is api_custom
    assert registry.resolve_tool_strategy(org) is tool_custom
    assert registry.resolve_sandbox_policy(org) is sandbox_custom
    assert registry.resolve_loader_strategy(org) is loader_custom
    assert registry.resolve_execution_runtime(org) is execution_custom


def test_runtime_override_matrix_env_precedence(monkeypatch):
    """Layer: contract. Verifies env overrides still win over process rules on the surviving API runtime seam."""
    registry = DecisionNodeRegistry()
    api_custom = type(
        "ApiCustom",
        (),
        {
            "parse_allowed_origins": lambda self, v: ["custom"],
            "resolve_asset_id": lambda self, p, i: "X",
        },
    )()
    registry.register_api_runtime("api-custom", api_custom)

    monkeypatch.setenv("ORKET_API_RUNTIME_NODE", "api-custom")
    org = SimpleNamespace(process_rules={"api_runtime_node": "default"})

    assert registry.resolve_api_runtime(org) is api_custom

