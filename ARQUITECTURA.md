# 🏗️ ARQUITECTURA DEL SISTEMA

## 📐 Diagrama de Flujo General

```
┌─────────────┐
│   Usuario   │
│  (WhatsApp) │
└──────┬──────┘
       │ Mensaje de texto
       ▼
┌─────────────────────────────────────────────┐
│          TWILIO (WhatsApp API)              │
│  - Recibe mensajes                          │
│  - Enruta a webhook                         │
│  - Envía respuestas                         │
└──────┬──────────────────────────────────────┘
       │ HTTP POST
       ▼
┌─────────────────────────────────────────────┐
│       whatsapp_server.py (FastAPI)          │
│                                             │
│  Endpoint: /whatsapp                        │
│  - Valida request de Twilio                 │
│  - Extrae user_id (teléfono)               │
│  - Enriquece contexto                       │
│  - Gestiona sesión                          │
└──────┬──────────────────────────────────────┘
       │ ADK Runner
       ▼
┌─────────────────────────────────────────────┐
│        agent.py (Google ADK)                │
│                                             │
│  Agente: Milo (Gemini 2.0 Flash)           │
│  - Interpreta intención                     │
│  - Decide qué tools usar                    │
│  - Mantiene contexto de conversación        │
└──────┬──────────────────────────────────────┘
       │ Tool calls
       ▼
┌─────────────────────────────────────────────┐
│    agent_tools_backoffice.py                │
│                                             │
│  Tools disponibles:                         │
│  ├─ search_users()                          │
│  ├─ create_user()                           │
│  ├─ search_products()                       │
│  ├─ add_product_to_cart()                   │
│  ├─ get_cart_summary()                      │
│  ├─ checkout_cart()                         │
│  ├─ clear_cart()                            │
│  └─ get_checkout_link_for_last_order()      │
└──────┬──────────────────────────────────────┘
       │ HTTP requests
       ▼
┌─────────────────────────────────────────────┐
│      backoffice_app.py (FastAPI)            │
│                                             │
│  API Endpoints:                             │
│  ├─ GET/POST /users                         │
│  ├─ GET/POST /products                      │
│  ├─ POST /carts/add_item                    │
│  ├─ GET /carts/summary                      │
│  ├─ POST /orders/checkout                   │
│  └─ GET /orders/by_user                     │
│                                             │
│  Admin Panel:                               │
│  └─ /admin (Jinja2 templates)               │
└──────┬──────────────────────────────────────┘
       │ SQLite
       ▼
┌─────────────────────────────────────────────┐
│           retail.db (SQLite)                │
│                                             │
│  Tablas:                                    │
│  ├─ users                                   │
│  ├─ products                                │
│  ├─ carts                                   │
│  ├─ cart_items                              │
│  └─ orders                                  │
└─────────────────────────────────────────────┘
```

---

## 🔄 Flujo de Conversación Típico

### Ejemplo: "Hola, quiero comprar leche"

```
1. Usuario (WhatsApp)
   └─> Envía: "Hola, quiero comprar leche"

2. Twilio
   └─> POST /whatsapp
       Body: "Hola, quiero comprar leche"
       From: "whatsapp:+5491234567890"
       WaId: "5491234567890"

3. whatsapp_server.py
   ├─> Extrae user_id = "5491234567890"
   ├─> Enriquece: "Su número de WhatsApp es: 5491234567890..."
   └─> Llama a ADK Runner

4. agent.py (Milo)
   ├─> Interpreta: Usuario quiere comprar leche
   ├─> Decisión: Primero necesito identificar al usuario
   └─> Llama: search_users(phone="5491234567890")

5. agent_tools_backoffice.py
   ├─> Normaliza phone: "5491234567890"
   ├─> GET /users/search?phone=5491234567890
   └─> Respuesta: status="not_found"

6. agent.py (Milo)
   ├─> Interpreta: Usuario no existe
   ├─> Decisión: Necesito crear usuario
   └─> Responde: "Hola! Para empezar, ¿cómo te llamás?"

7. Usuario responde: "Juan"

8. agent.py (Milo)
   └─> Responde: "Genial Juan! ¿Y tu email?"

9. Usuario responde: "juan@example.com"

10. agent.py (Milo)
    ├─> Llama: create_user(name="Juan", email="juan@example.com", phone="5491234567890")
    └─> Guarda user_id internamente

11. agent.py (Milo)
    ├─> Retoma intención original: buscar leche
    ├─> Llama: search_products(query="leche")
    └─> Recibe: [
          {id: 5, name: "Leche Entera La Serenísima 1L", price: 450},
          {id: 12, name: "Leche Descremada Sancor 1L", price: 420}
        ]

12. agent.py (Milo)
    └─> Responde: "Encontré estas opciones:
        1. Leche Entera La Serenísima 1L - $450
        2. Leche Descremada Sancor 1L - $420
        ¿Cuál preferís?"

13. Usuario: "La primera"

14. agent.py (Milo)
    ├─> Llama: add_product_to_cart(user_id=123, product_id=5, quantity=1)
    └─> Responde: "Perfecto! Agregué 1x Leche Entera La Serenísima 1L al carrito.
        ¿Querés algo más o finalizamos?"

15. Usuario: "Finalizar"

16. agent.py (Milo)
    ├─> Llama: checkout_cart(user_id=123, email="juan@example.com")
    ├─> Recibe: payment_url="https://.../checkout/456"
    └─> Responde: "Tu pedido está listo! Podés pagar acá:
        https://yoplabs-agent-demo.../checkout/456"

17. whatsapp_server.py
    └─> Envía TwiML response a Twilio

18. Twilio
    └─> Envía mensaje a WhatsApp del usuario

19. Usuario
    └─> Recibe respuesta en WhatsApp ✅
```

---

## 🗂️ Estructura de Datos

### Usuario (users)
```json
{
  "id": 123,
  "name": "Juan Pérez",
  "email": "juan@example.com",
  "phone": "5491234567890",
  "segment": "nuevo",
  "created_at": "2024-12-16T10:30:00"
}
```

### Producto (products)
```json
{
  "id": 5,
  "sku": "LECHE-SER-001",
  "name": "Leche Entera La Serenísima 1L",
  "category": "Lácteos",
  "description": "Leche entera fortificada",
  "price": 450.0,
  "is_offer": false,
  "stock": 50,
  "updated_at": "2024-12-16T09:00:00"
}
```

### Carrito (carts + cart_items)
```json
{
  "cart_id": 789,
  "user_id": 123,
  "status": "active",
  "items": [
    {
      "product_id": 5,
      "name": "Leche Entera La Serenísima 1L",
      "quantity": 1,
      "unit_price": 450.0,
      "line_total": 450.0
    }
  ],
  "total": 450.0
}
```

### Orden (orders)
```json
{
  "id": 456,
  "user_id": 123,
  "cart_id": 789,
  "total": 450.0,
  "payment_status": "pending",
  "created_at": "2024-12-16T10:45:00"
}
```

---

## 🔐 Autenticación y Seguridad

### API Key Flow
```
Tools (agent_tools_backoffice.py)
    │
    ├─> Headers: {"x-api-key": "19PxrNUo..."}
    │
    ▼
Backoffice API (backoffice_app.py)
    │
    ├─> Dependency: require_api_key()
    │
    ├─> Valida: x-api-key == BACKOFFICE_API_KEY
    │
    └─> ✅ Autorizado / ❌ 401 Unauthorized
```

### Admin Panel Flow
```
Usuario
    │
    ├─> POST /admin/login
    │   (username + password)
    │
    ▼
Backoffice
    │
    ├─> Valida: ADMIN_USER + ADMIN_PASSWORD
    │
    ├─> Session: request.session["is_admin"] = True
    │
    ▼
Admin Dashboard
    └─> Dependency: get_current_admin()
        └─> Verifica session
            ✅ Autorizado / ❌ Redirect /admin/login
```

---

## 🌐 Ambientes

### Local (Desarrollo)
```
┌─────────────────────────────┐
│ localhost:8080              │
│ backoffice_app.py           │
│ ├─ API                      │
│ └─ Admin panel              │
└─────────────────────────────┘

┌─────────────────────────────┐
│ localhost:8001              │
│ checkout_web/               │
│ └─ index.html (static)      │
└─────────────────────────────┘

┌─────────────────────────────┐
│ localhost:9002              │
│ whatsapp_server.py          │
│ └─ /whatsapp webhook        │
└─────────────────────────────┘
         ▲
         │ HTTP (via ngrok)
         │
┌─────────────────────────────┐
│ https://xxx.ngrok-free.app  │
│ ngrok tunnel                │
└─────────────────────────────┘
         ▲
         │ HTTPS
         │
┌─────────────────────────────┐
│ Twilio WhatsApp API         │
└─────────────────────────────┘
```

### Producción (Cloud Run)
```
┌─────────────────────────────────────────────────────┐
│ https://yoplabs-agent-demo-....run.app              │
│                                                     │
│ main.py (FastAPI)                                   │
│                                                     │
│ ├─ /healthz         → Health check                 │
│ ├─ /whatsapp        → whatsapp_server.app          │
│ ├─ /checkout-ui/*   → StaticFiles(checkout_web/)   │
│ └─ /*               → backoffice_app.app            │
│                                                     │
│ Container:                                          │
│ ├─ Python 3.11                                      │
│ ├─ retail.db (SQLite)                               │
│ └─ Env vars (env.prod.yaml)                         │
└─────────────────────────────────────────────────────┘
         ▲
         │ HTTPS
         │
┌─────────────────────────────┐
│ Twilio WhatsApp API         │
└─────────────────────────────┘
```

---

## 📦 Deployment Pipeline

```
1. Código local
   └─> git commit & push (opcional)

2. Build
   └─> gcloud builds submit --tag gcr.io/...
       ├─ Dockerfile
       ├─ requirements.txt
       └─> Imagen Docker en GCR

3. Deploy
   └─> gcloud run deploy ...
       ├─ env.prod.yaml
       ├─ Port: 8080
       ├─ Memory: 1Gi
       └─> Cloud Run Service

4. Configuración
   └─> Twilio webhook
       └─> https://....run.app/whatsapp

5. Verificación
   └─> /healthz
   └─> Logs en tiempo real
   └─> Test con WhatsApp
```

---

## 🔍 Puntos de Monitoreo

### Health Checks
```
┌─────────────────────────────────────┐
│ GET /healthz                        │
│ └─> {"status": "ok"}                │
│                                     │
│ GET /                               │
│ └─> {"status": "ok",                │
│      "service": "whatsapp_server"}  │
└─────────────────────────────────────┘
```

### Logs Clave
```
whatsapp_server.py:
├─ "🔔 Incoming WhatsApp from ..."
├─ "✅ Respuesta enviada: ..."
└─ "❌ Error en whatsapp_webhook: ..."

agent_tools_backoffice.py:
├─ HTTP requests (via requests library)
└─ Respuestas normalizadas con status

backoffice_app.py:
├─ Uvicorn access logs
└─ Errores de base de datos
```

### Métricas Cloud Run
```
- Request count
- Request latency (p50, p95, p99)
- Error rate
- Container instances
- CPU utilization
- Memory utilization
```

---

## 🚨 Puntos de Fallo y Mitigación

### 1. Twilio → WhatsApp Server
**Posibles fallos:**
- Timeout (> 15s)
- Network error
- Invalid TwiML response

**Mitigación:**
- Try-catch en todos los niveles
- Timeout en HTTP requests (3s connect, 15s read)
- Respuesta TwiML siempre válida (incluso en error)

### 2. WhatsApp Server → Agent
**Posibles fallos:**
- ADK timeout
- Gemini API error
- Session error

**Mitigación:**
- Timeout en runner.run_async
- Try-catch con mensaje genérico al usuario
- Fallback en creación de sesión

### 3. Agent → Backoffice
**Posibles fallos:**
- API key inválida
- Endpoint no disponible
- Database lock

**Mitigación:**
- Validación de API key
- Try-catch en todas las tools
- Respuestas normalizadas con status
- Retry logic (manual en algunas tools)

### 4. Base de Datos
**Posibles fallos:**
- Database locked
- Disk full
- Corruption

**Mitigación:**
- timeout=30 en conexiones
- check_same_thread=False
- Backup automático (pendiente)

---

## 📊 Performance

### Latencias Esperadas
```
Usuario → Twilio:           ~100ms
Twilio → WhatsApp Server:   ~200ms
WhatsApp Server → Agent:    ~50ms
Agent → Backoffice:         ~100ms
Backoffice → SQLite:        ~10ms
Agent processing (Gemini):  2-5s

Total (típico):             3-6s ✅
Total (peor caso):          10-15s ⚠️
Timeout Twilio:             15s ❌
```

### Optimizaciones Aplicadas
✅ Conexión HTTP reutilizable (requests.Session)
✅ Índices en base de datos (phone, email)
✅ Respuestas tempranas cuando es posible
✅ Instrucciones del agente concisas

### Optimizaciones Pendientes
⚠️ Caché de productos (Redis)
⚠️ Pool de conexiones a DB
⚠️ Streaming de respuestas del agente
⚠️ Compresión de responses

---

## 🎯 Conclusión

Este sistema es una arquitectura **event-driven** simple pero efectiva para un bot conversacional con WhatsApp:

- **Entrada:** Mensaje de WhatsApp
- **Procesamiento:** Agent ADK + Tools
- **Persistencia:** SQLite
- **Salida:** Respuesta por WhatsApp

La clave está en:
1. ✅ Manejo robusto de errores en CADA nivel
2. ✅ Logging detallado para debugging
3. ✅ Normalización consistente de datos
4. ✅ Separación clara de ambientes
5. ✅ Documentación completa

---

**Última actualización:** Diciembre 2024
