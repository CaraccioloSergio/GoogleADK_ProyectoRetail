# 🔧 Guía de Debugging y Deployment

## 📋 Resumen de Cambios Realizados

### 1. **whatsapp_server.py** - CORREGIDO
**Problemas resueltos:**
- ✅ Agregado endpoint `/whatsapp` (antes solo estaba en `/`)
- ✅ Mejorado manejo de errores con try-catch completos
- ✅ Agregado logging detallado
- ✅ Mejorada extracción de user_id (prioriza WaId)
- ✅ Health check en GET `/`
- ✅ Manejo robusto de sesiones con fallback

### 2. **agent.py** - SIMPLIFICADO
**Problemas resueltos:**
- ✅ Instrucciones simplificadas (menos verbose)
- ✅ Flujos más claros y directos
- ✅ Eliminados loops potenciales
- ✅ Modelo cambiado a `gemini-2.0-flash-exp` (más estable)

### 3. **Variables de entorno** - ORGANIZADAS
**Archivos creados/modificados:**
- ✅ `.env` - Configuración para PRODUCCIÓN (Cloud Run)
- ✅ `.env.local` - Configuración para DESARROLLO local
- ✅ `env.prod.yaml` - Ya existía, está correcto

---

## 🐛 Debugging Local

### Paso 1: Configurar entorno local

```powershell
# 1. Copiar archivo de configuración local
Copy-Item retail_agent\.env.local retail_agent\.env

# 2. Activar entorno virtual
.\.venv\Scripts\Activate.ps1

# 3. Verificar instalación
pip install -r requirements.txt
```

### Paso 2: Levantar servicios localmente

**Terminal 1 - Backoffice:**
```powershell
$env:ENV="local"
uvicorn backoffice_app:app --reload --host 0.0.0.0 --port 8080
```

**Terminal 2 - Checkout:**
```powershell
cd checkout_web
python -m http.server 8001
```

**Terminal 3 - WhatsApp Server:**
```powershell
$env:ENV="local"
uvicorn whatsapp_server:app --reload --port 9002
```

**Terminal 4 - ngrok:**
```powershell
ngrok http 9002
```

### Paso 3: Configurar Twilio

1. Copiar URL de ngrok (ej: `https://abc123.ngrok-free.app`)
2. Ir a Twilio Console → WhatsApp Sandbox Settings
3. Configurar webhook:
   ```
   https://abc123.ngrok-free.app/whatsapp
   ```
4. Guardar cambios

### Paso 4: Probar

Enviar mensaje a tu número de Twilio WhatsApp Sandbox:
```
join <código-sandbox>
```

Luego:
```
Hola, quiero comprar algo
```

**Ver logs en Terminal 3** para debugging.

---

## 🚀 Deployment a Cloud Run

### Paso 1: Preparar para producción

```powershell
# 1. Asegurar que retail_agent/.env tenga config de producción
Copy-Item retail_agent\.env.local retail_agent\.env.prod.backup
Copy-Item retail_agent\.env retail_agent\.env  # Ya tiene config prod

# 2. Verificar env.prod.yaml
cat env.prod.yaml
```

### Paso 2: Build y Deploy

```powershell
# Configurar proyecto
gcloud config set project yopdev-prod

# Build de la imagen
gcloud builds submit --tag gcr.io/yopdev-prod/yoplabs-agent-demo

# Deploy a Cloud Run
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

### Paso 3: Obtener URL de Cloud Run

```powershell
gcloud run services describe yoplabs-agent-demo --region us-central1 --format "value(status.url)"
```

Ejemplo de output:
```
https://yoplabs-agent-demo-697941530409.us-central1.run.app
```

### Paso 4: Actualizar Twilio Webhook

1. Ir a Twilio Console → WhatsApp Sandbox
2. Configurar webhook con URL de Cloud Run:
   ```
   https://yoplabs-agent-demo-697941530409.us-central1.run.app/whatsapp
   ```
3. Guardar

---

## 🔍 Debugging en Producción

### Ver logs de Cloud Run

```powershell
# Logs en tiempo real
gcloud run services logs read yoplabs-agent-demo --region us-central1 --follow

# Logs recientes
gcloud run services logs read yoplabs-agent-demo --region us-central1 --limit 50

# Filtrar por errores
gcloud run services logs read yoplabs-agent-demo --region us-central1 --filter "severity>=ERROR"
```

### Probar endpoints manualmente

**Health check:**
```powershell
curl https://yoplabs-agent-demo-697941530409.us-central1.run.app/healthz
```

**Backoffice API:**
```powershell
curl https://yoplabs-agent-demo-697941530409.us-central1.run.app/users `
  -H "x-api-key: 19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk"
```

**Checkout UI:**
```
https://yoplabs-agent-demo-697941530409.us-central1.run.app/checkout-ui/index.html
```

---

## 🔴 Problemas Comunes y Soluciones

### Problema 1: Twilio no responde

**Síntomas:**
- Envías mensaje pero no recibes respuesta
- Twilio muestra error 11200 o timeout

**Solución:**
```powershell
# 1. Verificar que el webhook esté configurado correctamente
# URL debe ser: https://tu-servicio.run.app/whatsapp (NO /)

# 2. Verificar logs
gcloud run services logs read yoplabs-agent-demo --region us-central1 --follow

# 3. Probar endpoint manualmente
curl -X POST https://tu-servicio.run.app/whatsapp `
  -F "Body=test" `
  -F "From=whatsapp:+1234567890" `
  -F "WaId=1234567890"

# 4. Verificar que TWILIO_VALIDATE=false en producción
```

### Problema 2: Agent crashea al validar usuario

**Síntomas:**
- Bot responde pero se queda "pensando"
- Logs muestran errores en search_users o create_user

**Solución:**
```powershell
# 1. Verificar que BACKOFFICE_BASE_URL apunte a URL correcta
# En producción: https://yoplabs-agent-demo-697941530409.us-central1.run.app
# En local: http://127.0.0.1:8080

# 2. Verificar que BACKOFFICE_API_KEY sea correcta
# Debe coincidir en env.prod.yaml y en el backoffice

# 3. Probar tools manualmente desde Python
python
>>> from retail_agent.agent_tools_backoffice import search_users
>>> search_users(phone="1234567890")
```

### Problema 3: Stock insuficiente pero no ofrece alternativas

**Síntoma:**
- Bot dice "no hay stock" pero no ofrece ajustar cantidad

**Causa:**
- La tool add_product_to_cart devuelve error pero sin available_stock

**Solución:**
Ya está corregido en agent_tools_backoffice.py - verifica que esté deployado.

### Problema 4: Links de checkout rotos

**Síntomas:**
- Bot genera link pero lleva a 404
- Link no tiene los parámetros correctos

**Solución:**
```powershell
# 1. Verificar CHECKOUT_BASE_URL en env
# Debe ser: https://tu-servicio.run.app/checkout-ui/index.html

# 2. Probar checkout manualmente
# https://tu-servicio.run.app/checkout-ui/index.html?user_id=1&order_id=123

# 3. Verificar que checkout_web esté en el contenedor
docker run -it gcr.io/yopdev-prod/yoplabs-agent-demo ls -la /app/checkout_web
```

---

## 📊 Monitoreo

### Métricas clave en Cloud Run Console

1. **Request count**: Debe incrementar con cada mensaje de WhatsApp
2. **Request latency**: Debería ser < 10s (ADK puede tardar)
3. **Error rate**: Idealmente 0%
4. **Container instances**: 1-2 en demo

### Alertas recomendadas

```yaml
# Crear alerta de error rate
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Agent Error Rate" \
  --condition-threshold-value=0.1 \
  --condition-threshold-duration=300s
```

---

## 🎯 Checklist de Deploy

Antes de hacer deploy, verificar:

- [ ] `retail_agent/.env` tiene URLs de producción
- [ ] `env.prod.yaml` tiene todas las variables necesarias
- [ ] BACKOFFICE_API_KEY coincide en ambos archivos
- [ ] Twilio webhook apunta a `/whatsapp` (no `/`)
- [ ] CHECKOUT_BASE_URL apunta a `/checkout-ui/index.html`
- [ ] TWILIO_VALIDATE=false en producción (por ahora)
- [ ] Logs de Cloud Run muestran "ok" en health check

---

## 📝 Comandos Útiles

```powershell
# Ver todas las revisiones
gcloud run revisions list --service yoplabs-agent-demo --region us-central1

# Rollback a revisión anterior
gcloud run services update-traffic yoplabs-agent-demo `
  --to-revisions REVISION_NAME=100 `
  --region us-central1

# Ver variables de entorno actuales
gcloud run services describe yoplabs-agent-demo `
  --region us-central1 `
  --format "value(spec.template.spec.containers[0].env)"

# Actualizar una variable sin redesplegar
gcloud run services update yoplabs-agent-demo `
  --region us-central1 `
  --update-env-vars BACKOFFICE_API_KEY=new-key

# Eliminar servicio
gcloud run services delete yoplabs-agent-demo --region us-central1
```

---

## 🆘 Soporte

Si sigues teniendo problemas:

1. **Revisar logs detallados:**
   ```powershell
   gcloud run services logs read yoplabs-agent-demo --region us-central1 --limit 200
   ```

2. **Verificar configuración de Twilio:**
   - Webhook URL correcta
   - Número de sandbox activo
   - Usuario conectado al sandbox

3. **Probar endpoints individualmente:**
   - Health check: `/healthz`
   - WhatsApp webhook: `/whatsapp` (POST)
   - Backoffice: `/users` (GET con API key)

4. **Contactar al equipo** con:
   - Logs completos
   - Mensaje de error exacto
   - Configuración de Twilio (sin credenciales)
