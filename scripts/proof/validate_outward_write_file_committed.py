#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.outward_run_witness_package import load_witness_package
from scripts.proof.outward_run_witness_ledger import verify_committed_artifact

DEFAULT_OUTPUT = Path("benchmarks/results/proof/outward_write_file_validation.json")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate committed write_file artifact bytes from an outward package.")
    parser.add_argument("--package", dest="package_path", required=True, help="Path to outward witness package.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Stable validation report output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted validation report.")
    return parser.parse_args(argv)


def validate_package_artifact(package_path: Path) -> dict[str, object]:
    loaded = load_witness_package(package_path)
    if not loaded.ok or loaded.package is None:
        return _report(result="rejected", failure_code=str(loaded.failure_code or "package_load_failed"))
    artifact = verify_committed_artifact(loaded.package)
    failure_code = artifact.get("failure_code")
    return _report(
        result="accepted" if artifact.get("result") == "pass" else "rejected",
        failure_code=str(failure_code) if failure_code else None,
        artifact_digest=str(artifact.get("artifact_digest") or ""),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output = Path(str(args.output)).resolve()
    report = validate_package_artifact(Path(str(args.package_path)).resolve())
    persisted = write_payload_with_diff_ledger(output, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"result={persisted.get('result')}",
                    f"missing_evidence={','.join(str(item) for item in persisted.get('missing_evidence') or [])}",
                    f"output={output}",
                ]
            )
        )
    return 0 if persisted.get("result") == "accepted" else 1


def _report(*, result: str, failure_code: str | None, artifact_digest: str = "") -> dict[str, object]:
    missing = [failure_code] if failure_code else []
    return {
        "schema_version": "outward_write_file_committed_validation.v1",
        "observed_path": "primary" if result == "accepted" else "blocked",
        "observed_result": "success" if result == "accepted" else "failure",
        "result": result,
        "artifact_role": "committed_output",
        "artifact_digest": artifact_digest,
        "missing_evidence": missing,
    }


if __name__ == "__main__":
    raise SystemExit(main())
