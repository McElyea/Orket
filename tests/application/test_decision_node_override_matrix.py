from types import SimpleNamespace

from orket.decision_nodes.registry import DecisionNodeRegistry


def test_runtime_override_matrix_process_rules_resolution(monkeypatch):
    monkeypatch.delenv("ORKET_API_RUNTIME_NODE", raising=False)
    monkeypatch.delenv("ORKET_TOOL_STRATEGY_NODE", raising=False)
    monkeypatch.delenv("ORKET_SANDBOX_POLICY_NODE", raising=False)
    monkeypatch.delenv("ORKET_ENGINE_RUNTIME_NODE", raising=False)
    monkeypatch.delenv("ORKET_LOADER_STRATEGY_NODE", raising=False)
    monkeypatch.delenv("ORKET_EXECUTION_RUNTIME_NODE", raising=False)
    monkeypatch.delenv("ORKET_PIPELINE_WIRING_NODE", raising=False)

    registry = DecisionNodeRegistry()

    api_custom = type(
        "ApiCustom",
        (),
        {
            "parse_allowed_origins": lambda self, v: ["custom"],
            "resolve_asset_id": lambda self, p, i: "X",
            "create_session_id": lambda self: "SID",
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
    engine_custom = type(
        "EngineCustom",
        (),
        {
            "bootstrap_environment": lambda self: None,
            "resolve_config_root": lambda self, config_root: config_root,
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
            "select_run_id": lambda self, session_id: "RUN",
            "select_epic_build_id": lambda self, build_id, epic_name, sanitize_name: "BUILD",
            "select_rock_session_id": lambda self, session_id: "ROCKRUN",
            "select_rock_build_id": lambda self, build_id, rock_name, sanitize_name: "ROCKBUILD",
        },
    )()
    pipeline_custom = type(
        "PipelineCustom",
        (),
        {
            "create_sandbox_orchestrator": lambda self, workspace, organization: object(),
            "create_webhook_database": lambda self: object(),
            "create_bug_fix_manager": lambda self, organization, webhook_db: object(),
            "create_orchestrator": lambda self, workspace, async_cards, snapshots, org, config_root, db_path, loader, sandbox_orchestrator: object(),
            "create_sub_pipeline": lambda self, parent_pipeline, epic_workspace, department: object(),
        },
    )()

    registry.register_api_runtime("api-custom", api_custom)
    registry.register_tool_strategy("tool-custom", tool_custom)
    registry.register_sandbox_policy("sandbox-custom", sandbox_custom)
    registry.register_engine_runtime("engine-custom", engine_custom)
    registry.register_loader_strategy("loader-custom", loader_custom)
    registry.register_execution_runtime("execution-custom", execution_custom)
    registry.register_pipeline_wiring("pipeline-custom", pipeline_custom)

    org = SimpleNamespace(
        process_rules={
            "api_runtime_node": "api-custom",
            "tool_strategy_node": "tool-custom",
            "sandbox_policy_node": "sandbox-custom",
            "engine_runtime_node": "engine-custom",
            "loader_strategy_node": "loader-custom",
            "execution_runtime_node": "execution-custom",
            "pipeline_wiring_node": "pipeline-custom",
        }
    )

    assert registry.resolve_api_runtime(org) is api_custom
    assert registry.resolve_tool_strategy(org) is tool_custom
    assert registry.resolve_sandbox_policy(org) is sandbox_custom
    assert registry.resolve_engine_runtime(org) is engine_custom
    assert registry.resolve_loader_strategy(org) is loader_custom
    assert registry.resolve_execution_runtime(org) is execution_custom
    assert registry.resolve_pipeline_wiring(org) is pipeline_custom


def test_runtime_override_matrix_env_precedence(monkeypatch):
    registry = DecisionNodeRegistry()
    api_custom = type(
        "ApiCustom",
        (),
        {
            "parse_allowed_origins": lambda self, v: ["custom"],
            "resolve_asset_id": lambda self, p, i: "X",
            "create_session_id": lambda self: "SID",
        },
    )()
    registry.register_api_runtime("api-custom", api_custom)

    monkeypatch.setenv("ORKET_API_RUNTIME_NODE", "api-custom")
    org = SimpleNamespace(process_rules={"api_runtime_node": "default"})

    assert registry.resolve_api_runtime(org) is api_custom

