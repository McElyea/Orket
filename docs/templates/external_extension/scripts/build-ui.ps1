$ErrorActionPreference = "Stop"

npm --prefix src/companion_app/frontend install
npm --prefix src/companion_app/frontend run build

Write-Host "Frontend build complete."
