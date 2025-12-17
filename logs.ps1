# Script para ver logs de Cloud Run
# Uso: .\logs.ps1 [opciones]
#   .\logs.ps1           - Ver logs en tiempo real
#   .\logs.ps1 -Recent   - Ver últimos 50 logs
#   .\logs.ps1 -Errors   - Ver solo errores

param(
    [switch]$Recent,
    [switch]$Errors
)

$SERVICE_NAME = "yoplabs-agent-demo"
$REGION = "us-central1"

Write-Host "📊 Logs de $SERVICE_NAME" -ForegroundColor Cyan
Write-Host ""

if ($Errors) {
    Write-Host "🔴 Mostrando solo errores..." -ForegroundColor Yellow
    gcloud run services logs read $SERVICE_NAME `
        --region $REGION `
        --filter "severity>=ERROR" `
        --limit 100
}
elseif ($Recent) {
    Write-Host "📋 Mostrando últimos 50 logs..." -ForegroundColor Yellow
    gcloud run services logs read $SERVICE_NAME `
        --region $REGION `
        --limit 50
}
else {
    Write-Host "🔴 Logs en tiempo real (Ctrl+C para salir)..." -ForegroundColor Yellow
    Write-Host ""
    gcloud run services logs read $SERVICE_NAME `
        --region $REGION `
        --follow
}
