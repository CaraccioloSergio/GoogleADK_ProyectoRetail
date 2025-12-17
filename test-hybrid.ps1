# Script para testing HÍBRIDO: Agente local + Backoffice Cloud Run
# Uso: .\test-hybrid.ps1

Write-Host "🌐 YopLabs Agent Demo - HYBRID Testing (Local Agent + Cloud Backoffice)" -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos en el directorio correcto
if (-not (Test-Path "main.py")) {
    Write-Host "❌ ERROR: Este script debe ejecutarse desde la raíz del proyecto" -ForegroundColor Red
    exit 1
}

# Verificar que existe .env.local.hybrid
if (-not (Test-Path "retail_agent\.env.local.hybrid")) {
    Write-Host "❌ ERROR: No se encuentra retail_agent\.env.local.hybrid" -ForegroundColor Red
    exit 1
}

# Copiar configuración híbrida
Write-Host "⚙️  Configurando entorno híbrido..." -ForegroundColor Yellow
Copy-Item "retail_agent\.env.local.hybrid" "retail_agent\.env" -Force

# Verificar entorno virtual
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "📦 Entorno virtual no encontrado. Creando..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ Entorno virtual creado" -ForegroundColor Green
}

# Activar entorno virtual
Write-Host "🔄 Activando entorno virtual..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Instalar dependencias
Write-Host "📚 Instalando dependencias..." -ForegroundColor Yellow
pip install -q -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ERROR instalando dependencias" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Entorno configurado!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 ARQUITECTURA HÍBRIDA:" -ForegroundColor Cyan
Write-Host "   ✓ WhatsApp Agent: LOCAL (rápido, con debugging)" -ForegroundColor White
Write-Host "   ✓ Backoffice API: CLOUD RUN (persistente, público)" -ForegroundColor White
Write-Host "   ✓ Checkout UI: CLOUD RUN (accesible desde cualquier dispositivo)" -ForegroundColor White
Write-Host ""
Write-Host "🚀 Para iniciar, necesitás 2 terminales:" -ForegroundColor Cyan
Write-Host ""
Write-Host "Terminal 1 - WhatsApp Server (puerto 8080):" -ForegroundColor Yellow
Write-Host '   python -m uvicorn main:app --reload --port 8080' -ForegroundColor White
Write-Host ""
Write-Host "Terminal 2 - ngrok:" -ForegroundColor Yellow
Write-Host '   ngrok http 8080' -ForegroundColor White
Write-Host ""
Write-Host "📱 Luego configurá Twilio:" -ForegroundColor Cyan
Write-Host "   URL: https://xxxx-xxx-xxx.ngrok-free.app/whatsapp" -ForegroundColor White
Write-Host ""

# Ofrecer iniciar servicios automáticamente
$response = Read-Host "¿Querés que inicie los servicios automáticamente? (s/n)"

if ($response -eq "s" -or $response -eq "S") {
    Write-Host ""
    Write-Host "🚀 Iniciando servicios..." -ForegroundColor Green
    
    # Iniciar main (que incluye whatsapp + backoffice endpoints) en nueva ventana
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\.venv\Scripts\Activate.ps1; Write-Host '🤖 WhatsApp Agent Server (LOCAL)' -ForegroundColor Green; Write-Host '📡 Conectando a Cloud Run:' -ForegroundColor Cyan; Write-Host '   https://yoplabs-agent-demo-697941530409.us-central1.run.app' -ForegroundColor White; Write-Host ''; python -m uvicorn main:app --reload --port 8080"
    
    Start-Sleep -Seconds 3
    
    Write-Host ""
    Write-Host "✅ Servicio iniciado en ventana separada" -ForegroundColor Green
    Write-Host ""
    Write-Host "📍 URLs:" -ForegroundColor Cyan
    Write-Host "   WhatsApp webhook (local): http://localhost:8080/whatsapp" -ForegroundColor White
    Write-Host "   Backoffice Admin (cloud): https://yoplabs-agent-demo-697941530409.us-central1.run.app/admin" -ForegroundColor White
    Write-Host "   Checkout UI (cloud): https://yoplabs-agent-demo-697941530409.us-central1.run.app/checkout-ui/" -ForegroundColor White
    Write-Host ""
    Write-Host "⚠️  IMPORTANTE: Iniciá ngrok manualmente en otra terminal:" -ForegroundColor Yellow
    Write-Host "   ngrok http 8080" -ForegroundColor White
    Write-Host ""
    Write-Host "🔗 Luego configurá Twilio con la URL de ngrok + /whatsapp" -ForegroundColor Yellow
    Write-Host ""
}
