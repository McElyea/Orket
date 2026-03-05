from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from quant_sweep.runner import run_quant_sweep


if __name__ == "__main__":
    raise SystemExit(run_quant_sweep())

