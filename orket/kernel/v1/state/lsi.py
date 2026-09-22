"""Application-owned native local state over captured inputs and one filesystem adapter."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.storage import kernel_state_store as store
from orket.application.services.kernel_invocation_inputs import capture_kernel_invocation_root
from orket.application.services.kernel_triplet_input_service import capture_kernel_triplet
from orket.core.contracts.kernel_triplet import RefSource, TripletDigests, plan_kernel_triplet
from orket.core.contracts.kernel_triplet import iter_link_refs as _iter_refs_from_links
from orket.kernel.v1.contracts import KernelIssue

from .layout import (
    DIR_COMMITTED,
    DIR_STAGING,
    LSI_VERSION,
)
from .layout import (
    event_line as _event_line,
)
from .layout import (
    objects_path as _objects_path,
)
from .layout import (
    refs_by_id_path as _refs_by_id_path,
)
from .layout import (
    scope_root as _scope_root,
)
from .layout import (
    triplets_dir as _triplets_dir,
)
from .layout import (
    triplets_path as _triplets_path,
)
from .layout import (
    write_json as _atomic_write_json,
)

E_LSI_ORPHAN_TARGET = "E_LSI_ORPHAN_TARGET"
I_REF_INDEX_LAG = "I_REF_INDEX_LAG"


class LocalSovereignIndex:
    """
    Minimal Spec-002 LSI v1 implementation.
    This file intentionally focuses on:
      - disk anatomy
      - canonicalization + structural digest
      - staging/committed scopes
      - refs/by_id symbol table (non-owning, multi-source)
      - link integrity lookup (orphan detection) with Self > Staging > Committed order

    Promotion/pruning across scopes belongs in promotion.py, but we DO perform
    stem-scoped pruning within the SAME scope on update to prevent duplicates.
    """

    def __init__(self, root: str) -> None:
        self._workspace_inputs = capture_kernel_invocation_root(root)

    @property
    def root(self) -> str:
        return self._workspace_inputs.root

    # ---------- Write paths (staging) ----------

    def stage_triplet(
        self, *, run_id: str, turn_id: str, stem: str,
        body: dict[str, Any], links: dict[str, Any], manifest: dict[str, Any],
    ) -> TripletDigests:
        """Capture the complete triplet before publishing any local object or index."""
        require_sync_context(code="E_KERNEL_STATE_REQUIRES_ASYNC_OWNER")
        stem = stem.replace("\\", "/").strip("/")
        plan = plan_kernel_triplet(capture_kernel_triplet(body, links, manifest), stem=stem)
        scope_root = _scope_root(self.root, DIR_STAGING, run_id, turn_id)
        record_path = _triplets_path(scope_root, stem)
        grouped: dict[tuple[str, str], list[RefSource]] = {}
        for ref_type, ref_id, source in plan.references:
            _refs_by_id_path(scope_root, ref_type, ref_id)
            grouped.setdefault((ref_type, ref_id), []).append(source)
        for digest, content in plan.objects:
            self._put_object(scope_root, digest, content)
        _atomic_write_json(record_path, {
            "lsi_version": LSI_VERSION, "stem": stem, "dto_type": plan.digests.dto_type,
            "body_digest": plan.digests.body_digest, "links_digest": plan.digests.links_digest,
            "manifest_digest": plan.digests.manifest_digest, "updated_at_turn": turn_id,
        })
        self._update_refs_by_id_grouped(scope_root, grouped)
        return plan.digests

    # ---------- Read helpers (tests + kernel) ----------

    def read_triplet_record(
        self, *, scope: str, stem: str, run_id: str | None = None, turn_id: str | None = None
    ) -> dict[str, Any] | None:
        require_sync_context(code="E_KERNEL_STATE_REQUIRES_ASYNC_OWNER")
        stem = stem.replace("\\", "/").strip("/")
        scope_root = (
            _scope_root(self.root, scope, run_id, turn_id) if scope == DIR_STAGING else _scope_root(self.root, scope)
        )
        path = _triplets_path(scope_root, stem)
        if not store.exists(path):
            return None
        payload = store.read_json(path)
        if not isinstance(payload, dict):
            raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
        return payload

    def read_refs_sources(
        self,
        *,
        scope: str,
        ref_type: str,
        ref_id: str,
        run_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[dict[str, Any]]:
        require_sync_context(code="E_KERNEL_STATE_REQUIRES_ASYNC_OWNER")
        scope_root = (
            _scope_root(self.root, scope, run_id, turn_id) if scope == DIR_STAGING else _scope_root(self.root, scope)
        )
        path = _refs_by_id_path(scope_root, ref_type, ref_id)
        if not store.exists(path):
            return []
        data = store.read_json(path)
        sources = data.get("sources") if isinstance(data, dict) else None
        if not isinstance(sources, list) or any(not isinstance(source, dict) for source in sources):
            raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
        # Return exactly as stored (already canonicalized & sorted)
        return [s for s in sources if isinstance(s, dict)]

    # ---------- Validation (link integrity) ----------

    def validate_links_against_index(
        self,
        *,
        run_id: str,
        turn_id: str,
        stem: str,
    ) -> tuple[str, list[KernelIssue], list[str]]:
        """
        Minimal link integrity law:
          - Extract all {type,id} from /links for the staged stem.
          - Build visibility set from:
              1) committed created identities
              2) staged created identities (from bodies/manifests only)
          - Links never create visibility.
          - Missing => FAIL E_LSI_ORPHAN_TARGET at pointer to /id
        Returns (outcome, issues, events)
        """
        require_sync_context(code="E_KERNEL_STATE_REQUIRES_ASYNC_OWNER")
        stem = stem.replace("\\", "/").strip("/")
        events: list[str] = []

        # Load staged triplet record
        staged_root = _scope_root(self.root, DIR_STAGING, run_id, turn_id)
        triplet = self.read_triplet_record(scope=DIR_STAGING, stem=stem, run_id=run_id, turn_id=turn_id)
        if not triplet:
            missing_triplet_issues = [
                KernelIssue(
                    level="FAIL",
                    stage="lsi",
                    code=E_LSI_ORPHAN_TARGET,
                    location="/ci/schema",
                    message="Triplet not found in staging for validation.",
                    details={"stem": stem, "run_id": run_id, "turn_id": turn_id},
                )
            ]
            events.append(
                _event_line("FAIL", "lsi", E_LSI_ORPHAN_TARGET, "/ci/schema", "Triplet missing in staging.", stem=stem)
            )
            return "FAIL", missing_triplet_issues, events

        links_digest = triplet.get("links_digest")
        if not isinstance(links_digest, str):
            missing_links_digest_issues = [
                KernelIssue(
                    level="FAIL",
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                    location="/manifest",
                    message="Triplet record missing links_digest.",
                    details={"stem": stem},
                )
            ]
            events.append(
                _event_line(
                    "FAIL",
                    "base_shape",
                    "E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                    "/manifest",
                    "Triplet record missing links_digest.",
                    stem=stem,
                )
            )
            return "FAIL", missing_links_digest_issues, events

        links_obj = self._get_object_json(staged_root, links_digest)
        if not isinstance(links_obj, dict):
            invalid_links_object_issues = [
                KernelIssue(
                    level="FAIL",
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_LINKS_VALUE",
                    location="/links",
                    message="Links object must be a JSON object.",
                    details={"stem": stem},
                )
            ]
            events.append(
                _event_line(
                    "FAIL",
                    "base_shape",
                    "E_BASE_SHAPE_INVALID_LINKS_VALUE",
                    "/links",
                    "Links object must be a JSON object.",
                    stem=stem,
                )
            )
            return "FAIL", invalid_links_object_issues, events

        # Evaluate refs deterministically in pointer order
        refs = sorted(_iter_refs_from_links(links_obj), key=lambda r: (r[2], r[0], r[1]))

        committed_visible = self._collect_created_identities(_scope_root(self.root, DIR_COMMITTED))
        staged_visible = self._collect_created_identities(staged_root)
        visible_identities = committed_visible | staged_visible

        issues: list[KernelIssue] = []
        for ref_type, ref_id, ptr, relationship in refs:
            id_ptr = f"{ptr}/id"
            ref_identity = f"{ref_type}:{ref_id}"
            if ref_identity not in visible_identities:
                issues.append(
                    KernelIssue(
                        level="FAIL",
                        stage="lsi",
                        code=E_LSI_ORPHAN_TARGET,
                        location=id_ptr,
                        message="Reference target not visible in committed or staged creations.",
                        details={"type": ref_type, "id": ref_id, "relationship": relationship},
                    )
                )
            else:
                indexed_layer = self._lookup_ref_visibility(run_id, turn_id, stem, ref_type, ref_id)
                if indexed_layer is None:
                    found_layer = "StagedCreation" if ref_identity in staged_visible else "Committed"
                    events.append(
                        _event_line(
                            "INFO",
                            "lsi",
                            I_REF_INDEX_LAG,
                            id_ptr,
                            "Reference target exists in triplets but has not reached refs/by_id yet.",
                            layer=found_layer,
                            type=ref_type,
                            id=ref_id,
                        )
                    )
                else:
                    events.append(
                        _event_line(
                            "INFO",
                            "lsi",
                            "I_REF_VISIBLE",
                            id_ptr,
                            "Reference target resolved.",
                            layer=indexed_layer,
                            type=ref_type,
                            id=ref_id,
                        )
                    )

        # Deterministic issue ordering (stage fixed, then pointer, then code, then details)
        issues.sort(key=lambda i: (i.location, i.code, json.dumps(i.details, sort_keys=True, separators=(",", ":"))))

        if issues:
            for issue in issues:
                events.append(
                    _event_line("FAIL", issue.stage, issue.code, issue.location, issue.message, **issue.details)
                )
            return "FAIL", issues, events

        return "PASS", [], events

    def _collect_created_identities(self, scope_root: Path) -> set[str]:
        identities: set[str] = set()
        triplets_dir = _triplets_dir(scope_root)
        if not store.exists(triplets_dir):
            return identities

        for triplet_file in sorted(store.paths(triplets_dir, "*.json"), key=lambda p: p.as_posix()):
            if triplet_file.name.endswith(".tombstone.json"):
                continue
            try:
                triplet_record = store.read_json(triplet_file)
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {triplet_file}") from exc
            if not isinstance(triplet_record, dict):
                raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {triplet_file}")
            body_digest = triplet_record.get("body_digest")
            if not isinstance(body_digest, str) or not body_digest:
                raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {triplet_file}")
            body_obj = self._get_object_json(scope_root, body_digest)
            if not isinstance(body_obj, dict):
                raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {triplet_file}")
            dto_type = body_obj.get("dto_type")
            obj_id = body_obj.get("id")
            if isinstance(dto_type, str) and dto_type and isinstance(obj_id, str) and obj_id:
                identities.add(f"{dto_type}:{obj_id}")
        return identities

    # ----------------------------
    # Internal storage mechanics
    # ----------------------------

    def _put_object(self, scope_root: Path, digest_hex: str, canonical_bytes: bytes) -> None:
        path = _objects_path(scope_root, digest_hex)
        if store.exists(path):
            return
        store.write_bytes(path, canonical_bytes)

    def _get_object_json(self, scope_root: Path, digest_hex: str) -> Any:
        path = _objects_path(scope_root, digest_hex)
        if not store.exists(path):
            return None
        return store.read_json(path)

    def _update_refs_by_id_grouped(self, scope_root: Path, grouped: dict[tuple[str, str], list[RefSource]]) -> None:
        for (ref_type, ref_id), sources_for_ref in grouped.items():
            path = _refs_by_id_path(scope_root, ref_type, ref_id)
            existing = {"type": ref_type, "id": ref_id, "sources": []}
            if store.exists(path):
                data = store.read_json(path)
                if not isinstance(data, dict):
                    raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
                existing = data

            existing_sources = existing.get("sources")
            if not isinstance(existing_sources, list) or any(not isinstance(source, dict) for source in existing_sources):
                raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")

            # Stem-scoped pruning within scope
            stems_to_replace = {s.stem for s in sources_for_ref}
            pruned = [s for s in existing_sources if isinstance(s, dict) and s.get("stem") not in stems_to_replace]

            # Inject new
            injected = pruned + [
                {
                    "stem": s.stem,
                    "location": s.location,
                    "relationship": s.relationship,
                    "artifact_digest": s.artifact_digest,
                }
                for s in sources_for_ref
            ]

            # Deterministic sort: (stem, location, relationship, artifact_digest)
            def sort_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
                stem = str(item.get("stem") or "")
                loc = str(item.get("location") or "")
                rel = str(item.get("relationship") or "")
                dig = str(item.get("artifact_digest") or "")
                return (stem, loc, rel, dig)

            injected_sorted = sorted(injected, key=sort_key)

            record = {
                "lsi_version": LSI_VERSION,
                "type": ref_type,
                "id": ref_id,
                "sources": injected_sorted,
            }
            _atomic_write_json(path, record)

    def _lookup_ref_visibility(self, run_id: str, turn_id: str, stem: str, ref_type: str, ref_id: str) -> str | None:
        """
        Visibility layers (strict):
          1) Self: staging refs/by_id contains a source whose stem == current stem
          2) Staging: staging refs/by_id exists
          3) Committed: committed refs/by_id exists
        """
        # Self + staging
        staging_sources = self.read_refs_sources(
            scope=DIR_STAGING, ref_type=ref_type, ref_id=ref_id, run_id=run_id, turn_id=turn_id
        )
        if any(s.get("stem") == stem for s in staging_sources):
            return "Self"
        if staging_sources:
            return "Staging"

        committed_sources = self.read_refs_sources(scope=DIR_COMMITTED, ref_type=ref_type, ref_id=ref_id)
        if committed_sources:
            return "Committed"

        return None
