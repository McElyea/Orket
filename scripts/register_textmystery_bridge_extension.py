from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.runtime_paths import durable_root

EXTENSION_ID = "textmystery.bridge.extension"
WORKLOAD_ID = "textmystery_bridge_v1"


def _extension_dir(project_root: Path) -> Path:
    return project_root / "workspace" / "live_ext" / "textmystery_bridge"


def _manifest_payload() -> dict[str, Any]:
    return {
        "extension_id": EXTENSION_ID,
        "extension_version": "1.0.0",
        "extension_api_version": "1.0.0",
        "module": "textmystery_bridge_extension",
        "register_callable": "register",
        "workloads": [
            {
                "workload_id": WORKLOAD_ID,
                "workload_version": "1.0.0",
            }
        ],
    }


def _module_source() -> str:
    return """from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from orket.extensions import RunPlan


class TextMysteryBridgeWorkload:
    workload_id = "textmystery_bridge_v1"
    workload_version = "1.0.0"

    def __init__(self) -> None:
        self._compiled_by_plan_hash: dict[str, dict[str, Any]] = {}

    def compile(self, input_config: dict[str, Any]) -> RunPlan:
        operation = str(input_config.get("operation") or "parity-check").strip().lower()
        if operation not in {"parity-check", "leak-check"}:
            raise ValueError("operation must be 'parity-check' or 'leak-check'")

        endpoint_base_url = str(input_config.get("endpoint_base_url") or "http://127.0.0.1:8787").strip().rstrip("/")
        request_payload = input_config.get("payload") if isinstance(input_config.get("payload"), dict) else {}
        route = "/textmystery/parity-check" if operation == "parity-check" else "/textmystery/leak-check"
        response_payload = self._post_json(endpoint_base_url + route, request_payload)

        plan = RunPlan(
            workload_id=self.workload_id,
            workload_version=self.workload_version,
            actions=(),
            metadata={
                "bridge_operation": operation,
                "endpoint_base_url": endpoint_base_url,
                "request_payload": request_payload,
                "response_payload": response_payload,
            },
        )
        self._compiled_by_plan_hash[plan.plan_hash()] = dict(plan.metadata)
        return plan

    def validators(self):
        return []

    def summarize(self, run_artifacts: dict[str, Any]) -> dict[str, Any]:
        run_result = run_artifacts.get("run_result") if isinstance(run_artifacts.get("run_result"), dict) else {}
        plan_hash = str(run_result.get("plan_hash") or "")
        metadata = self._compiled_by_plan_hash.get(plan_hash, {})
        response_payload = metadata.get("response_payload") if isinstance(metadata.get("response_payload"), dict) else {}
        return {
            "ok": True,
            "bridge_operation": metadata.get("bridge_operation"),
            "endpoint_base_url": metadata.get("endpoint_base_url"),
            "contract_response": response_payload,
        }

    def required_materials(self):
        return []

    @staticmethod
    def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = Request(url=url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=10) as resp:  # nosec B310 - local bridge endpoint expected
                body = resp.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"bridge request failed status={exc.code} url={url} detail={detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"bridge request connection failed url={url} detail={exc}") from exc
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError("bridge endpoint returned non-object JSON")
        return parsed


def register(registry):
    registry.register_workload(TextMysteryBridgeWorkload())
"""


def _catalog_path() -> Path:
    path = durable_root() / "config" / "extensions_catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"extensions": []}, indent=2), encoding="utf-8")
    return path


def main() -> int:
    extension_dir = _extension_dir(PROJECT_ROOT)
    extension_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = extension_dir / "orket_extension.json"
    module_path = extension_dir / "textmystery_bridge_extension.py"
    manifest_path.write_text(json.dumps(_manifest_payload(), indent=2, sort_keys=True), encoding="utf-8")
    module_path.write_text(_module_source(), encoding="utf-8")

    catalog_path = _catalog_path()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = payload.get("extensions") if isinstance(payload.get("extensions"), list) else []
    rows = [row for row in rows if not (isinstance(row, dict) and str(row.get("extension_id")) == EXTENSION_ID)]
    rows.append(
        {
            "extension_id": EXTENSION_ID,
            "extension_version": "1.0.0",
            "extension_api_version": "1.0.0",
            "source": "workspace/live_ext/textmystery_bridge",
            "path": str(extension_dir),
            "module": "textmystery_bridge_extension",
            "register_callable": "register",
            "workloads": [{"workload_id": WORKLOAD_ID, "workload_version": "1.0.0"}],
        }
    )
    payload["extensions"] = rows
    catalog_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Registered extension_id={EXTENSION_ID} workload_id={WORKLOAD_ID}")
    print(f"Catalog: {catalog_path}")
    print(f"Module: {module_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
