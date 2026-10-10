"""Native external report package preparation for public task acceptance."""
import json
import shutil
from pathlib import Path

import yaml

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "governed-report"


def prepare_report_task(root: Path):
    extension = root / "extension"
    shutil.copytree(EXAMPLE, extension, ignore=shutil.ignore_patterns("__pycache__"))
    manifest_path = extension / "extension.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    catalog = root / "catalog.json"
    catalog.write_text(json.dumps({"extensions": [{
        "extension_id": manifest["extension_id"], "extension_version": manifest["extension_version"],
        "extension_api_version": "1.0.0", "source": "independent-report-example", "path": str(extension),
        "contract_style": "sdk_v0", "manifest_path": str(manifest_path),
        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"], "manifest_entries": manifest["workloads"],
    }]}), encoding="utf-8")
    return catalog, extension / "submission.json", extension / "inputs.json"


def report_response():
    return {"sections": {"summary": "The supplied README omits installation instructions."},
            "source_refs": ["snapshot:readme", "snapshot:conventions"],
            "limitations": ["Only the two supplied documents were inspected."], "advisory": True}
