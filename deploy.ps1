# Script de deployment a Cloud Run
# Uso: .\deploy.ps1

Write-Host "🚀 YopLabs Agent Demo - Deploy to Cloud Run" -ForegroundColor Cyan
Write-Host ""

# Variables
$PROJECT_ID = "yopdev-prod"
$SERVICE_NAME = "yoplabs-agent-demo"
$REGION = "us-central1"
$IMAGE_NAME = "gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Verificar que estamos en el directorio correcto
if (-not (Test-Path "main.py")) {
    Write-Host "❌ Error: Este script debe ejecutarse desde la raíz del proyecto" -ForegroundColor Red
    exit 1
}

# Verificar que existe env.prod.yaml
if (-not (Test-Path "env.prod.yaml")) {
    Write-Host "❌ Error: No se encuentra env.prod.yaml" -ForegroundColor Red
    exit 1
}

Write-Host "📋 Verificando configuración..." -ForegroundColor Yellow

# Configurar proyecto
gcloud config set project $PROJECT_ID

Write-Host ""
Write-Host "🔨 Building Docker image..." -ForegroundColor Yellow
gcloud builds submit --tag $IMAGE_NAME

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error en el build" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🚢 Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image $IMAGE_NAME `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --env-vars-file env.prod.yaml `
    --port 8080 `
    --memory 1Gi `
    --timeout 300 `
    --max-instances 3 `
    --min-instances 1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error en el deploy" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Deploy exitoso!" -ForegroundColor Green
Write-Host ""

# Obtener URL del servicio
$SERVICE_URL = gcloud run services describe $SERVICE_NAME --region $REGION --format "value(status.url)"

Write-Host "📍 URL del servicio:" -ForegroundColor Cyan
Write-Host "   $SERVICE_URL" -ForegroundColor White
Write-Host ""

Write-Host "🔗 Endpoints importantes:" -ForegroundColor Cyan
Write-Host "   Health check: $SERVICE_URL/healthz" -ForegroundColor White
Write-Host "   WhatsApp webhook: $SERVICE_URL/whatsapp" -ForegroundColor White
Write-Host "   Backoffice admin: $SERVICE_URL/admin" -ForegroundColor White
Write-Host "   Checkout UI: $SERVICE_URL/checkout-ui/index.html" -ForegroundColor White
Write-Host ""

Write-Host "⚙️  Próximos pasos:" -ForegroundColor Yellow
Write-Host "   1. Configurar Twilio webhook con: $SERVICE_URL/whatsapp" -ForegroundColor White
Write-Host "   2. Probar enviando mensaje al número de Twilio" -ForegroundColor White
Write-Host "   3. Monitorear logs con: gcloud run services logs read $SERVICE_NAME --region $REGION --follow" -ForegroundColor White
Write-Host ""
