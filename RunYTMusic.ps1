# --- Ollama ---
if (-not (Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue)) {
    Write-Host "Starting Ollama..."
    Start-Process -NoNewWindow -FilePath "ollama" -ArgumentList "serve"
} else {
    Write-Host "Ollama already running."
}

# --- Docker Desktop ---
if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Write-Host "Starting Docker Desktop..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Start-Sleep -Seconds 15
} else {
    Write-Host "Docker Desktop already running."
}

# --- Airflow ---
Set-Location "$HOME\.ytmusicrec\airflow"
docker compose up -d

Write-Host ""
Write-Host "ytmusicrec fully running ✅"
