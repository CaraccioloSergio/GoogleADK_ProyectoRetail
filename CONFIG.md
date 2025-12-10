
---

## 8. `CONFIG.md` – Guía paso a paso

```markdown
# CONFIG.md – Guía paso a paso

Esta guía asume:

- Tenés **Python 3.10+** instalado
- Estás en una máquina local con acceso a terminal
- Ya tenés o vas a crear una API key de **Gemini** en Google AI Studio

---

## 1. Clonar el repo (o crear carpeta)

# CONFIG.md — Configuración y puesta en marcha

Esta guía explica cómo configurar y ejecutar el proyecto en un entorno
local de desarrollo (Windows PowerShell). Contiene ejemplos de variables
de entorno, comandos para levantar los servicios y notas sobre la DB.

## Requisitos
- Python 3.10+
- Powershell (Windows) o cualquier terminal POSIX
- Opcional: `curl` o `httpie` para probar endpoints

## 1) Clonar el repo
```powershell
git clone https://github.com/CaraccioloSergio/GoogleADK_ProyectoRetail.git
cd GoogleADK_ProyectoRetail
```

## 2) Entorno virtual e instalación
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3) Variables de entorno relevantes

- `BACKOFFICE_BASE_URL` (opcional): URL base del backoffice. Default: `http://localhost:8000`.
- `CHECKOUT_BASE_URL` (opcional): URL base del checkout web. Default: `http://localhost:8001/index.html`.
- `ADMIN_USER` / `ADMIN_PASSWORD` (opcional): credenciales del admin. Default: `admin` / `admin123`.

Ejemplo de cómo exportarlas en PowerShell (temporal en la sesión):
```powershell
$env:BACKOFFICE_BASE_URL = "http://localhost:8000"
$env:CHECKOUT_BASE_URL = "http://localhost:8001/index.html"
$env:ADMIN_USER = "admin"
$env:ADMIN_PASSWORD = "admin123"
```

## 4) Archivo `.env` (opcional)

Si preferís usar un archivo `.env`, creá uno en la raíz con este contenido:

```
BACKOFFICE_BASE_URL=http://localhost:8000
CHECKOUT_BASE_URL=http://localhost:8001/index.html
ADMIN_USER=admin
ADMIN_PASSWORD=admin123
```

Nota: `backoffice_app.py` actualmente lee algunas configuraciones directamente
desde `os.getenv`. Si querés que el servidor cargue `.env` automáticamente,
podés usar `python-dotenv` (ya incluido) y cargarlo al inicio del proceso.

## 5) Inicializar y ejecutar el backoffice (FastAPI)

El backoffice crea la base SQLite (`retail.db`) al iniciarse si no existe,
ejecutando el script `schema.sql`.

```powershell
# Desde la raíz del repo
uvicorn backoffice_app:app --reload --host 0.0.0.0 --port 8000
```

## 6) Ejecutar el checkout web (servidor estático)

```powershell
cd checkout_web
python -m http.server 8001
```

## 7) Admin panel

- Acceder en `http://localhost:8000/admin`.
- Credenciales por defecto: `admin` / `admin123`.

## 8) Probar el flujo rápido (ejemplo)

- Crear un producto:
```powershell
curl -X POST "http://localhost:8000/products" -H "Content-Type: application/json" -d '{"sku":"P001","name":"Leche 1L","price":150.0}'
```

- Crear un usuario:
```powershell
curl -X POST "http://localhost:8000/users" -H "Content-Type: application/json" -d '{"name":"Juan","email":"juan@example.com"}'
```

- Agregar producto al carrito (user_id y product_id deben existir):
```powershell
curl -X POST "http://localhost:8000/carts/add_item" -H "Content-Type: application/json" -d '{"user_id":1,"product_id":1,"quantity":2}'
```

- Hacer checkout (genera `payment_url` apuntando al `checkout_web`):
```powershell
curl -X POST "http://localhost:8000/orders/checkout" -H "Content-Type: application/json" -d '{"user_id":1,"email":"juan@example.com"}'
```

## 9) Configuración para el agente (dev)

- `retail_agent/agent_tools_backoffice.py` usa `BACKOFFICE_BASE_URL` para
	comunicarse con el backoffice. Asegurate de lanzar el backoffice en la
	URL correcta o exportar la variable.

- Ejemplo de prueba manual de tools desde REPL (venga desde la raíz con venv activado):
```powershell
python
>>> from retail_agent.agent_tools_backoffice import search_products
>>> search_products('leche')
```

## 10) Notas y recomendaciones
- Cambiar credenciales por defecto antes de cualquier demo pública.
- Para entornos de producción: usar una base de datos gestionada, HTTPS,
	almacenamiento de secretos y mecanismos de autenticación robustos.

## 11) Troubleshooting rápido
- Si `uvicorn` no arranca: verificá que el venv esté activado y las
	dependencias instaladas.
- Si el checkout no muestra items: confirmá que `CHECKOUT_BASE_URL` esté
	apuntando al servidor estático correcto y que `payment_url` recibido del
	backoffice contiene el parámetro `items`.

Si querés, puedo también:
- Añadir un `run_agent.py` de ejemplo para instanciar el `root_agent`.
- Preparar un `.env.example` y un pequeño script `start-dev.ps1`.
