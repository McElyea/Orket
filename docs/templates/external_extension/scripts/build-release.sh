#!/usr/bin/env bash
set -euo pipefail

rm -rf dist
python -m build --sdist --outdir dist .

echo "Release build complete."
