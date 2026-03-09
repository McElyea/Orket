#!/usr/bin/env bash
set -euo pipefail

npm --prefix src/companion_app/frontend install
npm --prefix src/companion_app/frontend run build

echo "Frontend build complete."
