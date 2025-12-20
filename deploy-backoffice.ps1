# Script para deployar el backoffice a Cloud Run
# Uso: .\deploy-backoffice.ps1

Write-Host "YopLabs Agent Demo - Deploy Backoffice to Cloud Run" -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos en el directorio correcto
if (-not (Test-Path "backoffice_app.py")) {
    Write-Host "ERROR: Este script debe ejecutarse desde la raiz del proyecto" -ForegroundColor Red
    exit 1
}

# Verificar que gcloud esta instalado
try {
    gcloud --version | Out-Null
} catch {
    Write-Host "ERROR: gcloud CLI no esta instalado" -ForegroundColor Red
    Write-Host "Instala desde: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

# Confirmar deploy
Write-Host "Esto va a deployar el backoffice a Cloud Run." -ForegroundColor Yellow
Write-Host "El codigo sera deployado pero la base de datos NO se tocara." -ForegroundColor Green
Write-Host ""
$confirm = Read-Host "Continuar con el deploy? (s/n)"

if ($confirm -ne "s" -and $confirm -ne "S") {
    Write-Host "Deploy cancelado." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Iniciando deploy a Cloud Run..." -ForegroundColor Cyan
Write-Host ""

# Deploy
gcloud run deploy yoplabs-agent-demo --source . --region us-central1 --project yopdev-prod --allow-unauthenticated

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Deploy exitoso!" -ForegroundColor Green
    Write-Host ""
    Write-Host "PROXIMOS PASOS:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. Aplicar migracion de base de datos:" -ForegroundColor Yellow
    Write-Host "   https://yoplabs-agent-demo-697941530409.us-central1.run.app/admin/login" -ForegroundColor White
    Write-Host "   Luego ir a: /admin/migrate" -ForegroundColor White
    Write-Host ""
    Write-Host "2. Verificar en el admin:" -ForegroundColor Yellow
    Write-Host "   https://yoplabs-agent-demo-697941530409.us-central1.run.app/admin/users" -ForegroundColor White
    Write-Host ""
    Write-Host "3. Levantar agente local:" -ForegroundColor Yellow
    Write-Host "   .\test-hybrid.ps1" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Deploy fallo" -ForegroundColor Red
    Write-Host "Revisa los errores arriba" -ForegroundColor Yellow
    exit 1
}
