from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

# Importar apps
from backoffice_app import app as backoffice_app

# Importar el webhook de whatsapp directamente
import whatsapp_server

app = FastAPI(title="YopLabs Agent Demo")

# Healthcheck
@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"

# WhatsApp webhooks (directamente en la app principal)
@app.post("/whatsapp")
@app.post("/whatsapp/")
async def whatsapp_webhook(request: Request):
    return await whatsapp_server.whatsapp_webhook(request)

# Checkout UI
app.mount(
    "/checkout-ui",
    StaticFiles(directory="checkout_web", html=True),
    name="checkout-ui",
)

# Backoffice al final (catch-all)
app.mount("/", backoffice_app)