from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


def _load_manifest(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Manifest must be a JSON object.")
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Manifest must include 'assets' as a list.")
    return payload


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_asset(asset: Dict[str, Any]) -> None:
    required = ["id", "url", "sha256", "target_path"]
    for key in required:
        if not str(asset.get(key) or "").strip():
            raise ValueError(f"Asset missing required field '{key}'.")


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as src, dest.open("wb") as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def _process_assets(assets: List[Dict[str, Any]], root: Path) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for asset in assets:
        _validate_asset(asset)
        asset_id = str(asset["id"])
        url = str(asset["url"])
        expected = str(asset["sha256"]).lower()
        target = root / str(asset["target_path"])
        target = target.resolve()

        _download(url, target)
        actual = _sha256_file(target).lower()
        ok = actual == expected
        if not ok:
            raise ValueError(
                f"Checksum mismatch for '{asset_id}': expected={expected} actual={actual} path={target}"
            )
        results.append({"id": asset_id, "path": str(target), "sha256": actual, "ok": True})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch SDK data assets from a manifest.")
    parser.add_argument(
        "--manifest",
        type=str,
        default="scripts/sdk/data_manifest.example.json",
        help="Manifest JSON containing assets[] entries.",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Project root for resolving target_path locations.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    root = Path(args.root).resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"manifest_not_found: {manifest_path}")

    payload = _load_manifest(manifest_path)
    assets = [item for item in list(payload.get("assets") or []) if isinstance(item, dict)]
    results = _process_assets(assets, root)

    print(
        json.dumps(
            {
                "ok": True,
                "manifest": str(manifest_path),
                "assets_fetched": len(results),
                "results": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise
