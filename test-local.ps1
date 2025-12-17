# Script para testing local
# Uso: .\test-local.ps1

Write-Host "YopLabs Agent Demo - Local Testing" -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos en el directorio correcto
if (-not (Test-Path "main.py")) {
    Write-Host "ERROR: Este script debe ejecutarse desde la raiz del proyecto" -ForegroundColor Red
    exit 1
}

# Verificar que existe .env.local
if (-not (Test-Path "retail_agent\.env.local")) {
    Write-Host "ERROR: No se encuentra retail_agent\.env.local" -ForegroundColor Red
    Write-Host "   Crea el archivo copiando .env.example" -ForegroundColor Yellow
    exit 1
}

# Copiar configuracion local
Write-Host "Configurando entorno local..." -ForegroundColor Yellow
Copy-Item "retail_agent\.env.local" "retail_agent\.env" -Force

# Verificar entorno virtual
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Entorno virtual no encontrado. Creando..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "Entorno virtual creado" -ForegroundColor Green
}

# Activar entorno virtual
Write-Host "Activando entorno virtual..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Instalar dependencias
Write-Host "Instalando dependencias..." -ForegroundColor Yellow
pip install -q -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR instalando dependencias" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Entorno configurado!" -ForegroundColor Green
Write-Host ""
Write-Host "Para levantar los servicios, abri 4 terminales:" -ForegroundColor Cyan
Write-Host ""
Write-Host "Terminal 1 - Backoffice (puerto 8080):" -ForegroundColor Yellow
Write-Host '   $env:ENV="local"' -ForegroundColor White
Write-Host '   uvicorn backoffice_app:app --reload --host 0.0.0.0 --port 8080' -ForegroundColor White
Write-Host ""
Write-Host "Terminal 2 - Checkout UI (puerto 8001):" -ForegroundColor Yellow
Write-Host '   cd checkout_web' -ForegroundColor White
Write-Host '   python -m http.server 8001' -ForegroundColor White
Write-Host ""
Write-Host "Terminal 3 - WhatsApp Server (puerto 9002):" -ForegroundColor Yellow
Write-Host '   $env:ENV="local"' -ForegroundColor White
Write-Host '   uvicorn whatsapp_server:app --reload --port 9002' -ForegroundColor White
Write-Host ""
Write-Host "Terminal 4 - ngrok:" -ForegroundColor Yellow
Write-Host '   ngrok http 9002' -ForegroundColor White
Write-Host ""
Write-Host "Luego configura Twilio con la URL de ngrok + /whatsapp" -ForegroundColor Cyan
Write-Host ""

# Ofrecer iniciar servicios automaticamente
$response = Read-Host "Queres que inicie los servicios automaticamente? (s/n)"

if ($response -eq "s" -or $response -eq "S") {
    Write-Host ""
    Write-Host "Iniciando servicios..." -ForegroundColor Green
    
    # Iniciar backoffice en nueva ventana
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; `$env:ENV='local'; .\.venv\Scripts\Activate.ps1; uvicorn backoffice_app:app --reload --host 0.0.0.0 --port 8080"
    
    Start-Sleep -Seconds 2
    
    # Iniciar checkout en nueva ventana
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\checkout_web'; python -m http.server 8001"
    
    Start-Sleep -Seconds 2
    
    # Iniciar whatsapp server en nueva ventana
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; `$env:ENV='local'; .\.venv\Scripts\Activate.ps1; uvicorn whatsapp_server:app --reload --port 9002"
    
    Write-Host ""
    Write-Host "Servicios iniciados en ventanas separadas" -ForegroundColor Green
    Write-Host ""
    Write-Host "URLs locales:" -ForegroundColor Cyan
    Write-Host "   Backoffice: http://localhost:8080/admin" -ForegroundColor White
    Write-Host "   Checkout UI: http://localhost:8001/index.html" -ForegroundColor White
    Write-Host "   WhatsApp webhook: http://localhost:9002/whatsapp" -ForegroundColor White
    Write-Host ""
    Write-Host "No olvides iniciar ngrok manualmente en otra terminal:" -ForegroundColor Yellow
    Write-Host "   ngrok http 9002" -ForegroundColor White
    Write-Host ""
}
