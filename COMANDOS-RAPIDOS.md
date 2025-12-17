# ⚡ COMANDOS RÁPIDOS - Referencia

## 🏠 Local Development

### Setup Inicial
```powershell
# Opción A: Script automático (RECOMENDADO)
.\test-local.ps1

# Opción B: Manual
Copy-Item retail_agent\.env.local retail_agent\.env
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Levantar Servicios
```powershell
# Terminal 1 - Backoffice (puerto 8080)
$env:ENV="local"
uvicorn backoffice_app:app --reload --host 0.0.0.0 --port 8080

# Terminal 2 - Checkout UI (puerto 8001)
cd checkout_web
python -m http.server 8001

# Terminal 3 - WhatsApp Server (puerto 9002)
$env:ENV="local"
uvicorn whatsapp_server:app --reload --port 9002

# Terminal 4 - ngrok
ngrok http 9002
```

### Testing Local
```powershell
# Health checks
curl http://localhost:8080/admin
curl http://localhost:8001/index.html
curl http://localhost:9002/

# Tests automáticos
python quick-test.py local

# Ver logs
# Los ves directamente en las terminales de uvicorn
```

---

## ☁️ Cloud Run (Producción)

### Deploy
```powershell
# Opción A: Script automático (RECOMENDADO)
.\deploy.ps1

# Opción B: Manual
gcloud config set project yopdev-prod
gcloud builds submit --tag gcr.io/yopdev-prod/yoplabs-agent-demo
gcloud run deploy yoplabs-agent-demo `
  --image gcr.io/yopdev-prod/yoplabs-agent-demo `
  --platform managed `
  --region us-central1 `
  --allow-unauthenticated `
  --env-vars-file env.prod.yaml `
  --port 8080 `
  --memory 1Gi `
  --timeout 300
```

### Logs
```powershell
# Tiempo real
.\logs.ps1

# Solo errores
.\logs.ps1 -Errors

# Últimos 50
.\logs.ps1 -Recent

# Manual
gcloud run services logs read yoplabs-agent-demo --region us-central1 --follow
```

### Testing Producción
```powershell
# Health check
curl https://yoplabs-agent-demo-697941530409.us-central1.run.app/healthz

# Tests automáticos
python quick-test.py prod

# Test específico de backoffice
curl https://yoplabs-agent-demo-697941530409.us-central1.run.app/users `
  -H "x-api-key: 19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk"
```

### Monitoreo
```powershell
# Ver servicio
gcloud run services describe yoplabs-agent-demo --region us-central1

# URL del servicio
gcloud run services describe yoplabs-agent-demo `
  --region us-central1 `
  --format "value(status.url)"

# Revisiones
gcloud run revisions list `
  --service yoplabs-agent-demo `
  --region us-central1

# Métricas (en Console)
# https://console.cloud.google.com/run/detail/us-central1/yoplabs-agent-demo
```

---

## 🔧 Twilio

### Configurar Webhook

**Local (con ngrok):**
1. Obtener URL de ngrok: `https://xxx.ngrok-free.app`
2. Ir a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
3. Webhook URL: `https://xxx.ngrok-free.app/whatsapp`
4. Método: POST
5. Guardar

**Producción:**
1. URL: `https://yoplabs-agent-demo-697941530409.us-central1.run.app/whatsapp`
2. Método: POST
3. Guardar

### Conectar al Sandbox
```
# Enviar al número de Twilio (ej: +1 415 523 8886)
join <código-que-te-dieron>
```

### Probar
```
# Mensaje simple
Hola

# Flujo completo
Quiero comprar leche
```

---

## 🗄️ Base de Datos

### Acceder a SQLite
```powershell
# Abrir DB
sqlite3 retail.db

# Ver tablas
.tables

# Ver usuarios
SELECT * FROM users;

# Ver productos
SELECT * FROM products;

# Ver carritos activos
SELECT * FROM carts WHERE status = 'active';

# Ver órdenes
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;

# Salir
.quit
```

### Backup
```powershell
# Backup
Copy-Item retail.db retail.db.backup

# Restore
Copy-Item retail.db.backup retail.db
```

### Reset completo (⚠️ CUIDADO)
```powershell
Remove-Item retail.db
# Reiniciar backoffice_app.py para recrear con schema.sql
```

---

## 🔍 Debugging

### Ver logs detallados
```powershell
# Local
# Los ves en las terminales de uvicorn

# Producción
.\logs.ps1
```

### Probar tools manualmente
```powershell
# Activar venv
.\.venv\Scripts\Activate.ps1

# Python
python

# En Python REPL
>>> import sys
>>> sys.path.insert(0, "retail_agent")
>>> from agent_tools_backoffice import search_users, search_products
>>> 
>>> # Probar search_users
>>> search_users(phone="1234567890")
>>> 
>>> # Probar search_products
>>> search_products(query="leche")
>>> 
>>> # Salir
>>> exit()
```

### Verificar configuración
```powershell
# Ver .env actual
cat retail_agent\.env

# Ver env.prod.yaml
cat env.prod.yaml

# Ver versión de Python
python --version

# Ver paquetes instalados
pip list
```

---

## 📦 Gestión de Dependencias

### Actualizar dependencias
```powershell
pip install --upgrade google-adk google-genai fastapi uvicorn
pip freeze > requirements.txt
```

### Verificar versiones
```powershell
pip show google-adk
pip show google-genai
pip show fastapi
```

---

## 🔐 Variables de Entorno

### Cambiar entre local y prod
```powershell
# Para desarrollo local
Copy-Item retail_agent\.env.local retail_agent\.env

# Para producción (antes de deploy)
Copy-Item retail_agent\.env.prod retail_agent\.env
# O editar retail_agent\.env manualmente
```

### Verificar variables actuales
```powershell
# Local
cat retail_agent\.env | Select-String "BACKOFFICE_BASE_URL"
cat retail_agent\.env | Select-String "ENV="

# Producción (Cloud Run)
gcloud run services describe yoplabs-agent-demo `
  --region us-central1 `
  --format "value(spec.template.spec.containers[0].env)"
```

### Actualizar variable en Cloud Run
```powershell
# Sin redesplegar
gcloud run services update yoplabs-agent-demo `
  --region us-central1 `
  --update-env-vars NUEVA_VAR=valor

# Con archivo completo (recomendado)
gcloud run services update yoplabs-agent-demo `
  --region us-central1 `
  --env-vars-file env.prod.yaml
```

---

## 🧹 Limpieza

### Limpiar archivos temporales
```powershell
# Python cache
Get-ChildItem -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force

# Logs viejos (si los guardaste)
Remove-Item logs-*.txt
```

### Limpiar imágenes Docker viejas
```bash
# Ver imágenes
gcloud container images list --repository=gcr.io/yopdev-prod

# Listar tags de una imagen
gcloud container images list-tags gcr.io/yopdev-prod/yoplabs-agent-demo

# Eliminar imagen específica
gcloud container images delete gcr.io/yopdev-prod/yoplabs-agent-demo:TAG
```

---

## 🚨 Troubleshooting Rápido

### WhatsApp no responde
```powershell
# 1. Verificar webhook en Twilio (debe terminar en /whatsapp)
# 2. Ver logs
.\logs.ps1

# 3. Probar endpoint manualmente
curl -X POST https://tu-url/whatsapp `
  -F "Body=test" `
  -F "From=whatsapp:+1234567890"
```

### Agent crashea
```powershell
# 1. Ver logs
.\logs.ps1 -Errors

# 2. Verificar BACKOFFICE_BASE_URL
cat retail_agent\.env | Select-String "BACKOFFICE_BASE_URL"

# 3. Probar tools manualmente (ver sección Debugging)
```

### Link de checkout no funciona
```powershell
# 1. Verificar CHECKOUT_BASE_URL
cat retail_agent\.env | Select-String "CHECKOUT_BASE_URL"

# 2. Probar URL directamente
curl https://tu-url/checkout-ui/index.html
```

---

## 📊 URLs Importantes

### Local
```
Backoffice Admin:   http://localhost:8080/admin
Backoffice API:     http://localhost:8080/users
Checkout UI:        http://localhost:8001/index.html
WhatsApp Server:    http://localhost:9002/
WhatsApp Webhook:   http://localhost:9002/whatsapp
```

### Producción
```
Base URL:           https://yoplabs-agent-demo-697941530409.us-central1.run.app
Health Check:       https://yoplabs-agent-demo-697941530409.us-central1.run.app/healthz
WhatsApp Webhook:   https://yoplabs-agent-demo-697941530409.us-central1.run.app/whatsapp
Backoffice Admin:   https://yoplabs-agent-demo-697941530409.us-central1.run.app/admin
Checkout UI:        https://yoplabs-agent-demo-697941530409.us-central1.run.app/checkout-ui/index.html
```

### Twilio
```
Console:            https://console.twilio.com
WhatsApp Sandbox:   https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
```

### Google Cloud
```
Cloud Run:          https://console.cloud.google.com/run/detail/us-central1/yoplabs-agent-demo
Container Registry: https://console.cloud.google.com/gcr/images/yopdev-prod
Logs:               https://console.cloud.google.com/logs/query
```

---

## 💾 Backups Recomendados

### Antes de cambios mayores
```powershell
# Backup de DB
Copy-Item retail.db "retail.db.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# Backup de .env
Copy-Item retail_agent\.env "retail_agent\.env.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# Commit en git (si usas)
git add .
git commit -m "Backup before major changes"
git push
```

---

## 🎯 Comandos Más Usados (Top 10)

```powershell
# 1. Deploy rápido
.\deploy.ps1

# 2. Ver logs en tiempo real
.\logs.ps1

# 3. Setup local
.\test-local.ps1

# 4. Tests automáticos
python quick-test.py prod

# 5. Ver logs de errores
.\logs.ps1 -Errors

# 6. Health check producción
curl https://yoplabs-agent-demo-697941530409.us-central1.run.app/healthz

# 7. Verificar config
cat retail_agent\.env

# 8. Activar venv
.\.venv\Scripts\Activate.ps1

# 9. Ver usuarios en DB
sqlite3 retail.db "SELECT * FROM users LIMIT 10;"

# 10. URL del servicio
gcloud run services describe yoplabs-agent-demo --region us-central1 --format "value(status.url)"
```

---

**Tip:** Guarda este archivo en favoritos para acceso rápido! 📌

Última actualización: Diciembre 2024
