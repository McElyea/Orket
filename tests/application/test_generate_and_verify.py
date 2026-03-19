# Layer: unit
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("generate_and_verify_test", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_execute_test_cases_reports_full_pass(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/workloads/generate_and_verify.py"))
    target = tmp_path / "generated.py"
    target.write_text(
        "def slugify_title(title: str) -> str:\n"
        "    return title.strip().lower().replace(' ', '-')\n",
        encoding="utf-8",
    )

    report = module._execute_test_cases(
        module_path=target,
        function_name="slugify_title",
        test_cases=[{"name": "one", "args": ["hello world"], "expected": "hello-world"}],
    )

    assert report["syntax_valid"] is True
    assert report["callable_loaded"] is True
    assert report["all_passed"] is True


def test_execute_test_cases_reports_syntax_error(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/workloads/generate_and_verify.py"))
    target = tmp_path / "broken.py"
    target.write_text("def nope(:\n    pass\n", encoding="utf-8")

    report = module._execute_test_cases(
        module_path=target,
        function_name="slugify_title",
        test_cases=[],
    )

    assert report["syntax_valid"] is False
    assert "syntax_error" in report["error"]
