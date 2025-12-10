# Retail Agent Demo (Google ADK)

Demo de un **agente de ventas y soporte para retail** construido con **Google Agent Development Kit (ADK)**.

Funcionalidades principales:

- Identificación de usuario por **email** y/o **teléfono**
- Búsqueda de productos en un **catálogo de prueba**
- Manejo de **carrito de compras** (agregar productos, ver resumen)
- Simulación de **checkout**, generando un **link de pago** que apunta a una landing de YopLabs

Este proyecto está pensado como **POC** para usar en:
- Demos técnicas (devs)
- Demos comerciales (LinkedIn, potenciales clientes)
- Base para conectar luego con **WhatsApp** (Twilio / Meta Cloud API)

---

## Estructura

```text
retail-agent-demo/
│
├── retail_agent/
│   ├── __init__.py
│   ├── agent.py          # Definición del agente ADK y tools
│   ├── data.py           # "Base de datos" de prueba (usuarios + productos)
│   ├── cart_store.py     # Manejo de carritos en memoria
│   └── .env.example      # Ejemplo de configuración de entorno
│
├── requirements.txt
# Retail Agent Demo (Google ADK)

Demo de un agente de ventas y soporte para retail construido con el
Google Agent Development Kit (ADK). Es una prueba de concepto que
integra un backoffice (FastAPI + SQLite) con un conjunto de tools que
usa el agente para identificar usuarios, buscar productos, administrar
carritos y generar links de pago para un checkout simple.

Características principales
- Identificación de usuario por `email` y/o `teléfono`.
- Búsqueda de productos en un catálogo local de ejemplo.
- Manejo de carrito de compras (agregar, ver resumen, checkout).
- Panel administrativo simple (FastAPI + plantillas Jinja2).

Casos de uso
- Demos técnicas y comerciales.
- Base para integrar canales (WhatsApp, web chat) usando Google ADK.

Estructura del proyecto

```
retail-agent-demo/
│
├── backoffice_app.py        # FastAPI app (API + panel admin)
├── schema.sql              # Esquema SQLite para la DB local
├── retail.db               # (se crea al iniciar el backoffice si no existe)
├── retail_agent/           # Código del agente y tools (Google ADK)
│   ├── agent.py
│   └── agent_tools_backoffice.py
├── requirements.txt
├── CONFIG.md               # Guía paso a paso de configuración y uso
├── README.md
└── checkout_web/           # Mini frontend estático para el flujo de checkout
        ├── index.html
        ├── script.js
        └── styles.css
```

Quickstart (local)
1. Requisitos
     - Python 3.10+ instalado.
     - Git (opcional) para clonar el repo.

2. Crear y activar un entorno virtual
     - Windows (PowerShell):
         ```powershell
         python -m venv .venv
         .\.venv\Scripts\Activate.ps1
         ```

3. Instalar dependencias
     ```powershell
     pip install -r requirements.txt
     ```

4. Variables de entorno (opcional)
- `BACKOFFICE_BASE_URL` — URL base para que el agente hable con el backoffice (por defecto `http://localhost:8000`).
- `CHECKOUT_BASE_URL` — URL base que usa el backoffice para generar el link de pago (por defecto `http://localhost:8001/index.html`).
- `ADMIN_USER` / `ADMIN_PASSWORD` — credenciales del panel admin (por defecto `admin` / `admin123`).

5. Iniciar backoffice (API + admin)
     ```powershell
     # desde la raíz del proyecto
     uvicorn backoffice_app:app --reload --host 0.0.0.0 --port 8000
     ```
     - La primera vez se ejecuta `init_db()` y se crea `retail.db` con `schema.sql`.

6. Iniciar el mini-checkout web (servidor estático)
     ```powershell
     cd checkout_web
     python -m http.server 8001
     ```

7. Abrir panel admin
     - URL: `http://localhost:8000/admin`
     - Usuario por defecto: `admin` / `admin123` (cambiar para producción).

Probando endpoints (ejemplos)
- Crear producto (POST):
    ```powershell
    curl -X POST "http://localhost:8000/products" -H "Content-Type: application/json" -d '{"sku":"P001","name":"Leche 1L","price":150.0}'
    ```
- Crear usuario (POST):
    ```powershell
    curl -X POST "http://localhost:8000/users" -H "Content-Type: application/json" -d '{"name":"Juan","email":"juan@example.com"}'
    ```

Sobre el agente (Google ADK)
- El agente está definido en `retail_agent/agent.py`. Usa `google.adk.agents.Agent`
    y emplea las tools en `retail_agent/agent_tools_backoffice.py` para consultar
    y operar sobre el backoffice.
- `agent_tools_backoffice.py` contiene helpers que consumen la API del
    backoffice (`BACKOFFICE_BASE_URL`) para: identificar/crear usuarios,
    buscar productos, agregar ítems al carrito, ver el resumen y hacer
    checkout.
- Este repo incluye la lógica del agente; lanzar un runtime de ADK o
    integrarlo con un canal (WhatsApp, web) queda fuera del scope, pero
    la definición del agente (`root_agent`) está lista para importarse
    desde un runner que instancie el SDK de Google ADK.

Contribuir
- Abrir un issue o PR con mejoras. Para cambios en dependencias,
    actualizá `requirements.txt`.

Licencia y créditos
- Proyecto de ejemplo / POC. Adaptá credenciales y secretos antes de
    usar en producción.

Contacto
- Autor: revisá el repo para datos del owner o contactame vía GitHub.
