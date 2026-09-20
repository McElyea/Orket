# Layer: contract. Controlled host ports; no provider execution claim.
import orket.interfaces.api as api_module

client = None


def test_preview_asset_uses_runtime_invocation(monkeypatch):
    """Layer: integration. Verifies preview construction now comes from the explicit API runtime host while invocation policy stays strategy-owned."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeBuilder:
        async def build_issue_preview(self, issue_id, asset_name, department):
            return {"mode": "issue", "issue_id": issue_id, "asset_name": asset_name, "department": department}

        async def build_rock_preview(self, asset_name, department):
            return {"mode": "rock", "asset_name": asset_name, "department": department}

        async def build_epic_preview(self, asset_name, department):
            return {"mode": "epic", "asset_name": asset_name, "department": department}

    monkeypatch.setattr(
        api_module._get_api_runtime_node(client.app),
        "resolve_preview_target",
        lambda path, issue_id: {"mode": "issue", "asset_name": "asset-x", "department": "core"},
    )
    monkeypatch.setattr(
        api_module._get_api_runtime_node(client.app),
        "resolve_preview_invocation",
        lambda target, issue_id: {
            "method_name": "build_issue_preview",
            "args": [issue_id, target["asset_name"], target["department"]],
            "unsupported_detail": "Unsupported preview mode 'issue'.",
        },
    )
    async def create_builder(_model_root):
        return FakeBuilder()

    monkeypatch.setattr(api_module._get_api_runtime_host(client.app), "create_preview_builder", create_builder)

    response = client.get(
        "/v1/system/preview-asset?path=model/core/epics/x.json&issue_id=ISSUE-9",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json() == {"mode": "issue", "issue_id": "ISSUE-9", "asset_name": "asset-x", "department": "core"}


def test_preview_asset_rejects_unsupported_mode(monkeypatch):
    """Layer: contract. Verifies preview routes still fail closed when runtime policy names an unsupported builder method."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeBuilder:
        async def build_epic_preview(self, asset_name, department):
            return {"asset_name": asset_name, "department": department}

    monkeypatch.setattr(
        api_module._get_api_runtime_node(client.app),
        "resolve_preview_target",
        lambda path, issue_id: {"mode": "custom", "asset_name": "asset-x", "department": "core"},
    )
    monkeypatch.setattr(
        api_module._get_api_runtime_node(client.app),
        "resolve_preview_invocation",
        lambda target, issue_id: {
            "method_name": "build_custom_preview",
            "args": [target["asset_name"], target["department"]],
            "unsupported_detail": "Unsupported preview mode 'custom'.",
        },
    )
    async def create_builder(_model_root):
        return FakeBuilder()

    monkeypatch.setattr(api_module._get_api_runtime_host(client.app), "create_preview_builder", create_builder)

    response = client.get(
        "/v1/system/preview-asset?path=model/core/epics/x.json",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 400
    assert "Unsupported preview mode" in response.json()["detail"]


def test_preview_asset_uses_runtime_error_detail_for_unsupported_mode(monkeypatch):
    """Layer: contract. Verifies preview unsupported-detail shaping survives the move to explicit host-owned builder construction."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeBuilder:
        async def build_epic_preview(self, asset_name, department):
            return {"asset_name": asset_name, "department": department}

    monkeypatch.setattr(
        api_module._get_api_runtime_node(client.app),
        "resolve_preview_target",
        lambda path, issue_id: {"mode": "custom", "asset_name": "asset-x", "department": "core"},
    )
    monkeypatch.setattr(
        api_module._get_api_runtime_node(client.app),
        "resolve_preview_invocation",
        lambda target, issue_id: {
            "method_name": "build_custom_preview",
            "args": [target["asset_name"], target["department"]],
            "unsupported_detail": f"Unsupported preview invocation 'build_custom_preview' for mode '{target['mode']}'",
        },
    )
    async def create_builder(_model_root):
        return FakeBuilder()

    monkeypatch.setattr(api_module._get_api_runtime_host(client.app), "create_preview_builder", create_builder)

    response = client.get(
        "/v1/system/preview-asset?path=model/core/epics/x.json",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported preview invocation 'build_custom_preview' for mode 'custom'"


def test_chat_driver_uses_runtime_invocation(monkeypatch):
    """Layer: contract. Verifies chat-driver construction now comes from the explicit API runtime host."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    class FakeDriver:
        def __init__(self):
            self.provider, self.closed = self, False

        async def close(self):
            self.closed = True

        async def process_custom(self, message):
            captured["message"] = message
            return f"echo:{message}"

    driver = FakeDriver()

    async def create_driver():
        return driver

    monkeypatch.setattr(api_module._get_api_runtime_host(client.app), "create_chat_driver", create_driver)
    monkeypatch.setattr(
        api_module._get_api_runtime_node(client.app),
        "resolve_chat_driver_invocation",
        lambda message: {"method_name": "process_custom", "args": [message]},
    )

    response = client.post(
        "/v1/system/chat-driver",
        json={"message": "hello"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"response": "echo:hello"}
    assert captured["message"] == "hello"
    assert driver.closed


def test_chat_driver_rejects_unsupported_runtime_method(monkeypatch):
    """Layer: contract. Verifies chat-driver routes still fail closed when runtime policy names a missing driver method."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeDriver:
        def __init__(self):
            self.provider, self.closed = self, False

        async def close(self):
            self.closed = True

        async def process_request(self, message):
            return f"echo:{message}"

    driver = FakeDriver()

    async def create_driver():
        return driver

    monkeypatch.setattr(api_module._get_api_runtime_host(client.app), "create_chat_driver", create_driver)
    monkeypatch.setattr(
        api_module._get_api_runtime_node(client.app),
        "resolve_chat_driver_invocation",
        lambda message: {"method_name": "missing_method", "args": [message]},
    )

    response = client.post(
        "/v1/system/chat-driver",
        json={"message": "hello"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert "Unsupported chat driver method" in response.json()["detail"]
    assert driver.closed
