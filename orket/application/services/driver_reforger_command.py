"""Operator compiler command parsing and presentation."""
from orket.application.services.reforger_service import ReforgerService


class DriverReforgerCommand:
    def __init__(self, reforger: ReforgerService):
        self.reforger_tools = reforger

    async def execute(self, args: list[str]) -> str:
        if not args:
            return "Usage: /reforge <inspect|run> [options]"
        sub = str(args[0]).strip().lower()
        flags = self._parse_reforge_flags(args[1:])
        if sub == "inspect":
            input_dir = str(flags.get("in") or flags.get("input") or ".").strip() or "."
            payload = {
                "route_id": flags.get("route"),
                "input_dir": input_dir,
                "mode": flags.get("mode"),
                "scenario_pack": flags.get("scenario-pack") or flags.get("scenario_pack"),
            }
            result = await self.reforger_tools.inspect(payload)
            if not result.get("ok"):
                return (
                    "Reforger inspect failed.\n"
                    + f"route_id={result.get('route_id')}\n"
                    + f"errors={result.get('errors')}\n"
                    + f"artifact_root={result.get('artifact_root')}"
                )
            return (
                "Reforger inspect ok.\n"
                + f"route_id={result.get('route_id')}\n"
                + f"runnable={result.get('runnable')}\n"
                + f"suite_ready={result.get('suite_ready')}\n"
                + f"missing_inputs={result.get('missing_inputs')}\n"
                + f"suite_requirements={result.get('suite_requirements')}\n"
                + f"artifact_root={result.get('artifact_root')}"
            )
        if sub == "run":
            return await self._run(flags)
        return "Usage: /reforge <inspect|run> [options]"

    async def _run(self, flags: dict[str, str]) -> str:
        route_id = str(flags.get("route") or "").strip()
        input_dir = str(flags.get("in") or flags.get("input") or "").strip()
        output_dir = str(flags.get("out") or flags.get("output") or "").strip()
        if not route_id or not input_dir or not output_dir:
            return (
                "Usage: /reforge run --route <id> --in <dir> --out <dir> "
                "[--mode truth_only] [--scenario-pack <id|path>] [--seed N] [--max-iters K]"
            )
        inspect_payload = {
            "route_id": route_id,
            "input_dir": input_dir,
            "mode": flags.get("mode"),
            "scenario_pack": flags.get("scenario-pack") or flags.get("scenario_pack"),
        }
        inspect_result = await self.reforger_tools.inspect(inspect_payload)
        suite_ready = bool(inspect_result.get("suite_ready"))
        force = self._flag_enabled(flags, "force")
        if not suite_ready and not force:
            return (
                "Reforger run blocked: suite_ready=false.\n"
                + f"missing_inputs={inspect_result.get('missing_inputs')}\n"
                + f"errors={inspect_result.get('errors')}\n"
                + f"suite_requirements={inspect_result.get('suite_requirements')}\n"
                + "Re-run with --force to compile anyway."
            )
        seed_raw = flags.get("seed")
        max_iters_raw = flags.get("max-iters") or flags.get("max_iters")
        run_payload = {
            "route_id": route_id,
            "input_dir": input_dir,
            "output_dir": output_dir,
            "mode": flags.get("mode"),
            "scenario_pack": flags.get("scenario-pack") or flags.get("scenario_pack"),
            "seed": int(seed_raw) if seed_raw and str(seed_raw).isdigit() else 0,
            "max_iters": int(max_iters_raw) if max_iters_raw and str(max_iters_raw).isdigit() else 8,
            "forced": force,
            "force_reason": "suite_ready_false" if force and not suite_ready else "",
        }
        result = await self.reforger_tools.run(run_payload)
        if not result.get("ok"):
            return (
                "Reforger run failed.\n"
                + f"route_id={result.get('route_id')}\n"
                + f"errors={result.get('errors')}\n"
                + f"artifact_root={result.get('artifact_root')}"
            )
        return (
            f"Reforger run ok={result.get('ok')}\n"
            + f"forced={result.get('forced')}\n"
            + f"force_reason={result.get('force_reason')}\n"
            + f"materialized_output_dir={result.get('materialized_output_dir')}\n"
            + f"artifact_root={result.get('artifact_root')}"
        )

    def _parse_reforge_flags(self, tokens: list[str]) -> dict[str, str]:
        flags: dict[str, str] = {}
        i = 0
        while i < len(tokens):
            token = str(tokens[i]).strip()
            if token.startswith("--"):
                key = token[2:]
                value: str = "true"
                if i + 1 < len(tokens) and not str(tokens[i + 1]).startswith("--"):
                    value = str(tokens[i + 1])
                    i += 1
                flags[key] = value
                i += 1
                continue
            i += 1
        return flags

    def _flag_enabled(self, flags: dict[str, str], name: str) -> bool:
        value = str(flags.get(name, "")).strip().lower()
        return value in {"1", "true", "yes", "on"}
