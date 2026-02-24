Orket OS — Sovereign Capability & Replay Spec (v1.2.1)
This is the single, sealed spec: requirements + final JSON contracts + final Python comparator.

A. Sovereign requirements (laws)
Deny Precedence Law  
If multiple deny conditions apply, deny_code MUST follow:
E_SIDE_EFFECT_UNDECLARED → else E_CAPABILITY_DENIED → else E_PERMISSION_DENIED.

Single‑Emission Decision Record Law  
Every Tool Attempt MUST produce exactly one CapabilityDecisionRecord (allowed/denied/skipped/unresolved).

Strict Canonical Parity Law  
Replay equivalence is defined by canonical UTF‑8 bytes (or digests thereof) of canonical surfaces; object equality is insufficient.

Float Ban Law  
Any float/NaN/Infinity/‑0 on a canonical surface MUST emit E_CANONICALIZATION_ERROR.
Fractional values MUST be strings or fixed‑point integers.

Safe Boundary Law  
Diagnostic fields MUST be ignored for parity:

TurnResult.events

KernelIssue.message

ReplayReport.mismatches[*].diagnostic

Issue Detail Parity Law  
In v1.2.1, every key in KernelIssue.details is parity‑relevant; no diagnostic escape hatches inside details.

Registry Lock Law  
If local error-codes-v1.json digest ≠ bundle registry_digest, replay MUST fail closed with E_REGISTRY_DIGEST_MISMATCH.

Deterministic Path Selection Law

turn_results[*].paths MUST be sorted by Unicode codepoint lexicographic order.

Comparator MUST attempt to load TurnResult paths in that order; first readable wins.

If none readable → status=ERROR + E_REPLAY_INPUT_MISSING.

Report Ordering Law  
ReplayReport.mismatches[] MUST be sorted by:

turn_id

stage_name (using stage-order-v1.json)

ordinal

surface

path

Surface List Law  
Parity inputs:

registry_digest, digests.*, turn_result_digest

transition.*_digest

canonical CapabilityDecisionRecord bytes

canonical KernelIssue bytes (excluding message)

Ignored surfaces:

TurnResult.events

KernelIssue.message

ReplayReport.mismatches[*].diagnostic

Correspondence Law  
For any CapabilityDecisionRecord with outcome ∈ {denied, unresolved} there MUST exist a KernelIssue with:

same (run_id, turn_id)

issue.stage == "capability"

issue.code == decision.deny_code

issue.location == "/capabilities/decisions/<ordinal>"

B. JSON contracts (final)
1. contracts/stage-order-v1.json
json
{
  "contract_version": "kernel_api/v1",
  "description": "Authoritative stage sequence for issue sorting and replay joining.",
  "stage_order": [
    "base_shape",
    "dto_links",
    "relationship_vocabulary",
    "policy",
    "determinism",
    "ci",
    "lsi",
    "promotion",
    "capability",
    "replay"
  ]
}
2. contracts/error-codes-v1.json
json
{
  "contract_version": "kernel_api/v1",
  "codes": {
    "E_SIDE_EFFECT_UNDECLARED": { "stage": "capability" },
    "E_CAPABILITY_DENIED": { "stage": "capability" },
    "E_PERMISSION_DENIED": { "stage": "capability" },

    "E_CAPABILITY_NOT_RESOLVED": { "stage": "capability" },
    "I_CAPABILITY_SKIPPED": { "stage": "capability" },

    "E_CANONICALIZATION_ERROR": { "stage": "determinism" },

    "E_REPLAY_INPUT_MISSING": { "stage": "replay" },
    "E_REPLAY_VERSION_MISMATCH": { "stage": "replay" },
    "E_REPLAY_EQUIVALENCE_FAILED": { "stage": "replay" },
    "E_REGISTRY_DIGEST_MISMATCH": { "stage": "replay" }
  }
}
3. contracts/capability-decision-record.schema.json (with tightened invariants)
json
{
  "$id": "https://orket.dev/os/contracts/capability-decision-record.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CapabilityDecisionRecord",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "contract_version",
    "decision_id",
    "run_id",
    "turn_id",
    "tool_name",
    "action",
    "ordinal",
    "stage",
    "outcome",
    "deny_code",
    "info_code",
    "reason",
    "provenance"
  ],
  "properties": {
    "contract_version": { "const": "kernel_api/v1" },

    "decision_id": {
      "$ref": "turn-result.schema.json#/$defs/StructuralDigest"
    },

    "run_id": { "type": "string" },
    "turn_id": { "type": "string" },

    "tool_name": { "type": "string" },
    "action": { "type": "string" },

    "ordinal": { "type": "integer", "minimum": 0 },
    "stage": { "const": "capability" },

    "outcome": { "enum": ["allowed", "denied", "skipped", "unresolved"] },

    "deny_code": { "type": ["string", "null"], "pattern": "^E_[A-Z0-9_]+$" },
    "info_code": { "type": ["string", "null"], "pattern": "^I_[A-Z0-9_]+$" },
    "reason": {
      "type": ["string", "null"],
      "enum": [null, "policy_disabled", "module_missing", "enforcement_off"]
    },

    "provenance": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "required": ["policy_source", "policy_digest", "rule_id"],
      "properties": {
        "policy_source": { "type": "string" },
        "policy_digest": {
          "$ref": "turn-result.schema.json#/$defs/StructuralDigest"
        },
        "rule_id": { "type": "string" }
      }
    }
  },

  "allOf": [
    {
      "if": { "properties": { "outcome": { "const": "allowed" } } },
      "then": {
        "required": ["provenance"],
        "properties": {
          "provenance": { "type": "object" },
          "deny_code": { "const": null },
          "info_code": { "const": null },
          "reason": { "const": null }
        }
      }
    },
    {
      "if": { "properties": { "outcome": { "const": "denied" } } },
      "then": {
        "required": ["deny_code"],
        "properties": {
          "deny_code": { "type": "string", "pattern": "^E_[A-Z0-9_]+$" },
          "info_code": { "const": null },
          "reason": { "const": null },
          "provenance": { "const": null }
        }
      }
    },
    {
      "if": { "properties": { "outcome": { "const": "skipped" } } },
      "then": {
        "required": ["info_code", "reason"],
        "properties": {
          "info_code": { "const": "I_CAPABILITY_SKIPPED" },
          "deny_code": { "const": null },
          "provenance": { "const": null }
        }
      }
    },
    {
      "if": { "properties": { "outcome": { "const": "unresolved" } } },
      "then": {
        "required": ["deny_code"],
        "properties": {
          "deny_code": { "const": "E_CAPABILITY_NOT_RESOLVED" },
          "info_code": { "const": null },
          "reason": { "const": null },
          "provenance": { "const": null }
        }
      }
    }
  ]
}
4. contracts/replay-bundle.schema.json
json
{
  "$id": "https://orket.dev/os/contracts/replay-bundle.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SovereignReplayBundle",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "contract_version",
    "run_envelope",
    "registry_digest",
    "digests",
    "turn_results"
  ],
  "properties": {
    "contract_version": { "const": "replay_bundle/v1" },

    "run_envelope": {
      "type": "object",
      "required": ["run_id", "workflow_id"],
      "properties": {
        "run_id": { "type": "string" },
        "workflow_id": { "type": "string" }
      },
      "additionalProperties": false
    },

    "registry_digest": {
      "$ref": "turn-result.schema.json#/$defs/StructuralDigest"
    },

    "digests": {
      "type": "object",
      "required": [
        "policy_digest",
        "runtime_profile_digest",
        "contract_registry_snapshot_digest"
      ],
      "properties": {
        "policy_digest": {
          "$ref": "turn-result.schema.json#/$defs/StructuralDigest"
        },
        "runtime_profile_digest": {
          "$ref": "turn-result.schema.json#/$defs/StructuralDigest"
        },
        "contract_registry_snapshot_digest": {
          "$ref": "turn-result.schema.json#/$defs/StructuralDigest"
        }
      },
      "additionalProperties": false
    },

    "turn_results": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["turn_id", "turn_result_digest", "paths"],
        "additionalProperties": false,
        "properties": {
          "turn_id": { "type": "string" },
          "turn_result_digest": {
            "$ref": "turn-result.schema.json#/$defs/StructuralDigest"
          },
          "paths": {
            "type": "array",
            "minItems": 1,
            "description": "Sorted by Unicode codepoint; comparator loads first readable.",
            "items": { "type": "string" }
          }
        }
      }
    }
  }
}
5. contracts/replay-report.schema.json (with nullable digests for schema/ERROR mismatches)
json
{
  "$id": "https://orket.dev/os/contracts/replay-report.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ReplayReport",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "contract_version",
    "report_id",
    "run_id",
    "status",
    "exit_code",
    "mismatches"
  ],
  "properties": {
    "contract_version": { "const": "kernel_api/v1" },

    "report_id": {
      "$ref": "turn-result.schema.json#/$defs/StructuralDigest"
    },

    "run_id": { "type": "string" },

    "status": { "enum": ["EQUIVALENT", "DIVERGENT", "ERROR"] },

    "exit_code": { "type": "integer" },

    "mismatches": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "turn_id",
          "stage_name",
          "ordinal",
          "surface",
          "path",
          "expected_digest",
          "actual_digest"
        ],
        "properties": {
          "turn_id": { "type": "string" },

          "stage_name": {
            "type": "string",
            "enum": [
              "base_shape",
              "dto_links",
              "relationship_vocabulary",
              "policy",
              "determinism",
              "ci",
              "lsi",
              "promotion",
              "capability",
              "replay"
            ]
          },

          "ordinal": { "type": "integer", "minimum": 0 },

          "surface": {
            "enum": [
              "decision_record",
              "issue",
              "transition",
              "bundle_digest",
              "schema",
              "unknown"
            ]
          },

          "path": { "type": "string" },

          "expected_digest": {
            "anyOf": [
              { "$ref": "turn-result.schema.json#/$defs/StructuralDigest" },
              { "type": "null" }
            ]
          },

          "actual_digest": {
            "anyOf": [
              { "$ref": "turn-result.schema.json#/$defs/StructuralDigest" },
              { "type": "null" }
            ]
          },

          "reason_code": {
            "type": ["string", "null"],
            "pattern": "^E_[A-Z0-9_]+$"
          },

          "diagnostic": {
            "type": ["object", "null"],
            "description": "Ignored for canonical report_id calculation; MUST be null when hashing report_id."
          }
        }
      }
    }
  }
}
6. contracts/turn-result.schema.json (patch)
Only wiring change (rest of file as you already have it):

json
"decisions": {
  "type": "array",
  "items": {
    "$ref": "https://orket.dev/os/contracts/capability-decision-record.schema.json"
  }
}
C. Python comparator contract (final)
Single module implementing canonicalization, IssueKey, comparator, and ReplayReport construction.

python
import copy
import json
import hashlib
from collections import defaultdict
from typing import Any, Dict, List, Tuple


# ---------- Canonicalization ----------

def contains_forbidden_numbers(x: Any) -> bool:
    if isinstance(x, float):
        # float / NaN / +/-inf / -0 all forbidden on canonical surfaces
        return True
    if isinstance(x, dict):
        return any(contains_forbidden_numbers(v) for v in x.values())
    if isinstance(x, list):
        return any(contains_forbidden_numbers(v) for v in x)
    return False


def canonical_serialize(obj: Any) -> bytes:
    if contains_forbidden_numbers(obj):
        raise ValueError("E_CANONICALIZATION_ERROR")
    # sort_keys=True → Unicode codepoint order; separators remove whitespace
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------- Stage order spine ----------

def load_stage_order(path: str) -> Dict[str, int]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    order = data["stage_order"]
    return {name: idx for idx, name in enumerate(order)}


# ---------- IssueKey + comparison ----------

missing_sentinel = {"_missing": True}


def get_issue_key(issue: Dict[str, Any], stage_lookup: Dict[str, int]) -> Tuple[Any, ...]:
    return (
        stage_lookup.get(issue["stage"], 99),
        issue["location"],
        issue["code"],
        sha256_hex(canonical_serialize(issue["details"]))
    )


def normalize_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    # Safe Boundary: drop message, keep parity-relevant fields (stage, location, code, details, etc.)
    return {k: v for k, v in issue.items() if k != "message"}


def compare_issues(
    turn_id: str,
    issues_a: List[Dict[str, Any]],
    issues_b: List[Dict[str, Any]],
    stage_lookup: Dict[str, int]
) -> List[Dict[str, Any]]:
    mismatches: List[Dict[str, Any]] = []

    keyed_a: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    keyed_b: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)

    for i in issues_a:
        keyed_a[get_issue_key(i, stage_lookup)].append(i)
    for i in issues_b:
        keyed_b[get_issue_key(i, stage_lookup)].append(i)

    all_keys = sorted(set(keyed_a) | set(keyed_b))

    for key in all_keys:
        la = keyed_a.get(key, [])
        lb = keyed_b.get(key, [])

        la_norm = sorted(
            (normalize_issue(x) for x in la),
            key=lambda x: sha256_hex(canonical_serialize(x))
        )
        lb_norm = sorted(
            (normalize_issue(x) for x in lb),
            key=lambda x: sha256_hex(canonical_serialize(x))
        )

        expected_obj = la_norm if la_norm else [missing_sentinel]
        actual_obj = lb_norm if lb_norm else [missing_sentinel]

        # Count mismatch
        if len(la_norm) != len(lb_norm):
            mismatches.append({
                "turn_id": turn_id,
                "stage_name": "replay",  # join/multiplicity mismatch
                "ordinal": 0,
                "surface": "issue",
                "path": key[1],  # location
                "expected_digest": sha256_hex(canonical_serialize(expected_obj)),
                "actual_digest": sha256_hex(canonical_serialize(actual_obj)),
                "reason_code": "E_REPLAY_EQUIVALENCE_FAILED",
                "diagnostic": None
            })
            continue

        # Structural mismatch
        for a_norm, b_norm in zip(la_norm, lb_norm):
            da = sha256_hex(canonical_serialize(a_norm))
            db = sha256_hex(canonical_serialize(b_norm))
            if da != db:
                mismatches.append({
                    "turn_id": turn_id,
                    "stage_name": a_norm.get("stage", "replay"),
                    "ordinal": 0,
                    "surface": "issue",
                    "path": key[1],
                    "expected_digest": da,
                    "actual_digest": db,
                    "reason_code": "E_REPLAY_EQUIVALENCE_FAILED",
                    "diagnostic": None
                })

    return mismatches


# ---------- ReplayReport construction ----------

def compute_report_id(report: Dict[str, Any]) -> str:
    tmp = copy.deepcopy(report)
    tmp["report_id"] = None
    for m in tmp.get("mismatches", []):
        m["diagnostic"] = None
    return sha256_hex(canonical_serialize(tmp))


def build_replay_report(
    run_id: str,
    mismatches: List[Dict[str, Any]],
    status: str,
    exit_code: int,
    stage_lookup: Dict[str, int]
) -> Dict[str, Any]:
    mismatches_sorted = sorted(
        mismatches,
        key=lambda m: (
            m["turn_id"],
            stage_lookup.get(m["stage_name"], 99),
            m["ordinal"],
            m["surface"],
            m["path"]
        )
    )

    report: Dict[str, Any] = {
        "contract_version": "kernel_api/v1",
        "report_id": None,
        "run_id": run_id,
        "status": status,
        "exit_code": exit_code,
        "mismatches": mismatches_sorted
    }

    report["report_id"] = compute_report_id(report)
    return report


# ---------- Turn loading (Deterministic Path Selection Law) ----------

def load_turn(turn_entry: Dict[str, Any]) -> Dict[str, Any]:
    # paths are required to be sorted by Unicode codepoint; we still enforce sort for fail-safe determinism
    for path in sorted(turn_entry["paths"]):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            continue
    raise ValueError("E_REPLAY_INPUT_MISSING")


# ---------- Top-level compare ----------

def compare(
    bundle_a: Dict[str, Any],
    bundle_b: Dict[str, Any],
    stage_lookup: Dict[str, int]
) -> Dict[str, Any]:
    # 1. Validate required fields
    for k in ("contract_version", "run_envelope", "registry_digest", "digests", "turn_results"):
        if k not in bundle_a or k not in bundle_b:
            # schema-level input missing
            mismatches = [{
                "turn_id": "",
                "stage_name": "replay",
                "ordinal": 0,
                "surface": "schema",
                "path": f"/{k}",
                "expected_digest": None,
                "actual_digest": None,
                "reason_code": "E_REPLAY_INPUT_MISSING",
                "diagnostic": None
            }]
            return build_replay_report(
                run_id=bundle_a.get("run_envelope", {}).get("run_id", ""),
                mismatches=mismatches,
                status="ERROR",
                exit_code=1,
                stage_lookup=stage_lookup
            )

    run_id = bundle_a["run_envelope"]["run_id"]

    # 2. Registry lock
    if bundle_a["registry_digest"] != bundle_b["registry_digest"]:
        mismatches = [{
            "turn_id": "",
            "stage_name": "replay",
            "ordinal": 0,
            "surface": "bundle_digest",
            "path": "/registry_digest",
            "expected_digest": bundle_a["registry_digest"],
            "actual_digest": bundle_b["registry_digest"],
            "reason_code": "E_REGISTRY_DIGEST_MISMATCH",
            "diagnostic": None
        }]
        return build_replay_report(run_id, mismatches, "DIVERGENT", 1, stage_lookup)

    mismatches: List[Dict[str, Any]] = []

    # 3. Bundle digests (policy/runtime/registry snapshot)
    for dk in ("policy_digest", "runtime_profile_digest", "contract_registry_snapshot_digest"):
        if bundle_a["digests"][dk] != bundle_b["digests"][dk]:
            mismatches.append({
                "turn_id": "",
                "stage_name": "replay",
                "ordinal": 0,
                "surface": "bundle_digest",
                "path": f"/digests/{dk}",
                "expected_digest": bundle_a["digests"][dk],
                "actual_digest": bundle_b["digests"][dk],
                "reason_code": "E_REPLAY_VERSION_MISMATCH",
                "diagnostic": None
            })

    # 4. Turn join
    turns_a = {t["turn_id"]: t for t in bundle_a["turn_results"]}
    turns_b = {t["turn_id"]: t for t in bundle_b["turn_results"]}

    for turn_id in sorted(set(turns_a) | set(turns_b)):
        ta_entry = turns_a.get(turn_id)
        tb_entry = turns_b.get(turn_id)

        if ta_entry is None or tb_entry is None:
            mismatches.append({
                "turn_id": turn_id,
                "stage_name": "replay",
                "ordinal": 0,
                "surface": "schema",
                "path": "/turn_results",
                "expected_digest": None,
                "actual_digest": None,
                "reason_code": "E_REPLAY_EQUIVALENCE_FAILED",
                "diagnostic": None
            })
            continue

        # 4a. turn_result_digest parity (Surface List Law)
        if ta_entry["turn_result_digest"] != tb_entry["turn_result_digest"]:
            mismatches.append({
                "turn_id": turn_id,
                "stage_name": "replay",
                "ordinal": 0,
                "surface": "bundle_digest",
                "path": f"/turn_results/{turn_id}/turn_result_digest",
                "expected_digest": ta_entry["turn_result_digest"],
                "actual_digest": tb_entry["turn_result_digest"],
                "reason_code": "E_REPLAY_EQUIVALENCE_FAILED",
                "diagnostic": None
            })

        # 4b. Load TurnResult via Deterministic Path Selection Law
        try:
            ta = load_turn(ta_entry)
            tb = load_turn(tb_entry)
        except ValueError:
            mismatches.append({
                "turn_id": turn_id,
                "stage_name": "replay",
                "ordinal": 0,
                "surface": "schema",
                "path": f"/turn_results/{turn_id}/paths",
                "expected_digest": None,
                "actual_digest": None,
                "reason_code": "E_REPLAY_INPUT_MISSING",
                "diagnostic": None
            })
            continue

        # 5. Transition digests (prior/proposed/inputs)
        for field in ("prior_state_digest", "proposed_state_digest", "inputs_digest"):
            if ta["transition"][field] != tb["transition"][field]:
                mismatches.append({
                    "turn_id": turn_id,
                    "stage_name": "replay",  # transition evidence checked at replay gate
                    "ordinal": 0,
                    "surface": "transition",
                    "path": f"/transition/{field}",
                    "expected_digest": ta["transition"][field],
                    "actual_digest": tb["transition"][field],
                    "reason_code": "E_REPLAY_EQUIVALENCE_FAILED",
                    "diagnostic": None
                })

        # 6. CapabilityDecisionRecord comparison
        da = sorted(ta["capabilities"]["decisions"], key=lambda d: d["ordinal"])
        db = sorted(tb["capabilities"]["decisions"], key=lambda d: d["ordinal"])

        if len(da) != len(db):
            mismatches.append({
                "turn_id": turn_id,
                "stage_name": "capability",
                "ordinal": 0,
                "surface": "decision_record",
                "path": "/capabilities/decisions",
                "expected_digest": None,
                "actual_digest": None,
                "reason_code": "E_REPLAY_EQUIVALENCE_FAILED",
                "diagnostic": None
            })
        else:
            for i, (xa, xb) in enumerate(zip(da, db)):
                ba = canonical_serialize(xa)
                bb = canonical_serialize(xb)
                if ba != bb:
                    mismatches.append({
                        "turn_id": turn_id,
                        "stage_name": "capability",
                        "ordinal": xa["ordinal"],
                        "surface": "decision_record",
                        "path": f"/capabilities/decisions/{i}",
                        "expected_digest": sha256_hex(ba),
                        "actual_digest": sha256_hex(bb),
                        "reason_code": "E_REPLAY_EQUIVALENCE_FAILED",
                        "diagnostic": None
                    })

        # 7. Issues (Safe Boundary + IssueKey multimap)
        ia = ta.get("issues", [])
        ib = tb.get("issues", [])
        mismatches.extend(compare_issues(turn_id, ia, ib, stage_lookup))

    # 8. Final report
    if mismatches:
        return build_replay_report(run_id, mismatches, "DIVERGENT", 1, stage_lookup)
    return build_replay_report(run_id, [], "EQUIVALENT", 0, stage_lookup)