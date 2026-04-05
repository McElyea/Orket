from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from orket.reforger.service_contracts import (
    AcceptanceThresholds,
    PromptReforgerServiceRequest,
    RuntimeContext,
    SERVICE_MODE_ADAPT,
    SERVICE_MODE_BASELINE,
)

PHASE0_BRIDGE_CONTRACT_REF = "localclaw://bridge/textmystery-v0"
PHASE0_EVAL_SLICE_REF = "localclaw://eval/truth-only-v0"
PHASE0_BASELINE_REQUEST_ID = "phase0-baseline-textmystery-v0"
PHASE0_ADAPT_REQUEST_ID = "phase0-adapt-textmystery-v0"
PHASE0_BASELINE_RUN_ID = "phase0-baseline-run-0001"
PHASE0_ADAPT_RUN_ID = "phase0-adapt-run-0007"


@dataclass(frozen=True)
class Phase0ProofSliceBinding:
    bridge_contract_ref: str
    eval_slice_ref: str
    route_id: str
    mode: str
    candidate_seed: int
    live_proof_blocker_step: str
    live_proof_blocker_error: str
    bridge_contract_payload: dict[str, Any]
    scenario_pack_payload: dict[str, Any]
    content_inputs: dict[str, Any]

    def materialize(self, root: Path) -> dict[str, Path]:
        input_dir = root / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        prompts_dir = input_dir / "content" / "prompts"
        voices_dir = input_dir / "content" / "voices"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        voices_dir.mkdir(parents=True, exist_ok=True)

        archetypes = self.content_inputs["archetypes"]
        npcs = self.content_inputs["npcs"]
        refusal_styles = self.content_inputs["refusal_styles"]
        voices = self.content_inputs["voices"]

        (prompts_dir / "archetypes.yaml").write_text(yaml.safe_dump(archetypes, sort_keys=True), encoding="utf-8")
        (prompts_dir / "npcs.yaml").write_text(yaml.safe_dump(npcs, sort_keys=True), encoding="utf-8")
        (input_dir / "content" / "refusal_styles.yaml").write_text(
            yaml.safe_dump(refusal_styles, sort_keys=True),
            encoding="utf-8",
        )
        (voices_dir / "profiles.yaml").write_text(yaml.safe_dump(voices, sort_keys=True), encoding="utf-8")

        scenario_path = root / "scenario_pack.json"
        scenario_path.write_text(json.dumps(self.scenario_pack_payload, indent=2) + "\n", encoding="utf-8")

        bridge_contract_path = root / "bridge_contract.json"
        bridge_contract_path.write_text(
            json.dumps(self.bridge_contract_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "input_dir": input_dir,
            "scenario_pack_path": scenario_path,
            "bridge_contract_path": bridge_contract_path,
        }


def phase0_acceptance_thresholds() -> AcceptanceThresholds:
    return AcceptanceThresholds(certified_min_score=1.0, certified_with_limits_min_score=0.85)


def phase0_runtime_context() -> RuntimeContext:
    return RuntimeContext(provider="local", model_id="fake", adapter="stub")


def phase0_baseline_request() -> PromptReforgerServiceRequest:
    return PromptReforgerServiceRequest(
        request_id=PHASE0_BASELINE_REQUEST_ID,
        service_mode=SERVICE_MODE_BASELINE,
        consumer_id="localclaw",
        bridge_contract_ref=PHASE0_BRIDGE_CONTRACT_REF,
        eval_slice_ref=PHASE0_EVAL_SLICE_REF,
        runtime_context=phase0_runtime_context(),
        baseline_bundle_ref="workspace://reforge/packs/model/fake/truth_only/best",
        acceptance_thresholds=phase0_acceptance_thresholds(),
    )


def phase0_adapt_request() -> PromptReforgerServiceRequest:
    return PromptReforgerServiceRequest(
        request_id=PHASE0_ADAPT_REQUEST_ID,
        service_mode=SERVICE_MODE_ADAPT,
        consumer_id="localclaw",
        bridge_contract_ref=PHASE0_BRIDGE_CONTRACT_REF,
        eval_slice_ref=PHASE0_EVAL_SLICE_REF,
        runtime_context=phase0_runtime_context(),
        baseline_bundle_ref="workspace://reforge/packs/model/fake/truth_only/best",
        acceptance_thresholds=phase0_acceptance_thresholds(),
        candidate_budget=4,
    )


def phase0_service_run_id(request_id: str) -> str | None:
    if request_id == PHASE0_BASELINE_REQUEST_ID:
        return PHASE0_BASELINE_RUN_ID
    if request_id == PHASE0_ADAPT_REQUEST_ID:
        return PHASE0_ADAPT_RUN_ID
    return None


def resolve_phase0_proof_slice(
    *,
    bridge_contract_ref: str,
    eval_slice_ref: str,
) -> Phase0ProofSliceBinding | None:
    if bridge_contract_ref != PHASE0_BRIDGE_CONTRACT_REF or eval_slice_ref != PHASE0_EVAL_SLICE_REF:
        return None
    return Phase0ProofSliceBinding(
        bridge_contract_ref=PHASE0_BRIDGE_CONTRACT_REF,
        eval_slice_ref=PHASE0_EVAL_SLICE_REF,
        route_id="textmystery_persona_v0",
        mode="truth_only",
        candidate_seed=1,
        live_proof_blocker_step="local_model_runtime_resolution",
        live_proof_blocker_error=(
            "No real local-model runtime is configured for the Phase 0 Prompt Reforger proof slice; "
            "the bounded generic service slice was proven structurally with the deterministic fake runtime."
        ),
        bridge_contract_payload={
            "bridge_contract_ref": PHASE0_BRIDGE_CONTRACT_REF,
            "version": "textmystery-bridge-v0",
            "tool_identity": "textmystery.persona",
            "tool_instructions": [
                "Honor the bridged persona fields exactly.",
                "Refuse when the bridged refusal guidance says to refuse.",
                "Do not invent bridge fields outside the canonical surface.",
            ],
            "examples": [
                {
                    "input": "Need a terse refusal from Nick.",
                    "expected_behavior": "Use the Nick persona and refusal template without exclamation points.",
                }
            ],
            "repair_retry_guidance": [
                "When validator feedback indicates a refusal-template defect, repair the prompt-facing refusal wording only.",
                "When validator feedback indicates punctuation drift, tighten the style rules without widening the bridge surface.",
            ],
        },
        scenario_pack_payload={
            "pack_id": "phase0_textmystery_truth_only_v0",
            "version": "1.0.0",
            "mode": "truth_only",
            "tests": [
                {"id": "TRUTH_001", "kind": "npc_archetype_exists", "hard": True, "weight": 1.0},
                {"id": "TRUTH_002", "kind": "npc_refusal_style_exists", "hard": True, "weight": 1.0},
                {"id": "TRUTH_003", "kind": "no_exclamation_rules", "hard": False, "weight": 0.9},
                {"id": "TRUTH_004", "kind": "refusal_templates_use_reason_code", "hard": False, "weight": 0.1},
            ],
        },
        content_inputs={
            "archetypes": {
                "version": 1,
                "defaults": {
                    "max_words": 14,
                    "end_punctuation": ".",
                    "allow_ellipsis": False,
                    "allow_exclamation": True,
                    "allow_questions": True,
                    "allow_contractions": True,
                },
                "archetypes": {
                    "TERSE": {
                        "description": "Short clipped voice",
                        "rules": {"max_words": 10, "allow_exclamation": False},
                        "banks": {"refuse": [""]},
                    }
                },
            },
            "npcs": {
                "version": 1,
                "npcs": {
                    "NICK": {
                        "archetype": "TERSE",
                        "display_name": "Nick",
                        "refusal_style_id": "REF_STYLE_STEEL",
                        "voice_profile_id": "NICK_VOICE",
                    }
                },
            },
            "refusal_styles": [{"id": "REF_STYLE_STEEL", "templates": ["No comment."]}],
            "voices": {
                "version": 1,
                "profiles": {
                    "NICK_VOICE": {
                        "voice_id": "male_low_clipped",
                        "base_speed": 1.1,
                        "emotion_map": {"neutral": {}},
                    }
                },
            },
        },
    )
