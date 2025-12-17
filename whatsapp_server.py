from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

# Validación Twilio (opcional)
from twilio.request_validator import RequestValidator

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# --- Paths base ---
BASE_DIR = Path(__file__).resolve().parent
RETAIL_AGENT_DIR = BASE_DIR / "retail_agent"
ENV_PATH = RETAIL_AGENT_DIR / ".env"

# Solo cargar .env en local/dev
if (os.getenv("ENV", "") or "").lower() in ("dev", "local", ""):
    load_dotenv(ENV_PATH, override=False)

# --- ADK import ---
sys.path.insert(0, str(RETAIL_AGENT_DIR))
from agent import root_agent  # noqa

APP_NAME = "retail_whatsapp"

# -------------------------
# ADK: Runner + sesiones
# -------------------------
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

app = FastAPI(title="Retail WhatsApp Bridge")

# -------------------------
# Twilio validation (toggle)
# -------------------------
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_VALIDATE = (os.getenv("TWILIO_VALIDATE", "false") or "").lower() == "true"

twilio_validator = RequestValidator(TWILIO_AUTH_TOKEN) if (TWILIO_VALIDATE and TWILIO_AUTH_TOKEN) else None

def _public_url_from_request(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    path = request.url.path
    return f"{proto}://{host}{path}"

def validate_twilio_request(request: Request, form_data: dict):
    if not twilio_validator:
        return  # desactivado

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        raise HTTPException(status_code=403, detail="Forbidden")

    url = _public_url_from_request(request)
    ok = twilio_validator.validate(url, form_data, signature)
    if not ok:
        raise HTTPException(status_code=403, detail="Forbidden")

async def ensure_session(user_id: str) -> str:
    """Asegura que existe una sesión para el usuario"""
    session_id = user_id
    try:
        session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        if session is None:
            session = await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        return session.id
    except Exception as e:
        print(f"❌ Error creando sesión: {e}")
        # Crear sesión nueva como fallback
        session = await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        return session.id

async def run_whatsapp_turn(user_id: str, body: str) -> str:
    """Ejecuta un turno de conversación con el agente"""
    try:
        session_id = await ensure_session(user_id)

        # Contexto simplificado para evitar que el modelo piense en voz alta
        enriched_text = (
            f"[INFO INTERNA: Usuario WhatsApp #{user_id}]\n\n"
            f"{body}"
        )

        content = types.Content(role="user", parts=[types.Part(text=enriched_text)])

        final_text = "Perdón, tuve un problema procesando tu mensaje. Probá de nuevo en un toque."
        
        # Iterar sobre TODOS los eventos hasta obtener la respuesta final de texto
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            # Debug: ver qué tipo de evento es
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    func_call = getattr(part, 'function_call', None)
                    if func_call and hasattr(func_call, 'name'):
                        print(f"🔧 Tool call: {func_call.name}")
                    
                    func_resp = getattr(part, 'function_response', None)
                    if func_resp and hasattr(func_resp, 'name'):
                        # Mostrar la respuesta de la tool para debug
                        response_data = getattr(func_resp, 'response', {})
                        print(f"✅ Tool response: {func_resp.name}")
                        print(f"📊 Response data: {response_data}")
            
            # Solo procesamos el evento final que contiene la respuesta de texto
            if event.is_final_response():
                if event.content and event.content.parts:
                    # Buscar la primera part que sea texto
                    for part in event.content.parts:
                        txt = getattr(part, "text", None)
                        if txt:
                            final_text = txt
                            break
                # Una vez encontrada la respuesta final, salimos
                if final_text != "Perdón, tuve un problema procesando tu mensaje. Probá de nuevo en un toque.":
                    break

        return final_text
        
    except Exception as e:
        print(f"❌ Error en run_whatsapp_turn: {e}")
        import traceback
        traceback.print_exc()
        return "Perdón, hubo un problema técnico. Probá de nuevo en un ratito."

@app.on_event("startup")
async def warmup_backoffice():
    """
    Al iniciar el servidor, hace una request al backoffice
    para 'calentarlo' y evitar cold starts en las primeras interacciones.
    """
    import asyncio
    import httpx
    
    backoffice_url = os.getenv("BACKOFFICE_BASE_URL", "")
    if not backoffice_url or "localhost" in backoffice_url or "127.0.0.1" in backoffice_url:
        print("⚡ Modo local, skip warmup")
        return
    
    async def warmup():
        try:
            print(f"🔥 Calentando backoffice: {backoffice_url}")
            async with httpx.AsyncClient(timeout=30) as client:
                # Request simple al listado de productos
                resp = await client.get(
                    f"{backoffice_url}/products",
                    headers={"x-api-key": os.getenv("BACKOFFICE_API_KEY", "")}
                )
                if resp.status_code == 200:
                    print("✅ Backoffice calentado exitosamente")
                else:
                    print(f"⚠️  Backoffice respondió con {resp.status_code}")
        except Exception as e:
            print(f"⚠️  Error calentando backoffice: {e}")
    
    # Ejecutar en background para no bloquear el startup
    asyncio.create_task(warmup())

@app.get("/")
async def health_check():
    """Health check para Cloud Run"""
    return {"status": "ok", "service": "whatsapp_server"}

@app.post("/whatsapp")
@app.post("/whatsapp/")
async def whatsapp_webhook(request: Request):
    """Webhook principal para mensajes de WhatsApp vía Twilio"""
    try:
        form = await request.form()
        form_dict = dict(form)

        # 1) Validar Twilio si está activo
        if TWILIO_VALIDATE:
            try:
                validate_twilio_request(request, form_dict)
            except HTTPException as e:
                print("❌ Twilio validation failed:", e.detail)
                raise

        # 2) Extraer datos del mensaje
        body = (form.get("Body") or "").strip()
        wa_id = (form.get("WaId") or "").strip()
        from_raw = (form.get("From") or "").strip()

        # Priorizar WaId, luego From limpio
        user_id = wa_id or from_raw.replace("whatsapp:", "").replace("+", "") or "unknown"

        print(f"🔔 Incoming WhatsApp from {user_id[:10]}***: '{body[:50]}...'")

        # 3) Procesar mensaje
        if not body:
            reply_text = "No recibí ningún texto 🙂"
        else:
            reply_text = await run_whatsapp_turn(user_id, body)

        # 4) Responder con TwiML
        twiml = MessagingResponse()
        twiml.message(reply_text)
        
        print(f"✅ Respuesta enviada: '{reply_text[:100]}...'")
        
        return Response(content=str(twiml), media_type="application/xml")
        
    except Exception as e:
        print(f"❌ Error en whatsapp_webhook: {e}")
        import traceback
        traceback.print_exc()
        
        # Responder con mensaje genérico en caso de error
        twiml = MessagingResponse()
        twiml.message("Disculpá, tuve un problema técnico. Probá de nuevo en un ratito.")
        return Response(content=str(twiml), media_type="application/xml")

# Endpoint alternativo para compatibilidad
@app.post("/")
async def whatsapp_webhook_root(request: Request):
    """Alias del webhook en raíz para compatibilidad"""
    return await whatsapp_webhook(request)
