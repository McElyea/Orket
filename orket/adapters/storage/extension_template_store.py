"""Materialize packaged template data in an owned filesystem worker."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from importlib.resources import files
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from orket.adapters.execution.owned_io import run_owned_thread


class ExtensionTemplateMissing(FileNotFoundError):
    pass


class ExtensionTargetExists(FileExistsError):
    pass


@dataclass(frozen=True)
class MaterializedTemplate:
    template: str
    copied_file_count: int


class ExtensionTemplateStore:
    side_effecting = True

    async def materialize(self, template_name: str, target: Path, *, force: bool) -> MaterializedTemplate:
        return await run_owned_thread(partial(self._materialize, template_name, target, force),
                                      label="extension-template-materialization")

    def _materialize(self, template_name: str, target: Path, force: bool) -> MaterializedTemplate:
        source = files("orket").joinpath("runtime", "config", "assets", "extension_templates", template_name+".zip")
        if not source.is_file():
            raise ExtensionTemplateMissing(f"Template not found: {source}")
        destination = target.resolve()
        if destination.exists() and not force:
            raise ExtensionTargetExists(f"Target already exists: {destination}")
        with ZipFile(BytesIO(source.read_bytes())) as archive:
            payloads = self._capture_entries(archive, destination)
        for output, payload in payloads:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(payload)
            if output.read_bytes() != payload:
                raise OSError(f"Template file publication was not verified: {output}")
        return MaterializedTemplate(str(source), len(payloads))

    @staticmethod
    def _capture_entries(archive: ZipFile, destination: Path) -> tuple[tuple[Path, bytes], ...]:
        entries, seen = [], set()
        for member in archive.infolist():
            # ZipInfo normalizes backslashes on Windows; validate the serialized
            # name before that host-specific normalization can hide it.
            raw_name = member.orig_filename
            relative = PurePosixPath(raw_name)
            if (relative.is_absolute() or ".." in relative.parts or "\\" in raw_name
                    or ":" in raw_name or member.is_dir()):
                raise ValueError(f"Invalid packaged template member: {raw_name}")
            output = destination.joinpath(*relative.parts).resolve()
            if not output.is_relative_to(destination) or output in seen:
                raise ValueError(f"Packaged template member escapes or aliases a target: {member.filename}")
            seen.add(output)
            entries.append((output, archive.read(member)))
        if not entries:
            raise ValueError("Packaged template has no files")
        return tuple(entries)
