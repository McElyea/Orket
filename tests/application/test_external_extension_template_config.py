from __future__ import annotations

import sys
from pathlib import Path


def test_external_extension_template_defaults_validate() -> None:
    """Layer: contract. Verifies external extension template defaults parse under the companion config schema."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"

    sys.path.insert(0, str(src_root))
    try:
        from companion_extension.config_loader import load_defaults

        defaults = load_defaults(template_root / "config")
        assert defaults.mode.role_id.value == "general_assistant"
        assert defaults.mode.relationship_style.value == "platonic"
        assert defaults.voice.silence_delay_sec == 1.5
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)
