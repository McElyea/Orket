from __future__ import annotations

def run_quant_sweep() -> int:
    from quant_sweep.runner import run_quant_sweep as _run_quant_sweep

    return _run_quant_sweep()

__all__ = ["run_quant_sweep"]
