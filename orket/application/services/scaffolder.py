from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


@dataclass(frozen=True)
class ScaffoldSpec:
    required_directories: tuple[str, ...]
    required_files: Dict[str, str]
    forbidden_extensions: tuple[str, ...]
    scan_roots: tuple[str, ...]


class ScaffoldValidationError(Exception):
    """Raised when scaffold validation fails."""


class Scaffolder:
    """
    Deterministic project scaffolder.

    Generates a predictable base tree and validates required structure.
    """

    _DEFAULT_DIRECTORIES: tuple[str, ...] = (
        "agent_output/src",
        "agent_output/tests",
        "agent_output/config",
        "agent_output/scripts",
        "agent_output/docs",
    )
    _DEFAULT_FILES: Dict[str, str] = {
        "agent_output/README.md": "# Orket Scaffold\n\nDeterministic project baseline.\n",
        "agent_output/.env.example": "# Add environment variables here\n",
        "agent_output/src/__init__.py": "",
        "agent_output/tests/.gitkeep": "",
    }
    _DEFAULT_FORBIDDEN_EXTENSIONS: tuple[str, ...] = (".exe", ".dll", ".so", ".dylib")
    _DEFAULT_SCAN_ROOTS: tuple[str, ...] = ("agent_output",)

    def __init__(self, workspace_root: Path, file_tools: Any, organization: Any = None):
        self.workspace_root = workspace_root
        self.file_tools = file_tools
        self.organization = organization

    async def ensure(self) -> Dict[str, Any]:
        spec = self._resolve_spec()

        created_dirs = await self._ensure_directories(spec.required_directories)
        created_files = await self._ensure_files(spec.required_files)
        await self._validate_required_structure(spec)
        violations = await self._find_forbidden_extensions(
            forbidden_extensions=spec.forbidden_extensions,
            scan_roots=spec.scan_roots,
        )
        if violations:
            raise ScaffoldValidationError(
                "Forbidden file types detected: " + ", ".join(sorted(violations))
            )

        return {
            "created_directories": created_dirs,
            "created_files": created_files,
            "required_directories": list(spec.required_directories),
            "required_files": sorted(spec.required_files.keys()),
            "forbidden_extensions": list(spec.forbidden_extensions),
        }

    def _resolve_spec(self) -> ScaffoldSpec:
        rules = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            rules = self.organization.process_rules

        required_directories = self._normalize_str_list(
            rules.get("scaffolder_required_directories"),
            self._DEFAULT_DIRECTORIES,
        )
        required_files = self._normalize_file_map(
            rules.get("scaffolder_required_files"),
            self._DEFAULT_FILES,
        )
        forbidden_extensions = self._normalize_str_list(
            rules.get("scaffolder_forbidden_extensions"),
            self._DEFAULT_FORBIDDEN_EXTENSIONS,
        )
        scan_roots = self._normalize_str_list(
            rules.get("scaffolder_scan_roots"),
            self._DEFAULT_SCAN_ROOTS,
        )

        return ScaffoldSpec(
            required_directories=tuple(required_directories),
            required_files=dict(required_files),
            forbidden_extensions=tuple(forbidden_extensions),
            scan_roots=tuple(scan_roots),
        )

    async def _ensure_directories(self, directories: Sequence[str]) -> List[str]:
        created: List[str] = []
        for rel_dir in directories:
            path = self.workspace_root / rel_dir
            existed = await asyncio.to_thread(path.exists)
            if not existed:
                await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
                created.append(rel_dir)
        return created

    async def _ensure_files(self, required_files: Mapping[str, str]) -> List[str]:
        created: List[str] = []
        for rel_path, content in required_files.items():
            path = self.workspace_root / rel_path
            exists = await asyncio.to_thread(path.exists)
            if exists:
                continue
            await self.file_tools.write_file(rel_path, content)
            created.append(rel_path)
        return created

    async def _validate_required_structure(self, spec: ScaffoldSpec) -> None:
        missing_dirs: List[str] = []
        missing_files: List[str] = []

        for rel_dir in spec.required_directories:
            if not await asyncio.to_thread((self.workspace_root / rel_dir).is_dir):
                missing_dirs.append(rel_dir)
        for rel_file in spec.required_files.keys():
            if not await asyncio.to_thread((self.workspace_root / rel_file).is_file):
                missing_files.append(rel_file)

        if missing_dirs or missing_files:
            parts = []
            if missing_dirs:
                parts.append("missing directories: " + ", ".join(sorted(missing_dirs)))
            if missing_files:
                parts.append("missing files: " + ", ".join(sorted(missing_files)))
            raise ScaffoldValidationError("; ".join(parts))

    async def _find_forbidden_extensions(
        self,
        *,
        forbidden_extensions: Sequence[str],
        scan_roots: Sequence[str],
    ) -> List[str]:
        normalized_ext = tuple(ext.lower() for ext in forbidden_extensions if ext)
        if not normalized_ext:
            return []

        violations: List[str] = []
        for rel_root in scan_roots:
            root = self.workspace_root / rel_root
            if not await asyncio.to_thread(root.exists):
                continue
            files = await asyncio.to_thread(lambda: [p for p in root.rglob("*") if p.is_file()])
            for file_path in files:
                if file_path.suffix.lower() in normalized_ext:
                    violations.append(str(file_path.relative_to(self.workspace_root)).replace("\\", "/"))
        return violations

    @staticmethod
    def _normalize_str_list(raw: Any, default: Iterable[str]) -> List[str]:
        if isinstance(raw, list):
            values = [str(item).strip() for item in raw if str(item).strip()]
            if values:
                return values
        return [str(item).strip() for item in default if str(item).strip()]

    @staticmethod
    def _normalize_file_map(raw: Any, default: Mapping[str, str]) -> Dict[str, str]:
        if isinstance(raw, dict):
            normalized = {}
            for key, value in raw.items():
                key_str = str(key).strip()
                if not key_str:
                    continue
                normalized[key_str] = str(value)
            if normalized:
                return normalized
        return dict(default)
