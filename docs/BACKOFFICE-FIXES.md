# 🚨 BACKOFFICE_APP.PY - PROBLEMAS ENCONTRADOS Y FIXES

## 🔴 PROBLEMAS CRÍTICOS ENCONTRADOS

### 1. `/users/search` - Query SQL INCORRECTA ⚠️⚠️⚠️
**Problema:** Usa `OR` en vez de `AND` en la búsqueda
```python
# ANTES (INCORRECTO):
sql = f"""
    SELECT ... FROM users
    WHERE {' OR '.join(conditions)}  # ❌ INCORRECTO
"""
```

**Impacto:**
- Si buscas por `phone="123" AND name="Juan"`, devuelve TODOS los usuarios con phone="123" O name="Juan"
- Esto causa que el agente encuentre múltiples usuarios cuando debería encontrar uno solo
- El agente crashea porque no sabe cuál usuario usar

**Fix:**
```python
# DESPUÉS (CORRECTO):
sql = f"""
    SELECT ... FROM users
    WHERE {' AND '.join(conditions)}  # ✅ CORRECTO
"""
```

---

### 2. `/carts/add_item` - Sin validación de stock ANTES de agregar
**Problema:** Solo chequea stock en el endpoint, pero no valida cuando hay items existentes
```python
# ANTES:
if product["stock"] < payload.quantity:  # Solo valida cantidad nueva
    raise HTTPException(...)

# Si el item ya existe, suma sin validar
new_qty = existing_item["quantity"] + payload.quantity
cur.execute("UPDATE cart_items SET quantity = ?", (new_qty,))
```

**Impacto:**
- El agente puede agregar más cantidad de la que hay en stock
- Causa errores silenciosos en checkout

**Fix:**
```python
# DESPUÉS:
stock_available = product["stock"] if product["stock"] is not None else 999999

# Validar cantidad nueva
if stock_available < payload.quantity:
    raise HTTPException(...)

# Si existe, validar NUEVA cantidad total
if existing_item:
    new_qty = existing_item["quantity"] + payload.quantity
    if stock_available < new_qty:  # ✅ Validar total
        raise HTTPException(...)
```

---

### 3. `/orders/checkout` y `/checkout/{order_id}` - URLs hardcodeadas
**Problema:** URL de checkout hardcodeada a localhost
```python
# ANTES:
payment_url = (
    f"http://localhost:8001/index.html"  # ❌ Hardcoded
    f"?order_id={order['id']}&..."
)
```

**Impacto:**
- En producción (Cloud Run), genera links a localhost
- Los links no funcionan para el usuario

**Fix:**
```python
# DESPUÉS:
# En startup:
CHECKOUT_FRONTEND_URL = os.getenv("CHECKOUT_FRONTEND_URL")

# En endpoints:
payment_url = f"{CHECKOUT_FRONTEND_URL}?..."  # ✅ Usa variable de entorno
```

---

### 4. Sin logging en endpoints de API
**Problema:** Difícil debuggear cuando falla
```python
# ANTES:
@app.get("/users/search")
def search_users(...):
    # Sin logging
    rows = conn.execute(sql, params).fetchall()
    return [User(**dict(r)) for r in rows]
```

**Impacto:**
- No sabés qué parámetros llegaron
- No sabés cuántos resultados devolvió
- Debugging es casi imposible

**Fix:**
```python
# DESPUÉS:
@app.get("/users/search")
def search_users(...):
    print(f"🔍 API search_users: email={email}, phone={phone}, name={name}")
    rows = conn.execute(sql, params).fetchall()
    print(f"✅ Encontrados {len(rows)} usuarios")
    return [User(**dict(r)) for r in rows]
```

---

## 📋 RESUMEN DE CAMBIOS

### Endpoints Modificados (8):

1. **`POST /users`** ✅
   - Logging agregado
   - Normalización mejorada

2. **`GET /users/search`** ⚠️⚠️⚠️ CRÍTICO
   - OR → AND en query SQL
   - Normalización mejorada
   - Logging agregado

3. **`GET /users/by_email`** ✅
   - Logging agregado
   - Normalización mejorada

4. **`GET /users/{user_id}`** ✅
   - Logging agregado

5. **`POST /carts/add_item`** ⚠️⚠️ MUY IMPORTANTE
   - Validación de stock mejorada (cantidad total)
   - Logging detallado agregado
   - Mensajes de error más claros

6. **`GET /carts/summary`** ✅
   - Logging agregado

7. **`POST /carts/clear`** ✅
   - Logging agregado

8. **`POST /orders/checkout`** ⚠️ IMPORTANTE
   - Usa CHECKOUT_BASE_URL de variables de entorno
   - Logging agregado

9. **`GET /checkout/{order_id}`** ⚠️ IMPORTANTE
   - Usa CHECKOUT_FRONTEND_URL de variables de entorno
   - Logging agregado

10. **`GET /orders/last`** ✅
    - Logging agregado

11. **`GET /orders/by_user`** ✅
    - Logging agregado

---

## 🔧 CÓMO APLICAR LOS FIXES

### Opción A: Reemplazo completo del archivo (RECOMENDADO)
El archivo `backoffice_app_CORRECTED.py` contiene todos los fixes aplicados.

```powershell
# 1. Backup del original
Copy-Item backoffice_app.py backoffice_app.py.backup

# 2. Aplicar correcciones
# Manualmente: copiar los endpoints corregidos del archivo de parche

# 3. Verificar
python -c "import backoffice_app; print('✅ Sintaxis OK')"
```

### Opción B: Aplicar manualmente
Buscar y reemplazar cada endpoint usando el código del archivo de parche.

---

## ✅ TESTING DESPUÉS DE APLICAR

### Test 1: Búsqueda de usuarios
```powershell
# Antes del fix: devuelve muchos usuarios irrelevantes
# Después del fix: devuelve solo el usuario exacto

curl http://localhost:8080/users/search?phone=1234567890 `
  -H "x-api-key: 19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk"
```

### Test 2: Agregar al carrito con stock limitado
```powershell
# Debe validar stock correctamente y dar error descriptivo

curl -X POST http://localhost:8080/carts/add_item `
  -H "x-api-key: 19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk" `
  -H "Content-Type: application/json" `
  -d '{"user_id": 1, "product_id": 5, "quantity": 1000}'
```

### Test 3: Checkout URL
```powershell
# Debe generar URL con CHECKOUT_BASE_URL correcto

curl -X POST http://localhost:8080/orders/checkout `
  -H "x-api-key: 19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk" `
  -H "Content-Type: application/json" `
  -d '{"user_id": 1, "email": "test@example.com"}'
```

### Test 4: Verificar logs
```powershell
# Los logs ahora deben mostrar emojis y detalles:
# 🔍 API search_users: email=..., phone=..., name=...
# ✅ Encontrados 1 usuarios
# 🛒 API add_item: user=1, product=5, qty=2
# ✅ Carrito actualizado: 3 items, total=$1234.56
```

---

## 🎯 IMPACTO ESPERADO

### Antes:
❌ Agent crashea al buscar usuario (encuentra múltiples)  
❌ Stock no se valida correctamente  
❌ Links de checkout no funcionan en prod  
❌ Debugging difícil sin logs  

### Después:
✅ Búsqueda de usuarios precisa (AND en vez de OR)  
✅ Stock validado en TODOS los casos  
✅ Links de checkout funcionan en prod  
✅ Debugging fácil con logs detallados  

---

## 📞 Si Tenés Problemas

1. **Verificar sintaxis:**
   ```powershell
   python -c "import backoffice_app"
   ```

2. **Ver logs en tiempo real:**
   ```powershell
   # En terminal de backoffice
   # Deberías ver emojis: 🔍 📝 ✅ ❌
   ```

3. **Probar endpoints manualmente:**
   ```powershell
   # Usar curl o Postman con los ejemplos de arriba
   ```

---

**Última actualización:** Diciembre 2024  
**Prioridad:** CRÍTICA - Aplicar ANTES de deploy
