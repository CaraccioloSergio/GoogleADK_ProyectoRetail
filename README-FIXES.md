# 🔥 FIXES APLICADOS - README

## ⚠️ PROBLEMAS QUE TENÍAS

### 1. WhatsApp no respondía
- **Causa**: Endpoint incorrecto (`/` en vez de `/whatsapp`)
- **Fix**: Agregado endpoint `/whatsapp` + manejo robusto de errores

### 2. Agent crasheaba al validar usuario
- **Causa**: 
  - Instrucciones muy complejas causaban loops
  - Múltiples llamadas HTTP sin manejo de errores
  - URLs incorrectas entre local y producción
- **Fix**: 
  - Simplificadas instrucciones del agente
  - Agregado manejo robusto de errores en tools
  - Separadas configuraciones `.env` y `.env.local`

### 3. Configuración mezclada local/producción
- **Causa**: Un solo `.env` con configuración inconsistente
- **Fix**: 
  - `.env` → Configuración de PRODUCCIÓN
  - `.env.local` → Configuración LOCAL
  - Scripts automatizan el cambio

---

## 🚀 INICIO RÁPIDO

### Opción A: Testing Local (RECOMENDADO PRIMERO)

```powershell
# 1. Ejecutar script de setup
.\test-local.ps1

# 2. Seguir las instrucciones en pantalla
# El script:
# - Configura .env para local
# - Instala dependencias
# - (Opcional) Inicia todos los servicios
```

### Opción B: Deploy a Producción

```powershell
# 1. Ejecutar script de deploy
.\deploy.ps1

# 2. Configurar Twilio con la URL que te muestra
# 3. Verificar logs
.\logs.ps1
```

---

## 📁 ARCHIVOS IMPORTANTES

### Configuración
- `retail_agent/.env` → **PRODUCCIÓN** (Cloud Run)
- `retail_agent/.env.local` → **LOCAL** (localhost)
- `env.prod.yaml` → Variables de Cloud Run

### Código
- `whatsapp_server.py` → ✅ CORREGIDO
- `retail_agent/agent.py` → ✅ SIMPLIFICADO
- `retail_agent/agent_tools_backoffice.py` → ✅ Mejorado manejo de errores

### Scripts
- `test-local.ps1` → Setup y testing local
- `deploy.ps1` → Deploy automático a Cloud Run
- `logs.ps1` → Ver logs de producción

### Documentación
- `DEBUGGING.md` → Guía detallada de debugging
- `README.md` → Este archivo
- `CONFIG.md` → Configuración original

---

## 🔍 VERIFICACIÓN RÁPIDA

### Testing Local

```powershell
# 1. Verificar que los servicios están corriendo
curl http://localhost:8080/admin        # Backoffice
curl http://localhost:8001/index.html   # Checkout
curl http://localhost:9002/             # WhatsApp server

# 2. Ver logs del WhatsApp server
# (En la terminal donde corre uvicorn)

# 3. Probar con Twilio
# Enviar mensaje al número de sandbox
```

### Testing Producción

```powershell
# 1. Verificar health check
curl https://yoplabs-agent-demo-697941530409.us-central1.run.app/healthz

# 2. Ver logs
.\logs.ps1

# 3. Probar con Twilio
# Enviar mensaje al número de sandbox
```

---

## ⚙️ CONFIGURACIÓN DE TWILIO

### Sandbox Settings
1. Ir a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. En "Sandbox Configuration"
3. Configurar webhook:

**Local (con ngrok):**
```
https://tu-ngrok-url.ngrok-free.app/whatsapp
```

**Producción:**
```
https://yoplabs-agent-demo-697941530409.us-central1.run.app/whatsapp
```

4. Método: **POST**
5. Guardar

### Verificar conexión
1. Unirse al sandbox: Enviar el código que te da Twilio
2. Probar: `Hola`
3. Deberías recibir respuesta de Milo

---

## 🐛 TROUBLESHOOTING

### "No recibo respuestas en WhatsApp"

1. **Verificar webhook configurado:**
   - Debe terminar en `/whatsapp` (no `/`)
   - Debe ser HTTPS (ngrok o Cloud Run)

2. **Ver logs:**
   ```powershell
   # Local
   # Mirar terminal de uvicorn
   
   # Producción
   .\logs.ps1
   ```

3. **Verificar que servicios están corriendo:**
   ```powershell
   # Local
   curl http://localhost:9002/
   
   # Producción
   curl https://yoplabs-agent-demo-697941530409.us-central1.run.app/healthz
   ```

### "Agent crashea al buscar usuario"

1. **Verificar URLs en .env:**
   ```env
   # Local debe ser:
   BACKOFFICE_BASE_URL=http://127.0.0.1:8080
   
   # Producción debe ser:
   BACKOFFICE_BASE_URL=https://yoplabs-agent-demo-697941530409.us-central1.run.app
   ```

2. **Verificar API key:**
   ```env
   # Debe ser la misma en .env y env.prod.yaml
   BACKOFFICE_API_KEY=19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk
   ```

3. **Probar manualmente:**
   ```python
   # En Python
   from retail_agent.agent_tools_backoffice import search_users
   search_users(phone="1234567890")
   ```

### "Link de checkout no funciona"

1. **Verificar CHECKOUT_BASE_URL:**
   ```env
   # Local:
   CHECKOUT_BASE_URL=http://localhost:8001/index.html
   
   # Producción:
   CHECKOUT_BASE_URL=https://yoplabs-agent-demo-697941530409.us-central1.run.app/checkout-ui/index.html
   ```

2. **Probar URL directamente:**
   ```
   Local: http://localhost:8001/index.html
   Producción: https://yoplabs-agent-demo-697941530409.us-central1.run.app/checkout-ui/index.html
   ```

---

## 📊 MONITOREO

### Ver logs en tiempo real
```powershell
.\logs.ps1
```

### Ver solo errores
```powershell
.\logs.ps1 -Errors
```

### Ver logs recientes
```powershell
.\logs.ps1 -Recent
```

### Cloud Run Console
https://console.cloud.google.com/run/detail/us-central1/yoplabs-agent-demo

---

## 🎯 CHECKLIST PRE-DEPLOY

Antes de hacer deploy, verificar:

- [ ] ✅ `retail_agent/.env` tiene URLs de PRODUCCIÓN
- [ ] ✅ `env.prod.yaml` tiene todas las variables
- [ ] ✅ BACKOFFICE_API_KEY coincide en ambos archivos
- [ ] ✅ Código commiteado en git (opcional pero recomendado)
- [ ] ✅ Test local funcionó correctamente

---

## 🆘 AYUDA ADICIONAL

Si después de revisar esta guía y `DEBUGGING.md` sigues con problemas:

1. **Exportar logs completos:**
   ```powershell
   .\logs.ps1 -Recent > logs-error.txt
   ```

2. **Verificar configuración:**
   ```powershell
   cat retail_agent\.env
   cat env.prod.yaml
   ```

3. **Contactar con:**
   - Logs exportados
   - Configuración (sin credenciales sensibles)
   - Descripción exacta del problema

---

## 📝 PRÓXIMOS PASOS SUGERIDOS

1. **Testing exhaustivo local** antes de deploy
2. **Habilitar validación de Twilio** en producción:
   ```env
   TWILIO_VALIDATE=true
   ```
3. **Agregar más productos** al catálogo desde el backoffice
4. **Implementar métricas** con Cloud Monitoring
5. **Configurar alertas** para errors

---

## 🎉 MEJORAS IMPLEMENTADAS

✅ Endpoint `/whatsapp` funcionando correctamente
✅ Manejo robusto de errores en todos los niveles
✅ Separación clara entre config local y producción
✅ Scripts automáticos para deploy y testing
✅ Logging detallado para debugging
✅ Documentación completa de troubleshooting
✅ Instrucciones simplificadas del agente
✅ Health checks implementados

---

**Última actualización:** Diciembre 2024  
**Versión:** 2.0 (Post-fix)
