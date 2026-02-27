from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MAX_ROUNDS = 8
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TIMEOUT = 180


def _sections(
    *,
    requirement: str,
    changelog: list[str],
    assumptions: list[str],
    open_questions: list[str],
) -> dict[str, Any]:
    return {
        "REQUIREMENT": requirement,
        "CHANGELOG": changelog,
        "ASSUMPTIONS": assumptions,
        "OPEN_QUESTIONS": open_questions,
    }


def _round(
    *,
    t: int,
    sections: dict[str, Any],
    parse_ok: bool = True,
    code_leak_hit: bool = False,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "t": t,
        "sections": sections,
        "parse_ok": parse_ok,
        "code_leak_hit": code_leak_hit,
        "notes": notes or [],
    }


def _good_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for idx in range(1, 6):
        run_id = f"good_resolved_{idx:02d}"
        rounds = [
            _round(
                t=1,
                sections=_sections(
                    requirement=(
                        "Must store profile data locally. Must enforce AES-256 at rest. "
                        "Retention must be 30 days."
                    ),
                    changelog=["Add retention and encryption constraints."],
                    assumptions=["Environment supports local encrypted storage."],
                    open_questions=[],
                ),
                notes=["constraint_add", "decision_resolved:retention_days"],
            ),
            _round(
                t=2,
                sections=_sections(
                    requirement=(
                        "Must store profile data locally. Must enforce AES-256 at rest. "
                        "Retention must be 30 days. Must block outbound profile export."
                    ),
                    changelog=["Add explicit outbound block acceptance constraint."],
                    assumptions=["Audit logger available."],
                    open_questions=[],
                ),
                notes=["constraint_add", "issue_closed:AUD-OUTBOUND"],
            ),
            _round(
                t=3,
                sections=_sections(
                    requirement=(
                        "Must store profile data locally. Must enforce AES-256 at rest. "
                        "Retention must be 30 days. Must block outbound profile export."
                    ),
                    changelog=["No semantic change."],
                    assumptions=["Audit logger available."],
                    open_questions=[],
                ),
                notes=["rewrite_same_semantics"],
            ),
        ]
        runs.append(
            {
                "run_id": run_id,
                "category": "good_resolved",
                "scenario_id": f"good_resolved_seeded_{idx:02d}",
                "model_matrix": {"architect": "qwen2.5-coder:7b", "auditor": "llama3.1:8b"},
                "config": {"max_rounds": MAX_ROUNDS, "temperature": DEFAULT_TEMPERATURE, "timeout": DEFAULT_TIMEOUT},
                "seed_decisions": {"retention_days": 30, "encryption_algo": "AES-256"},
                "rounds": rounds,
                "final_stop_reason": "STABLE",
                "final_outcome_candidate": "CONVERGED_RESOLVED",
            }
        )
    return runs


def _stable_unresolved_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for idx in range(1, 6):
        run_id = f"stable_unresolved_{idx:02d}"
        rounds = [
            _round(
                t=1,
                sections=_sections(
                    requirement="Must store profile data locally. Must block outbound export.",
                    changelog=["Baseline constraints captured."],
                    assumptions=["Encryption required but algorithm undecided."],
                    open_questions=["DECISION_REQUIRED: retention_days", "DECISION_REQUIRED: encryption_algo"],
                ),
                notes=["constraint_add", "decision_required_count:2"],
            ),
            _round(
                t=2,
                sections=_sections(
                    requirement="Must store profile data locally. Must block outbound export.",
                    changelog=["Clarify unresolved decisions remain external."],
                    assumptions=["Encryption required but algorithm undecided."],
                    open_questions=["DECISION_REQUIRED: retention_days", "DECISION_REQUIRED: encryption_algo"],
                ),
                notes=["rewrite_same_semantics", "stable_but_unresolved"],
            ),
            _round(
                t=3,
                sections=_sections(
                    requirement="Must store profile data locally. Must block outbound export.",
                    changelog=["No semantic change."],
                    assumptions=["Encryption required but algorithm undecided."],
                    open_questions=["DECISION_REQUIRED: retention_days", "DECISION_REQUIRED: encryption_algo"],
                ),
                notes=["rewrite_same_semantics", "stable_but_unresolved"],
            ),
            _round(
                t=4,
                sections=_sections(
                    requirement="Must store profile data locally. Must block outbound export.",
                    changelog=["No semantic change."],
                    assumptions=["Encryption required but algorithm undecided."],
                    open_questions=["DECISION_REQUIRED: retention_days", "DECISION_REQUIRED: encryption_algo"],
                ),
                notes=["rewrite_same_semantics", "stop_candidate_stable_but_unresolved_decision"],
            ),
        ]
        runs.append(
            {
                "run_id": run_id,
                "category": "stable_unresolved",
                "scenario_id": f"missing_decision_pressure_{idx:02d}",
                "model_matrix": {"architect": "qwen2.5:14b", "auditor": "deepseek-r1:32b"},
                "config": {"max_rounds": MAX_ROUNDS, "temperature": DEFAULT_TEMPERATURE, "timeout": DEFAULT_TIMEOUT},
                "seed_decisions": {"retention_days": None, "encryption_algo": None},
                "rounds": rounds,
                "final_stop_reason": "STABLE_CANDIDATE_BLOCKED",
                "final_outcome_candidate": "CONVERGED_UNRESOLVED",
            }
        )
    return runs


def _bad_runs() -> list[dict[str, Any]]:
    return [
        {
            "run_id": "bad_oscillation_01",
            "category": "bad",
            "scenario_id": "oscillation_loop_a",
            "model_matrix": {"architect": "qwen2.5:14b", "auditor": "deepseek-r1:32b"},
            "config": {"max_rounds": MAX_ROUNDS, "temperature": DEFAULT_TEMPERATURE, "timeout": DEFAULT_TIMEOUT},
            "seed_decisions": {"retention_days": None},
            "rounds": [
                _round(
                    t=1,
                    sections=_sections(
                        requirement="Must retain logs for forensic audits for 180 days.",
                        changelog=["Add long retention requirement."],
                        assumptions=[],
                        open_questions=["DECISION_REQUIRED: retention_days"],
                    ),
                    notes=["constraint_add"],
                ),
                _round(
                    t=2,
                    sections=_sections(
                        requirement="Must delete logs quickly for privacy; maximum retention 7 days.",
                        changelog=["Flip retention to short horizon."],
                        assumptions=[],
                        open_questions=["DECISION_REQUIRED: retention_days"],
                    ),
                    notes=["constraint_conflict"],
                ),
                _round(
                    t=3,
                    sections=_sections(
                        requirement="Must retain logs for forensic audits for 180 days.",
                        changelog=["Revert to long retention."],
                        assumptions=[],
                        open_questions=["DECISION_REQUIRED: retention_days"],
                    ),
                    notes=["constraint_conflict", "loop_signature:period_2"],
                ),
            ],
            "final_stop_reason": "LOOP_DETECTED",
            "final_outcome_candidate": "LOOP_DETECTED",
        },
        {
            "run_id": "bad_oscillation_02",
            "category": "bad",
            "scenario_id": "oscillation_loop_b",
            "model_matrix": {"architect": "qwen2.5-coder:14b", "auditor": "gemma3:27b"},
            "config": {"max_rounds": MAX_ROUNDS, "temperature": DEFAULT_TEMPERATURE, "timeout": DEFAULT_TIMEOUT},
            "seed_decisions": {"encryption_algo": None},
            "rounds": [
                _round(
                    t=1,
                    sections=_sections(
                        requirement="Must keep keys only on device; no remote backup.",
                        changelog=["Add local-key-only policy."],
                        assumptions=[],
                        open_questions=["DECISION_REQUIRED: key_backup_policy"],
                    ),
                    notes=["constraint_add"],
                ),
                _round(
                    t=2,
                    sections=_sections(
                        requirement="Must back up keys remotely for recovery.",
                        changelog=["Replace local-only with remote backup requirement."],
                        assumptions=[],
                        open_questions=["DECISION_REQUIRED: key_backup_policy"],
                    ),
                    notes=["constraint_conflict"],
                ),
                _round(
                    t=3,
                    sections=_sections(
                        requirement="Must keep keys only on device; no remote backup.",
                        changelog=["Revert requirement."],
                        assumptions=[],
                        open_questions=["DECISION_REQUIRED: key_backup_policy"],
                    ),
                    notes=["constraint_conflict", "loop_signature:period_2"],
                ),
            ],
            "final_stop_reason": "LOOP_DETECTED",
            "final_outcome_candidate": "LOOP_DETECTED",
        },
        {
            "run_id": "bad_scope_creep_01",
            "category": "bad",
            "scenario_id": "scope_creep_ratchet",
            "model_matrix": {"architect": "qwen2.5:14b", "auditor": "deepseek-r1:32b"},
            "config": {"max_rounds": MAX_ROUNDS, "temperature": DEFAULT_TEMPERATURE, "timeout": DEFAULT_TIMEOUT},
            "seed_decisions": {"retention_days": 30},
            "rounds": [
                _round(
                    t=1,
                    sections=_sections(
                        requirement="Must store profiles locally and block outbound profile export.",
                        changelog=["Baseline local-first policy."],
                        assumptions=[],
                        open_questions=[],
                    ),
                    notes=["constraint_add"],
                ),
                _round(
                    t=2,
                    sections=_sections(
                        requirement=(
                            "Must store profiles locally, block outbound export, add cloud sync for backups, "
                            "add multi-user sharing controls."
                        ),
                        changelog=["Add cloud sync and multi-user requirements."],
                        assumptions=[],
                        open_questions=[],
                    ),
                    notes=["scope_creep", "new_domain_entities:cloud sync,multi-user"],
                ),
                _round(
                    t=3,
                    sections=_sections(
                        requirement=(
                            "Must store profiles locally, block outbound export, add cloud sync, "
                            "multi-user sharing, telemetry analytics, and notification workflows."
                        ),
                        changelog=["Add telemetry and notifications."],
                        assumptions=[],
                        open_questions=[],
                    ),
                    notes=["scope_creep", "new_domain_entities:telemetry,analytics,notifications"],
                ),
            ],
            "final_stop_reason": "MAX_ROUNDS",
            "final_outcome_candidate": "MAX_ROUNDS",
        },
        {
            "run_id": "bad_paraphrase_thrash_01",
            "category": "bad",
            "scenario_id": "paraphrase_thrash",
            "model_matrix": {"architect": "llama3.1:8b", "auditor": "qwen2.5-coder:7b"},
            "config": {"max_rounds": MAX_ROUNDS, "temperature": DEFAULT_TEMPERATURE, "timeout": DEFAULT_TIMEOUT},
            "seed_decisions": {"retention_days": 30},
            "rounds": [
                _round(
                    t=1,
                    sections=_sections(
                        requirement="Must store profile data locally and never upload it to external services.",
                        changelog=["Baseline."],
                        assumptions=[],
                        open_questions=[],
                    ),
                    notes=["constraint_add"],
                ),
                _round(
                    t=2,
                    sections=_sections(
                        requirement=(
                            "Profile records are required to remain on-device only; outbound transfer is prohibited."
                        ),
                        changelog=["Rewrite for clarity."],
                        assumptions=[],
                        open_questions=[],
                    ),
                    notes=["rewrite_same_semantics", "high_diff_surface_low_semantic_delta"],
                ),
                _round(
                    t=3,
                    sections=_sections(
                        requirement=(
                            "User profile artifacts shall persist solely on local storage, and external transmission "
                            "must not occur."
                        ),
                        changelog=["Rewrite for readability."],
                        assumptions=[],
                        open_questions=[],
                    ),
                    notes=["rewrite_same_semantics", "high_diff_surface_low_semantic_delta"],
                ),
            ],
            "final_stop_reason": "MAX_ROUNDS",
            "final_outcome_candidate": "MAX_ROUNDS",
        },
        {
            "run_id": "bad_format_sabotage_01",
            "category": "bad",
            "scenario_id": "format_sabotage",
            "model_matrix": {"architect": "qwen2.5-coder:14b", "auditor": "deepseek-r1:32b"},
            "config": {"max_rounds": MAX_ROUNDS, "temperature": DEFAULT_TEMPERATURE, "timeout": DEFAULT_TIMEOUT},
            "seed_decisions": {"retention_days": 30},
            "rounds": [
                _round(
                    t=1,
                    sections=_sections(
                        requirement="Must store profile data locally and enforce retention for 30 days.",
                        changelog=["Baseline."],
                        assumptions=[],
                        open_questions=[],
                    ),
                    notes=["constraint_add"],
                ),
                _round(
                    t=2,
                    sections={
                        "REQUIREMENTS": "Must store profile data locally.",
                        "CHANGELOG": ["Introduced malformed header and inline pseudo code: def retain(x): pass"],
                        "ASSUMPTIONS": [],
                        "OPEN_QUESTIONS": [],
                    },
                    parse_ok=False,
                    code_leak_hit=True,
                    notes=["format_violation", "code_leak"],
                ),
            ],
            "final_stop_reason": "FORMAT_VIOLATION",
            "final_outcome_candidate": "FORMAT_VIOLATION",
        },
    ]


def _generate_candidate_runs() -> list[dict[str, Any]]:
    runs = _good_runs() + _stable_unresolved_runs() + _bad_runs()
    return sorted(runs, key=lambda row: str(row["run_id"]))


def _labels_template(runs: list[dict[str, Any]]) -> dict[str, Any]:
    labeled_runs = []
    for run in runs:
        rounds = []
        for round_row in run["rounds"]:
            rounds.append(
                {
                    "t": int(round_row["t"]),
                    "delta_type_round": None,
                    "delta_type_by_section": {
                        "REQUIREMENT": None,
                        "CHANGELOG": None,
                        "ASSUMPTIONS": None,
                        "OPEN_QUESTIONS": None,
                    },
                    "conflict_active_gold": None,
                    "conflict_ids_gold": [],
                    "resolved_decisions_gold": {},
                    "resolved_issues_gold": {},
                    "good_enough_gold": None,
                }
            )
        labeled_runs.append(
            {
                "run_id": run["run_id"],
                "scenario_id": run["scenario_id"],
                "model_matrix": run["model_matrix"],
                "rounds": rounds,
                "first_good_enough_round": None,
                "final_outcome_gold": None,
            }
        )
    return {"schema_version": "odr.gold_labels.v1", "generated_at": datetime.now(UTC).isoformat(), "runs": labeled_runs}


def _bundle(runs: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"good_resolved": 0, "stable_unresolved": 0, "bad": 0}
    for run in runs:
        category = str(run["category"])
        if category in counts:
            counts[category] += 1
    return {
        "schema_version": "odr.calibration.bundle.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "max_rounds": MAX_ROUNDS,
            "temperature": DEFAULT_TEMPERATURE,
            "timeout": DEFAULT_TIMEOUT,
            "notes": "Deterministic candidate set for first-pass human labeling.",
        },
        "distribution": counts,
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ODR calibration candidate run bundle and gold labels scaffold.")
    parser.add_argument("--out-dir", default="benchmarks/results/odr_calibration")
    parser.add_argument("--bundle-out", default="candidate_runs_v1.json")
    parser.add_argument("--labels-out", default="gold_labels_v1.json")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = _generate_candidate_runs()
    bundle = _bundle(runs)
    labels = _labels_template(runs)

    bundle_path = out_dir / args.bundle_out
    labels_path = out_dir / args.labels_out
    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    labels_path.write_text(json.dumps(labels, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {bundle_path} (runs={len(runs)})")
    print(f"Wrote {labels_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
