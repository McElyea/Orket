from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.proof.prepare_northstar_disposable_aws_smoke_packet import main as packet_main
from scripts.proof.run_trusted_terraform_disposable_aws_cleanup import main as cleanup_main
from scripts.proof.run_trusted_terraform_disposable_aws_setup import main as setup_main

pytestmark = pytest.mark.end_to_end


@pytest.mark.skipif(
    os.getenv("ORKET_ENABLE_LIVE_AWS_SMOKE_TESTS") != "1",
    reason="live AWS smoke requires ORKET_ENABLE_LIVE_AWS_SMOKE_TESTS=1",
)
def test_live_aws_setup_and_cleanup_require_explicit_opt_in(tmp_path: Path) -> None:
    assert packet_main(["--seed", "live-smoke-test", "--fixture-kind", "safe", "--fixture-seed", "live-fixture", "--output-dir", str(tmp_path)]) == 0
    assert setup_main(
        [
            "--packet-dir",
            str(tmp_path),
            "--execute-live-aws",
            "--acknowledge-cost-and-mutation",
            "--output",
            str(tmp_path / "aws-setup-result.json"),
        ]
    ) == 0
    assert cleanup_main(
        [
            "--packet-dir",
            str(tmp_path),
            "--execute-live-aws",
            "--acknowledge-delete",
            "--output",
            str(tmp_path / "aws-cleanup-result.json"),
        ]
    ) == 0
