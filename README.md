# GoogleADK – Proyecto Retail (Milo por WhatsApp)

Proyecto demo para el equipo **GenIA** de YopLabs.

Es un agente de supermercado llamado **Milo** construido con **Google Agent Development Kit (ADK)**, que se conecta a un **backoffice en FastAPI + SQLite**, expone un **checkout web estático** y conversa con clientes por **WhatsApp usando Twilio**.

> Objetivo: tener un flujo de punta a punta para demo técnica/comercial:  
> WhatsApp → Agente ADK (Milo) → Backoffice → Checkout.

---

## ✨ Funcionalidades 

- Identificación de usuarios por:
  - Nombre
  - Email
  - (y número de WhatsApp en la DB, listo para escalar la demo)
- Búsqueda de productos en un catálogo de prueba.
- Manejo completo de carrito:
  - Agregar productos.
  - Ver resumen.
- Checkout:
  - Generación de **link de pago** apuntando al mini-checkout local.
- Integración con **WhatsApp (Twilio Sandbox)**:
  - Conversación natural con Milo desde tu celu.
  - El agente **mantiene contexto** de la sesión por número de WhatsApp.

---

## 🧱 Arquitectura general

- **`backoffice_app.py`**
  - API JSON + Panel admin (FastAPI + Jinja2).
  - DB SQLite (`retail.db`).
  - Endpoints:
    - `/users`, `/users/search`, `/users/by_email`
    - `/products`
    - `/carts/add_item`, `/carts/summary`
    - `/orders/checkout`, `/orders`
- **`retail_agent/agent.py`**
  - Definición del agente ADK (**Milo**).
  - Usa `agent_tools_backoffice.py` para hablar con el backoffice.
- **`retail_agent/agent_tools_backoffice.py`**
  - Implementa las “tools” del agente:
    - `search_users`, `create_user`
    - `search_products`
    - `add_product_to_cart`, `get_cart_summary`
    - `checkout_cart`
- **`checkout_web/`**
  - Mini frontend estático HTML/CSS/JS para mostrar el carrito y simular el pago.
- **`whatsapp_server.py`**
  - FastAPI con endpoint de webhook para Twilio.
  - Usa un `Runner` de Google ADK para enviar/recibir mensajes del agente.
  - Gestiona sesiones por número de WhatsApp.

---

## 📁 Estructura del proyecto

```text
GoogleADK_ProyectoRetail/
│
├── backoffice_app.py          # FastAPI: API + panel administracion
├── retail.db                  # DB SQLite (se genera/llena en runtime)
├── schema.sql                 # Esquema de la base de datos
│
├── retail_agent/
│   ├── __init__.py
│   ├── .env.example           # Ejemplo de config para el agente
│   ├── .env                   # (ignorado en git) credenciales reales
│   ├── agent.py               # Definición del agente Milo (Google ADK)
│   └── agent_tools_backoffice.py  # Tools conectadas al backoffice
│
├── checkout_web/
│   ├── index.html             # Landing de checkout
│   ├── script.js              # Lógica del resumen de compra
│   └── styles.css             # Estilos del checkout
│
├── static/                    # Assets estáticos del panel admin
├── templates/                 # Plantillas Jinja2 del panel admin
│
├── whatsapp_server.py         # Webhook WhatsApp (Twilio) + Runner ADK
├── requirements.txt           # Dependencias Python
├── CONFIG.md                  # Notas internas de configuración
└── README.md                  # Este archivo
````

---

## 🔧 Requisitos

* **Python** 3.10 o superior.
* **pip**
* (Opcional) **Git** para clonar el repo.
* Cuenta en **Twilio** con **WhatsApp Sandbox** habilitado.
* Clave de **Google AI Studio** o configuración de **Vertex AI**
  (el agente usa `gemini-2.0-flash` vía `google-adk` / `google-genai`).

---

## 🚀 Setup inicial (local)

Desde la raíz del proyecto (`GoogleADK_ProyectoRetail/`):

### 1. Clonar y entrar al repo

```bash
git clone https://github.com/CaraccioloSergio/GoogleADK_ProyectoRetail.git
cd GoogleADK_ProyectoRetail
```

### 2. Crear y activar entorno virtual

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## ⚙️ Variables de entorno

El proyecto usa dos `.env`:

1. **Para el agente**: `retail_agent/.env`
2. (Opcional) Podés usar variables de entorno del sistema para Twilio / Google.

Ejemplo sugerido para `retail_agent/.env`:

```env
# Google / Gemini
GOOGLE_API_KEY=TU_API_KEY_DE_GOOGLE_AI

# Backoffice
BACKOFFICE_BASE_URL=http://localhost:8000

# Checkout (link que genera el backoffice)
CHECKOUT_BASE_URL=http://localhost:8001/index.html
```

Ejemplo de variables de entorno para **Twilio** (las podés exportar en tu shell o configurar en `.env` del root si preferís):

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886     # número del sandbox
```

---

## 🖥️ Levantar los servicios

### 1. Backoffice (API + Panel admin)

Desde la raíz del proyecto:

```bash
uvicorn backoffice_app:app --reload --host 0.0.0.0 --port 8000
```

* La primera vez ejecuta `init_db()` y crea/llena `retail.db` con `schema.sql`.
* Panel admin:
  👉 `http://localhost:8000/admin`
  Usuario por defecto: `admin` / `admin123` (solo demo).

### 2. Checkout web

En otra terminal:

```bash
cd checkout_web
python -m http.server 8001
```

* El backoffice genera links del tipo:

  ```
  http://localhost:8001/index.html?user_id=...&name=...&email=...&amount=...&items=...
  ```

---

## ☎️ Integración con WhatsApp (Twilio)

### 1. Levantar el servidor de WhatsApp

Volvé a la raíz del proyecto con el entorno virtual activo:

```bash
uvicorn whatsapp_server:app --reload --port 9002
```

> Podés usar otro puerto, pero tiene que coincidir con el que expongas por **ngrok** y configures en Twilio.

### 2. Exponer el servidor con ngrok

En otra terminal:

```bash
ngrok http 9002
```

* Copiá la URL HTTPS que te dé ngrok, por ejemplo:

  ```
  https://abcd-1234-xyz.ngrok-free.app
  ```

### 3. Configurar Twilio Sandbox

En la consola de Twilio (WhatsApp Sandbox):

* **WHEN A MESSAGE COMES IN** → pegá la URL de ngrok con el path del webhook:

  ```text
  https://abcd-1234-xyz.ngrok-free.app/whatsapp
  ```

* Guardá cambios.

### 4. Probar desde tu celular

1. Seguí las instrucciones de Twilio para unirte al sandbox (enviando el código que te dan).
2. Escribí a tu número de sandbox (algo como `whatsapp:+14155238886`).
3. Mandá un mensaje, por ejemplo:

   > Hola, quiero hacer mi compra de supermercado

En la consola de Uvicorn deberías ver el log con los form params de Twilio y la respuesta generada por Milo.

---

## 👨‍🍳 Sobre Milo (el agente)

El agente está definido en `retail_agent/agent.py`:

* Modelo: `gemini-2.0-flash`
* Rol:

  * Vendedor de supermercado amable, directo, en tono rioplatense.
  * Mantiene el contexto de:

    * Usuario identificado (nombre, email, teléfono / WhatsApp).
    * Carrito actual.
* Usa las tools de `agent_tools_backoffice.py` para:

  * `search_users` / `create_user`
  * `search_products`
  * `add_product_to_cart`
  * `get_cart_summary`
  * `checkout_cart`

---

## 🧪 Probando el backoffice con curl (opcional)

Crear un usuario:

```bash
curl -X POST "http://localhost:8000/users" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Juan\",\"email\":\"juan@example.com\"}"
```

Crear un producto:

```bash
curl -X POST "http://localhost:8000/products" ^
  -H "Content-Type: application/json" ^
  -d "{\"sku\":\"P001\",\"name\":\"Leche 1L\",\"price\":150.0}"
```

---

## 🤝 Contribuciones y notas

* Este repo es un **POC** para demos internas y clientes.
* Antes de usar en producción:

  * Mover credenciales a un manejador seguro (Secret Manager, Vault, etc.).
  * Cambiar usuarios/contraseñas por defecto.
  * Revisar CORS, seguridad de endpoints, logging, etc.

---