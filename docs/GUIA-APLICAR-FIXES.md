# 🚀 GUÍA RÁPIDA - APLICAR FIXES AUTOMÁTICAMENTE

## 📋 Scripts Disponibles

### 🎯 Opción 1: Script Todo-en-Uno (RECOMENDADO)
```powershell
.\fix-everything.ps1
```
**Qué hace:**
- ✅ Verifica que todos los archivos existan
- ✅ Crea backups automáticamente
- ✅ Aplica TODOS los fixes a backoffice_app.py
- ✅ Verifica que se aplicaron correctamente
- ✅ Valida sintaxis de Python
- ✅ Te ofrece levantar servicios automáticamente

**Cuándo usar:** Primera vez o cuando querés hacer todo de una

---

### 🔧 Opción 2: Solo Aplicar Fixes
```powershell
.\apply-backoffice-fixes.ps1
```
**Qué hace:**
- Crea backup con timestamp
- Aplica 12 fixes automáticamente:
  1. ENV_MODE con fallback
  2. CHECKOUT_FRONTEND_URL agregada
  3. Logging en startup
  4. Logging en require_api_key
  5. **CRÍTICO:** /users/search OR → AND
  6. Logging en search_users
  7. Logging de resultados
  8. Logging en add_item
  9. **CRÍTICO:** Validación de stock mejorada
  10. **CRÍTICO:** Validación stock items existentes
  11. Eliminar URLs hardcoded
  12. Usar variables de entorno correctas

**Cuándo usar:** Solo querés aplicar los fixes sin verificaciones extras

---

### 🔍 Opción 3: Solo Verificar
```powershell
.\verify-backoffice-fixes.ps1
```
**Qué hace:**
- Verifica que cada fix esté aplicado
- Muestra qué pasó ✅ y qué faltó ❌
- No modifica nada

**Cuándo usar:** Después de aplicar fixes manualmente o para verificar estado actual

---

## 🎬 Uso Paso a Paso

### Paso 1: Aplicar Fixes

```powershell
# Abrir PowerShell en la raíz del proyecto
cd C:\Users\Sergio\Desktop\Dev\retail-agent-demo

# Opción A: Todo automático
.\fix-everything.ps1

# Opción B: Solo fixes
.\apply-backoffice-fixes.ps1
```

### Paso 2: Verificar (si usaste Opción B)

```powershell
.\verify-backoffice-fixes.ps1
```

### Paso 3: Verificar Sintaxis

```powershell
python -c "import backoffice_app; print('✅ OK')"
```

### Paso 4: Testing Local

```powershell
# Opción A: Script automático
.\test-local.ps1

# Opción B: Manual
# Terminal 1
$env:ENV="local"
uvicorn backoffice_app:app --reload --port 8080

# Terminal 2
cd checkout_web
python -m http.server 8001

# Terminal 3
$env:ENV="local"
uvicorn whatsapp_server:app --reload --port 9002

# Terminal 4
ngrok http 9002
```

### Paso 5: Probar con WhatsApp

1. Configurar webhook en Twilio: `https://tu-ngrok-url.ngrok-free.app/whatsapp`
2. Enviar mensaje de prueba
3. Ver logs en Terminal 3 (deberías ver emojis 🔍 ✅ ❌)

---

## 🐛 Troubleshooting

### Error: "No se puede ejecutar scripts en este sistema"

```powershell
# Solución: Cambiar política de ejecución
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Luego reintentar
.\fix-everything.ps1
```

### Error: "Archivo no encontrado"

```powershell
# Verificar que estás en el directorio correcto
pwd
# Debe mostrar: ...\retail-agent-demo

# Si no, navegar al directorio correcto
cd C:\Users\Sergio\Desktop\Dev\retail-agent-demo
```

### Error: "Python no reconocido"

```powershell
# Verificar instalación de Python
python --version

# Si no funciona, usar py
py --version

# En el script, reemplazar 'python' por 'py'
```

### Verificación falló pero sintaxis OK

Si `verify-backoffice-fixes.ps1` muestra errores pero `python -c "import backoffice_app"` funciona:
- Los fixes críticos probablemente estén aplicados
- Podés continuar con testing
- Revisar warnings manualmente después

---

## 📊 Qué Hace Cada Fix

### 🚨 CRÍTICO - Fix #5: /users/search OR → AND
**Problema:** Búsqueda devuelve usuarios irrelevantes
**Fix:** Cambiar `' OR '.join(conditions)` por `' AND '.join(conditions)`
**Impacto:** El agente ahora encuentra el usuario correcto

### 🚨 CRÍTICO - Fix #9 y #10: Validación de stock
**Problema:** Permite agregar más productos del stock disponible
**Fix:** Validar stock ANTES de agregar y al actualizar
**Impacto:** No más errores de stock en checkout

### ⚠️ Fix #11 y #12: URLs de variables de entorno
**Problema:** Links hardcodeados a localhost
**Fix:** Usar `CHECKOUT_FRONTEND_URL` de variables
**Impacto:** Links funcionan en producción

### ℹ️ Otros Fixes: Logging
**Problema:** Difícil debuggear
**Fix:** Agregar `print()` con emojis en cada endpoint
**Impacto:** Debugging mucho más fácil

---

## ✅ Checklist Post-Fixes

Después de aplicar los fixes:

- [ ] Script ejecutado sin errores
- [ ] Verificación pasada (✅ > 80%)
- [ ] Sintaxis Python OK
- [ ] Backup creado
- [ ] Servicios locales levantados
- [ ] Logs muestran emojis (🔍 ✅ ❌)
- [ ] WhatsApp responde correctamente
- [ ] Búsqueda de usuario funciona
- [ ] Agregar al carrito funciona
- [ ] Stock se valida correctamente
- [ ] Checkout genera link válido

---

## 🔄 Rollback (si algo sale mal)

### Restaurar desde backup:

```powershell
# Listar backups
Get-ChildItem backoffice_app.py.backup-*

# Restaurar el más reciente
$latest = Get-ChildItem backoffice_app.py.backup-* | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Copy-Item $latest.FullName backoffice_app.py

# Verificar
python -c "import backoffice_app; print('✅ OK')"
```

---

## 📞 Siguiente Paso

Una vez que los fixes estén aplicados y verificados:

```powershell
# Deploy a producción
.\deploy.ps1
```

---

## 📝 Archivos Generados

Después de ejecutar los scripts:

```
retail-agent-demo/
├── backoffice_app.py                    (✅ corregido)
├── backoffice_app.py.backup-TIMESTAMP   (📦 backup)
├── apply-backoffice-fixes.ps1           (🔧 script aplicar)
├── verify-backoffice-fixes.ps1          (🔍 script verificar)
├── fix-everything.ps1                   (🎯 script completo)
└── BACKOFFICE-FIXES.md                  (📖 documentación)
```

---

**Tiempo estimado:** 5-10 minutos
**Dificultad:** Baja (todo automatizado)
**Resultado esperado:** ✅ Todos los fixes aplicados y verificados

---

Última actualización: Diciembre 2024
