"""Verified compiler file publication, called only inside an owned worker."""
import json
import shutil
from pathlib import Path

from orket.adapters.storage.verified_file import write_verified_bytes

side_effecting = True


def write_report(path: Path, payload: dict) -> None:
    write_verified_bytes(path, (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())


def capture_inputs(source: Path, relatives: tuple[str, ...], destination: Path, workspace: Path) -> None:
    """Retain only admitted compiler inputs; unrelated project state is not compiler input."""
    payload = {name: (source / name).read_bytes() for name in relatives if (source / name).is_file()}
    target = destination.resolve()
    if target == workspace.resolve() or not target.is_relative_to(workspace.resolve()):
        raise ValueError("REFORGER_INPUT_SNAPSHOT_OUT_OF_SURFACE")
    if target.exists():
        _files(target)
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for relative, raw in payload.items():
        write_verified_bytes(target / relative, raw)


def validate_output(workspace: Path, output: Path, protected: tuple[Path, ...]) -> None:
    root, target = workspace.resolve(), output.resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError("output_dir must be a strict child of the workspace")
    for item in protected:
        resolved = item.resolve()
        if resolved.is_relative_to(target) or target.is_relative_to(resolved):
            raise ValueError("output_dir overlaps compiler inputs or retained artifacts")


def _files(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        raise OSError("REFORGER_OUTPUT_MISSING")
    payload = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("REFORGER_OUTPUT_LINK")
        if path.is_file():
            payload[path.relative_to(root).as_posix()] = path.read_bytes()
    return payload


def publish_output(source: Path, output: Path, workspace: Path, protected: tuple[Path, ...]) -> None:
    """Verify every output byte before success; replacement is not a tree transaction."""
    validate_output(workspace, output, protected)
    payload = _files(source)
    if not payload:
        raise OSError("REFORGER_OUTPUT_EMPTY")
    if output.exists():
        _files(output)  # Refuse links before removing an admitted existing output tree.
        validate_output(workspace, output, protected)
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    for relative, raw in payload.items():
        write_verified_bytes(output / relative, raw)
    if _files(output) != payload:
        raise OSError("REFORGER_OUTPUT_UNVERIFIED")
