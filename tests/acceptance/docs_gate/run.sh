#!/usr/bin/env bash
set -euo pipefail

bash tests/acceptance/docs_gate/DL0_clean_pass.sh
bash tests/acceptance/docs_gate/DL1_broken_link.sh
bash tests/acceptance/docs_gate/DL2_missing_canonical.sh
bash tests/acceptance/docs_gate/DL3_missing_header_field.sh
echo "DOCS_GATE_ACCEPTANCE_OK"

